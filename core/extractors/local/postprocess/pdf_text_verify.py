"""PDF text verification post-processor.

When the source file is a text-based PDF (machine-generated), pdfplumber
extracts the text losslessly — it is the GROUND TRUTH. We use it to
override/verify OCR output:

  Strategy (per field with a known label pattern):
    1. Find the label in pdfplumber text (e.g. "票据号码", "发票号码").
    2. Extract the value right after the label.
    3. If found, OVERRIDE the OCR value with pdfplumber's (lossless wins).
    4. If the label isn't found in pdfplumber text, fall back to
       fuzzy-matching the OCR value against the text (edit distance).

This is label-anchored re-extraction — far more reliable than fuzzy
matching the OCR output, which fails when the OCR error is in the
first character (the fuzzy scan anchors on that char).

Limitations:
  - Only helps for text-based PDFs (pdfplumber can extract text).
  - Field labels must be known (we maintain a label→pattern map).
  - Line items are NOT verified here (column layout is too complex);
    they remain best-effort from the parser.
"""
from __future__ import annotations

import logging
import re

from ...base import ParsedInvoice
from .base import PostProcessor, register_post_processor

logger = logging.getLogger(__name__)


# Label → regex that extracts the value following the label.
# These mirror the field patterns in the layout parsers, but applied to
# pdfplumber's clean text (no OCR noise).
_LABEL_PATTERNS = {
    "invoice_code": re.compile(r"票据代码[:：]\s*(\d+)"),
    "invoice_number": re.compile(r"发票号码[:：]\s*(\d+)"),
    "check_code": re.compile(r"校验码[:：]\s*([A-Za-z0-9]+)"),
    "buyer_tax_id": re.compile(r"交款人统一社会信用代码[:：]\s*([\d\*]+)"),
    "invoice_date_raw": re.compile(r"开票日期[:：]\s*(\d{4}[年-]\d{1,2}[月-]\d{1,2}日?)"),
    # Unified amount: 价税合计 (VAT) or 金额合计 (medical), 大写...小写
    # The （小写）close paren can be full/half width; allow it + optional ¥.
    "amount_in_figures": re.compile(
        r"(?:价税合计|金额合计).{0,4}(?:大写).{0,60}(?:小写)[）)]?\s*[¥￥]?\s*([\d,]+\.\d{2})"
    ),
    # Party names: 名称：<value> or space-split "名 称 <value>".
    # Boundary = " 销 "/" 售 " (seller marker) or EOL.
    "buyer_name": re.compile(r"名\s*称\s*[:：]?\s*(.+?)(?=\s+[销售]\s|$)", re.MULTILINE),
    "seller_name": re.compile(r"名\s*称\s*[:：]?\s*(.+?)(?=\s+[销售]\s|$)", re.MULTILINE),
}

# Fields we attempt to verify. Each maps to a label pattern (if known)
# or a fallback edit-distance check.
_VERIFY_FIELDS = [
    "invoice_code",
    "invoice_number",
    "check_code",
    "buyer_tax_id",
    "invoice_date_raw",
    "amount_in_figures",
    "buyer_name",
    "seller_name",
]


class PdfTextVerify(PostProcessor):
    """Cross-validate parsed fields against pdfplumber's lossless text."""

    name = "pdf_text_verify"

    def run(self, parsed: ParsedInvoice, file_path: str) -> ParsedInvoice:
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, skipping post-processing")
            return parsed

        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = "\n".join(
                    (p.extract_text() or "") for p in pdf.pages
                )
        except Exception as e:
            logger.warning(f"PdfTextVerify: failed to extract text: {e}")
            return parsed

        if not full_text.strip():
            return parsed

        for field in _VERIFY_FIELDS:
            ocr_value = getattr(parsed, field, "")

            # Doc-type-aware guard: the VAT-style buyer/seller name
            # pattern (名称：<value>) only makes sense for VAT invoices.
            # For medical receipts, buyer_name comes from 交款人 (payer);
            # for train tickets, from the passenger ID line. Applying the
            # VAT 名称： pattern there grabs the wrong text (item table
            # header, company name, etc.). Only verify names for VAT.
            if field in ("buyer_name", "seller_name") and not (
                "增值税" in parsed.invoice_type
            ):
                continue

            # 1. Try label-anchored extraction from pdfplumber ground truth
            ground_truth = self._extract_from_text(field, full_text)

            # 2. If label not found AND we have an OCR value, try fuzzy
            if ground_truth is None and ocr_value:
                ground_truth = self._find_similar(ocr_value, full_text, max_dist=2)

            if ground_truth is None:
                continue

            # Normalize amount (strip commas, add ¥) and date
            if field == "amount_in_figures":
                ground_truth = _normalize_amount(ground_truth)
            if field == "invoice_date_raw":
                ground_truth = ground_truth.strip()

            # Fill if empty OR correct if different
            if not ocr_value or ground_truth == ocr_value:
                # Empty but filled by ground truth — still counts as processed
                if not ocr_value and ground_truth:
                    setattr(parsed, field, ground_truth)
                    parsed.corrections.append({
                        "field": field,
                        "old": "",
                        "new": ground_truth,
                    })
                    parsed.post_processed = True
                continue

            logger.info(
                f"PdfTextVerify: {field} corrected '{ocr_value}' -> '{ground_truth}'"
            )
            setattr(parsed, field, ground_truth)
            parsed.corrections.append({
                "field": field,
                "old": ocr_value,
                "new": ground_truth,
            })
            parsed.post_processed = True

        return parsed

    @staticmethod
    def _extract_from_text(field: str, full_text: str) -> str | None:
        """Extract the ground-truth value for `field` from pdfplumber text."""
        pattern = _LABEL_PATTERNS.get(field)
        if pattern is None:
            return None
        if field in ("buyer_name", "seller_name"):
            # First match = buyer, second = seller
            matches = pattern.findall(full_text)
            idx = 0 if field == "buyer_name" else 1
            if len(matches) > idx:
                return matches[idx].strip()
            return None
        m = pattern.search(full_text)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _find_similar(value: str, full_text: str, max_dist: int) -> str | None:
        """Fallback: find a substring within `max_dist` edits of `value`.

        Unlike the previous version, this scans ALL positions (not just
        first-char matches) so it works even when the OCR error is in the
        first character. For typical invoice text (<10KB) this is fast
        enough.
        """
        if len(value) < 3:
            return None

        # Prefix recovery: value is a prefix/suffix of a longer token
        for token in re.finditer(r"[\w\u4e00-\u9fff*-]+", full_text):
            t = token.group(0)
            if len(t) > len(value) and t.startswith(value):
                if t[len(value):].isalnum():
                    return t
            if len(t) > len(value) and t.endswith(value):
                if t[:len(t) - len(value)].isalnum():
                    return t

        # Direct substring match
        if value in full_text:
            return value

        # Chinese-heavy values: fuzzy too noisy, give up
        if any('\u4e00' <= c <= '\u9fff' for c in value):
            return None

        # Sliding-window scan over all positions
        best = None
        best_dist = max_dist + 1
        n = len(full_text)
        m = len(value)
        for pos in range(n - m + 1):
            candidate = full_text[pos:pos + m]
            d = _levenshtein(value, candidate, max_dist)
            if d is not None and (d < best_dist or
                                  (d == best_dist and best is not None and
                                   len(candidate) > len(best))):
                best = candidate
                best_dist = d
        # Also try slightly longer candidates (truncation)
        if best is None:
            for pos in range(n - m):
                candidate = full_text[pos:pos + m + 1]
                d = _levenshtein(value, candidate, max_dist)
                if d is not None and (d < best_dist or
                                      (d == best_dist and best is not None and
                                       len(candidate) > len(best))):
                    best = candidate
                    best_dist = d
        if best is not None and best_dist <= max_dist:
            return best
        return None


def _normalize_amount(amount_str: str) -> str:
    """Normalize to ¥X.XX format (strip commas, remove existing ¥/￥)."""
    cleaned = amount_str.replace("¥", "").replace("￥", "").replace(",", "").strip()
    return f"¥{cleaned}"


def _levenshtein(a: str, b: str, max_dist: int) -> int | None:
    """Levenshtein distance with early termination. Returns None if > max_dist."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_dist:
        return None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(
                prev[j] + 1,          # deletion
                cur[j - 1] + 1,       # insertion
                prev[j - 1] + cost,   # substitution
            ))
            row_min = min(row_min, cur[-1])
        if row_min > max_dist:
            return None
        prev = cur
    return prev[-1]


# Register on import
register_post_processor(PdfTextVerify())
