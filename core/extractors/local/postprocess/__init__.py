"""Post-processing: verify OCR output against pdfplumber text.

For text-based PDFs, the same file has lossless pdfplumber text. We
cross-check the OCR'd ParsedInvoice against pdfplumber text and fix
discrepancies. This is the safety net for OCR hallucination.

Currently implements:
  - pdf_text_verify:    per-field verification against pdfplumber text

Adding a new post-processor:
  1. Subclass PostProcessor
  2. Implement run(parsed, file_path) -> ParsedInvoice
  3. Add register_post_processor(YourPostProcessor()) at the bottom
"""
from .base import PostProcessor, register_post_processor, get_post_processors  # noqa: F401
from . import pdf_text_verify  # noqa: F401  -- registers the default post-processor
