"""PostProcessor ABC + registry.

Each post-processor takes a ParsedInvoice + the original file path,
runs a verification/correction step, and returns the (possibly updated)
ParsedInvoice. Multiple post-processors can be chained.

Why this lives under local/ and not at top level:
  - Cloud OCR backends (Tencent, Baidu) return structured data without
    raw text access — they don't have anything to verify against.
  - Only local backends retain the file path and have access to raw
    pdfplumber text for cross-validation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...base import ParsedInvoice


class PostProcessor(ABC):
    """Base class for post-processing steps."""

    #: Human-readable name for logging
    name: str = ""

    @abstractmethod
    def run(self, parsed: ParsedInvoice, file_path: str) -> ParsedInvoice:
        """Verify/correct the parsed invoice. Return (possibly updated) parse."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: list[PostProcessor] = []


def register_post_processor(pp: PostProcessor) -> PostProcessor:
    if not pp.name:
        raise ValueError("PostProcessor.name must be set before register_post_processor()")
    _REGISTRY.append(pp)
    return pp


def get_post_processors() -> list[PostProcessor]:
    """Return registered post-processors in registration order."""
    return list(_REGISTRY)
