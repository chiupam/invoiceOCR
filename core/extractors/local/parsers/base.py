"""Parser ABC: text+bbox → ParsedInvoice fields.

A parser knows the layout of one 票据 type. It scans the text blocks
for known field labels (票据代码, 发票号码, 校验码, etc.) and extracts the
values that follow them. It also finds line-item rows by detecting the
table header row and walking column boundaries.

Concrete parsers:
  - medical.py: 中央医疗门诊/住院收费票据
  - vat.py: 增值税电子发票 (普通/专用/数电)
  - train.py: future (火车票 PDF)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ...base import ParsedInvoice, TextBlock


class Parser(ABC):
    """ABC for per-doc-type layout parsers."""

    #: Stable id used in registry (matches DocType.type_id)
    name: str = ""

    @abstractmethod
    def parse(self, blocks: list[TextBlock], file_path: str = "") -> ParsedInvoice:
        """Parse blocks → ParsedInvoice.

        `file_path` is provided in case the parser needs to do
        PDF-level inspection (e.g. to detect multi-page structures).
        Most parsers don't need it.
        """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Parser] = {}


def register_parser(parser: Parser) -> Parser:
    if not parser.name:
        raise ValueError("Parser.name must be set before register_parser()")
    _REGISTRY[parser.name] = parser
    return parser


def unregister_parser(name: str) -> None:
    _REGISTRY.pop(name, None)


def get_parser(name: str) -> Optional[Parser]:
    return _REGISTRY.get(name)


def all_parsers() -> list[Parser]:
    return list(_REGISTRY.values())
