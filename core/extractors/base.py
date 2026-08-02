"""Shared contract for OCR backends.

Three things live here:

  - TextBlock: a tuple of (text, bbox, confidence) — what text-based
    backends (pdfplumber, DeepSeek-OCR, ...) produce.

  - ParsedInvoice: the final structured output that DocType.format()
    consumes. Backend-specific, but the keys are stable.

  - Backend ABC + registry: every backend subclass implements extract()
    and registers itself. The invoice_formatter.py dispatches via
    get_backend(name).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# TextBlock: the lingua franca between text-based backends and parsers
# ---------------------------------------------------------------------------

@dataclass
class TextBlock:
    """One text region with its bounding box.

    pdfplumber produces this from extract_words() directly.
    DeepSeek-OCR produces this from its <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|> output.
    Tencent Cloud OCR bbox output (when enabled) is also normalized to this.

    Coords are in PDF points (1pt = 1/72 inch). For scanned PDFs, they
    come from the OCR engine's coordinate system; we don't rescale.
    """
    text: str
    bbox: tuple[float, float, float, float]  # (x0, top, x1, bottom)
    confidence: float = 1.0
    page: int = 0                       # 0-indexed page number
    block_id: Optional[str] = None       # backend-specific grouping (e.g. table cell)

    def __repr__(self):
        return f"TextBlock({self.text!r}, bbox={self.bbox}, conf={self.confidence:.2f})"


# ---------------------------------------------------------------------------
# ParsedInvoice: the final structured output every backend produces
# ---------------------------------------------------------------------------

@dataclass
class ParsedInvoice:
    """Backend-agnostic representation of one extracted invoice.

    Produced by every Extractor regardless of source (Tencent, Baidu,
    pdfplumber, DeepSeek-OCR, etc.). Consumed by DocType.format() to
    render the app's UI sections.

    Type-specific blocks (medical_info, travel_info) stay as plain
    dicts for forward compatibility — adding a new DocType doesn't
    require changing this dataclass.
    """
    source: str                            # "tencent" | "baidu" | "siliconflow" | "self_hosted" | "pdfplumber"
    invoice_type: str = ""                 # "增值税专用发票" | "中央医疗门诊收费票据" | ...

    # Top-level identifiers
    invoice_code: str = ""                 # 票据代码 / 发票代码
    invoice_number: str = ""               # 票据号码 / 发票号码
    invoice_date: str = ""                 # ISO YYYY-MM-DD
    invoice_date_raw: str = ""             # Original string for display
    check_code: str = ""                   # 校验码
    machine_number: str = ""               # 机器编号

    # Amounts
    total_amount: str = ""                 # 合计金额 (¥-prefixed)
    total_tax: str = ""                    # 合计税额
    amount_in_words: str = ""              # 价税合计(大写)
    amount_in_figures: str = ""            # 价税合计(小写)

    # Parties (some types leave these empty)
    seller_name: str = ""
    seller_tax_id: str = ""
    seller_address: str = ""
    seller_bank_info: str = ""
    buyer_name: str = ""
    buyer_tax_id: str = ""
    buyer_address: str = ""
    buyer_bank_info: str = ""

    # Misc fields that don't fit elsewhere
    issuer: str = ""                       # 开票人 (some receipts have this)
    remarks: str = ""                      # 备注 (free-text blob)

    # Type-specific blocks (each type populates only its own)
    medical_info: dict = field(default_factory=dict)
    travel_info: dict = field(default_factory=dict)

    # Line items (uniform shape across types)
    items: list = field(default_factory=list)
    # Each item: {"name": str, "quantity": str, "unit": str,
    #             "unit_price": str, "amount": str, "remark": str}

    # Audit / debugging
    raw: dict = field(default_factory=dict)   # original backend response

    # Post-processing metadata
    post_processed: bool = False            # True if pdfplumber corrected something
    corrections: list = field(default_factory=list)  # list of (field, old, new)


# ---------------------------------------------------------------------------
# Backend ABC + registry
# ---------------------------------------------------------------------------

class Backend(ABC):
    """One OCR engine that turns a file into a ParsedInvoice.

    Two families (see module docstring):
      - CloudBackend: server returns structured fields directly
      - LocalBackend: server returns text+bbox; backend runs parser
                      and optional post-processing

    Every backend registers itself at import time via register_backend().
    """
    #: Stable id used in Settings + DB column
    name: str = ""
    #: Human-readable name shown in the upload form picker
    display_name: str = ""

    @abstractmethod
    def extract(self, file_path: str, doc_type: str = "") -> ParsedInvoice:
        """Extract structured data from `file_path`.

        Parameters
        ----------
        file_path : str
            Local path to a PDF or image file.
        doc_type : str
            Document type id ('vat' | 'medical' | 'train' | '').
            For cloud backends this is informational.
            For local backends this selects which Parser to dispatch to.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Returns False if dependencies are missing or API key absent.

        Used to hide disabled backends from the upload form picker.
        """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Backend] = {}


def register_backend(backend: Backend) -> Backend:
    """Register a Backend instance. Idempotent (re-registering replaces)."""
    if not backend.name:
        raise ValueError("Backend.name must be set before register_backend()")
    _REGISTRY[backend.name] = backend
    return backend


def unregister_backend(name: str) -> None:
    _REGISTRY.pop(name, None)


def get_backend(name: str) -> Optional[Backend]:
    return _REGISTRY.get(name)


def all_backends() -> list[Backend]:
    """Stable order: insertion order."""
    return list(_REGISTRY.values())
