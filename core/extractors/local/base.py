"""LocalBackend: ABC for text+bbox OCR engines.

Subclasses (SiliconFlow DeepSeek-OCR, future self-hosted vLLM, etc.)
only need to implement `_call_ocr()` which returns a list of TextBlock.
The base class handles:
  - Routing to the right Parser by doc_type
  - Running post-processing if the file is a text-based PDF (pdfplumber can help)
  - The extract() / is_available() interface

To add a new local backend:
  1. Subclass LocalBackend
  2. Implement _call_ocr(file_path) -> list[TextBlock]
  3. Set name + display_name class attributes
  4. Add register_backend(YourBackend()) at the bottom of the module
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from ..base import Backend, ParsedInvoice, TextBlock, register_backend


class LocalBackend(Backend):
    """ABC for OCR engines that return text+bbox blocks.

    Concrete subclasses (siliconflow.py, self_hosted.py) implement
    _call_ocr() to hit the actual OCR service. The base class handles
    parsing + post-processing boilerplate.
    """

    #: Per-doc-type parser registry. Subclasses can override if they
    #: need to customize parsing per backend.
    parsers_module = "core.extractors.local.parsers"

    def extract(self, file_path: str, doc_type: str = "") -> ParsedInvoice:
        """Run OCR on `file_path`, parse to ParsedInvoice, optionally post-process."""
        # 1. Call OCR → text+bbox
        blocks = self._call_ocr(file_path)
        # 2. Parse via per-doc-type parser
        parsed = self._parse(blocks, doc_type, file_path)
        # 3. Post-process if applicable (text-based PDF only)
        if self._should_post_process(file_path):
            parsed = self._post_process(parsed, file_path)
        return parsed

    @abstractmethod
    def _call_ocr(self, file_path: str) -> list[TextBlock]:
        """Hit the OCR service and return text+bbox blocks.

        Subclasses implement this — it's the only OCR-specific code.
        Should return blocks in reading order (top→bottom, left→right)
        with bounding boxes in PDF-point coordinates.
        """

    # ------------------------------------------------------------------
    # Internals — subclasses usually don't override these
    # ------------------------------------------------------------------

    def _parse(self, blocks: list[TextBlock], doc_type: str, file_path: str) -> ParsedInvoice:
        """Route to the right parser for `doc_type`."""
        # Lazy import to avoid circular dependencies
        from .parsers import get_parser
        parser = get_parser(doc_type) if doc_type else None
        if parser is None:
            # No parser registered — return blocks as raw items
            parsed = ParsedInvoice(source=self.name)
            for b in blocks:
                parsed.items.append({
                    "name": b.text,
                    "quantity": "",
                    "unit": "",
                    "unit_price": "",
                    "amount": "",
                    "remark": "",
                })
            return parsed
        return parser.parse(blocks, file_path=file_path)

    def _should_post_process(self, file_path: str) -> bool:
        """True if we have a text-based PDF where pdfplumber can help.

        Paper scans (image PDFs) get skipped because pdfplumber can't
        extract text from them.
        """
        if not file_path.lower().endswith(".pdf"):
            return False
        try:
            # Probe: if pdfplumber extracts >50 chars in the first page,
            # it's a text-based PDF.
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
            return len(text.strip()) > 50
        except Exception:
            return False

    def _post_process(self, parsed: ParsedInvoice, file_path: str) -> ParsedInvoice:
        """Run post-processing on text-based PDFs to verify/correct OCR output."""
        # Lazy import — pdfplumber is only needed at post-process time
        try:
            from .postprocess import get_post_processors
        except ImportError:
            return parsed
        for pp in get_post_processors():
            try:
                parsed = pp.run(parsed, file_path)
            except Exception as e:
                # Don't blow up the whole extraction if post-processing fails
                import logging
                logging.getLogger(__name__).warning(
                    f"PostProcessor {pp.__class__.__name__} failed: {e}"
                )
        return parsed


# ---------------------------------------------------------------------------
# Helper for subclasses
# ---------------------------------------------------------------------------

def pdf_to_blocks(pdf_path: str, min_text_len: int = 1) -> list[TextBlock]:
    """Read a PDF via pdfplumber and return its words as TextBlocks.

    Used by `local/pdfplumber.py` (text-based PDF backend) and by
    `postprocess/pdf_text_verify.py` (cross-validation).
    """
    import pdfplumber
    blocks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            for word in page.extract_words(
                use_text_flow=False, keep_blank_chars=False
            ):
                txt = word.get("text", "").strip()
                if len(txt) < min_text_len:
                    continue
                blocks.append(TextBlock(
                    text=txt,
                    bbox=(word["x0"], word["top"], word["x1"], word["bottom"]),
                    confidence=1.0,  # pdfplumber text is lossless
                    page=page_idx,
                ))
    return blocks
