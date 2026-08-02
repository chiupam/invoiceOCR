"""SiliconFlow-hosted DeepSeek-OCR backend.

Hits the SiliconFlow OpenAI-compatible API to call DeepSeek-OCR.
Returns text+bbox blocks in our standard TextBlock format.

Why DeepSeek-OCR (not PaddleOCR-VL):
  - PaddleOCR-VL is a 0.9B VLM that hallucinates on dense layouts
  - DeepSeek-OCR is a 3B purpose-built OCR model that returns
    faithful text with grounding boxes
  - Both are free on SiliconFlow's free tier

Why this is a "local" backend (despite being cloud-hosted):
  - The OCR engine returns text+bbox (not structured fields)
  - The post-processing layer (pdfplumber) does the cross-validation
  - The architecture is identical to what a self-hosted vLLM server
    would look like — only the endpoint URL changes

Configuration:
  - SF_API_KEY: must be set (SiliconFlow account)
  - SF_OCR_MODEL: defaults to "deepseek-ai/DeepSeek-OCR"
  - SF_OCR_ENDPOINT: defaults to "https://api.siliconflow.cn/v1"
"""
from __future__ import annotations

import base64
import logging
import os
import re
import time
from typing import Optional

import requests

from ..base import ParsedInvoice, TextBlock, register_backend
from .base import LocalBackend

logger = logging.getLogger(__name__)


# DeepSeek-OCR output format: <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>
_RE_OCR_RE = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>",
    re.DOTALL,
)


class SiliconFlowOCRBackend(LocalBackend):
    """DeepSeek-OCR via SiliconFlow (free tier)."""

    name = "siliconflow"
    display_name = "SiliconFlow DeepSeek-OCR (本地 OCR)"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("SF_API_KEY", "")
        self.model = model or os.environ.get("SF_OCR_MODEL", "deepseek-ai/DeepSeek-OCR")
        self.endpoint = (
            endpoint
            or os.environ.get("SF_OCR_ENDPOINT", "https://api.siliconflow.cn/v1")
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _call_ocr(self, file_path: str) -> list[TextBlock]:
        """POST the PDF to SiliconFlow, parse <|ref|><|det|> output."""
        if not self.api_key:
            raise RuntimeError(
                "SiliconFlow API key not configured. "
                "Set SF_API_KEY env var or pass api_key=..."
            )

        # Read file as base64 data URL
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        ext = file_path.lower().rsplit(".", 1)[-1]
        mime = "application/pdf" if ext == "pdf" else f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(file_bytes).decode()}"

        # Call the API
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "<image>\n<|grounding|>OCR this image."},
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"SiliconFlowOCR: POST {url} model={self.model} file={file_path}")
        t0 = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        elapsed = time.time() - t0
        logger.info(f"SiliconFlowOCR: response in {elapsed:.1f}s, status={resp.status_code}")

        if resp.status_code != 200:
            raise RuntimeError(
                f"SiliconFlow OCR failed: {resp.status_code} {resp.text[:500]}"
            )

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Parse <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|> output
        blocks = []
        for m in _RE_OCR_RE.finditer(content):
            text = m.group(1).strip()
            x0, y0, x1, y1 = map(int, m.groups()[1:5])
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    bbox=(x0, y0, x1, y1),
                    confidence=1.0,  # OCR doesn't expose per-block confidence
                )
            )
        logger.info(f"SiliconFlowOCR: parsed {len(blocks)} text blocks")
        return blocks


# Register on import
register_backend(SiliconFlowOCRBackend())
