"""Local pdfplumber backend: pure text extraction (no OCR).

For machine-generated PDFs, pdfplumber extracts the embedded text
losslessly. This backend skips the OCR call entirely:

  - Fast (ms, not seconds)
  - Free
  - No hallucination risk (no generative model)
  - The post-processing step is a no-op here (pdfplumber IS the source)

Use `backend='local'` when the input is a machine-generated PDF.
Use `backend='siliconflow'` for paper scans / phone photos (needs OCR).
"""
from __future__ import annotations

import logging

from ..base import ParsedInvoice, register_backend
from .base import LocalBackend, pdf_to_blocks

logger = logging.getLogger(__name__)


class LocalPdfBackend(LocalBackend):
    """Text extraction via pdfplumber — no OCR involved.

    Only works on machine-generated (text-based) PDFs. Paper scans /
    photos have no embedded text and must use an OCR backend (vllm,
    tencent).

    This backend is used automatically by the app as a first-pass for
    PDF uploads (see app/utils.py process_invoice_image). Users don't
    normally pick it directly — it's the free+fast path that fires when
    the file is a text-based PDF.
    """

    name = "local-pdf"
    display_name = "本地PDF文本提取 (pdfplumber)"

    def is_available(self) -> bool:
        try:
            import pdfplumber  # noqa: F401
            return True
        except ImportError:
            return False

    def _call_ocr(self, file_path: str):
        """pdfplumber isn't OCR — extract text+bbox blocks directly."""
        return pdf_to_blocks(file_path)

    def _should_post_process(self, file_path: str) -> bool:
        # pdfplumber IS the ground truth; nothing to cross-validate.
        return False


# Register on import
register_backend(LocalPdfBackend())
