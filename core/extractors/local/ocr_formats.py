"""Output-format parsers for VLM OCR responses.

Different VLM OCR models serialize their output differently:

  - DeepSeek-OCR:  <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>
                   (grounding boxes, one per text region)
  - Qwen3-VL etc.: plain labeled text, one field per line
  - frob/unlimited-ocr (Ollama):
                   "text [x0,y0,x1,y1]内容"
                   "table [x0,y0,x1,y1]<html>..."
                   (region label + bbox + content, mixed)

Instead of growing an if/else chain inside the backend, each model
family registers a parser keyed by a model-name glob. The backend
looks up the parser for the configured model and delegates.

New models with a new output shape = one new parser function + one
register_format() line. No backend changes.
"""
from __future__ import annotations

import fnmatch
import logging
import re
from typing import Callable

from ..base import TextBlock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parsers. Each takes the raw response content string and returns
# a list of TextBlock.
# ---------------------------------------------------------------------------

# DeepSeek-OCR: <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>
_RE_DEEPSEEK = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>",
    re.DOTALL,
)


def _parse_deepseek(content: str) -> list[TextBlock]:
    blocks = []
    for m in _RE_DEEPSEEK.finditer(content):
        text = m.group(1).strip()
        if not text:
            continue
        x0, y0, x1, y1 = map(int, m.groups()[1:5])
        blocks.append(TextBlock(text=text, bbox=(x0, y0, x1, y1), confidence=1.0))
    return blocks


# frob/unlimited-ocr (Ollama): "text [x0,y0,x1,y1]内容" or
# "table [x0,y0,x1,y1]<html>..." — region label + bbox + content.
# Line-oriented format: one region per line.
_RE_UNLIMITED = re.compile(
    r"^(text|table|header|footer|figure|formula|title|seal)\s*"
    r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\s*(.*)$",
    re.MULTILINE,
)


def _parse_unlimited(content: str) -> list[TextBlock]:
    blocks = []
    for m in _RE_UNLIMITED.finditer(content):
        label, x0, y0, x1, y1, body = m.groups()
        body = body.strip()
        if not body:
            continue
        # Table bodies are HTML — strip tags for the parser, keep the raw
        # in block_id for future structured-table handling.
        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\s+", " ", text).strip()
        blocks.append(
            TextBlock(
                text=text,
                bbox=(int(x0), int(y0), int(x1), int(y1)),
                confidence=1.0,
                block_id=f"{label}:table" if label == "table" else label,
            )
        )
    return blocks


def _parse_plain_text(content: str) -> list[TextBlock]:
    """Fallback: one block per non-empty line, synthetic Y for reading order."""
    blocks = []
    for i, line in enumerate(content.split("\n")):
        line = line.strip()
        if line:
            y = i * 20.0
            blocks.append(
                TextBlock(text=line, bbox=(0.0, y, 500.0, y + 20.0), confidence=1.0)
            )
    return blocks


# ---------------------------------------------------------------------------
# Registry: model-name glob → parser
# ---------------------------------------------------------------------------

FormatParser = Callable[[str], list[TextBlock]]

_FORMAT_REGISTRY: list[tuple[str, FormatParser]] = []


def register_format(model_glob: str, parser: FormatParser) -> None:
    """Register a parser for models matching `model_glob` (fnmatch)."""
    _FORMAT_REGISTRY.append((model_glob, parser))


def get_format_parser(model: str) -> FormatParser:
    """Find the parser for `model`. Falls back to plain-text."""
    for glob, parser in _FORMAT_REGISTRY:
        if fnmatch.fnmatch(model.lower(), glob.lower()):
            return parser
    return _parse_plain_text


# --- Built-in registrations ----------------------------------------------

register_format("deepseek*", _parse_deepseek)
register_format("*unlimited-ocr*", _parse_unlimited)
# Plain-text fallback is the default for everything else (Qwen3-VL, GLM-4.5V, ...)
