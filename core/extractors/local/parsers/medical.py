"""Medical receipt parser (text+bbox → ParsedInvoice).

Format: 中央医疗门诊/住院收费票据（电子）

Recognized fields (regex patterns cover both 中央医疗门诊 and 住院):
  - 票据代码        invoice_code
  - 票据号码        invoice_number
  - 交款人统一社会信用代码  buyer_tax_id
  - 校验码          check_code
  - 交款人          buyer_name
  - 开票日期        invoice_date (ISO)
  - 金额合计（大写）  amount_in_words
  - （小写）        amount_in_figures
  - 医疗机构类型     medical_info["医疗机构类型"]
  - 医保类型        medical_info["医保类型"]
  - 医保编号        medical_info["医保编号"]
  - 性别            medical_info["性别"]
  - 医保统筹基金支付  medical_info["医保统筹基金支付"]
  - 其他支付        medical_info["其他支付"]
  - 个人账户支付     medical_info["个人账户支付"]
  - 个人现金支付     medical_info["个人现金支付"]
  - 个人自付        medical_info["个人自付"]
  - 个人自费        medical_info["个人自费"]

Items: extracted from text regions between the table header row and
合计 row. Each item is a best-effort ({name, quantity, unit, amount})
tuple — manual review recommended for accuracy.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ...base import ParsedInvoice, TextBlock
from .base import Parser, register_parser

logger = logging.getLogger(__name__)


# Patterns
_RE_INVOICE_CODE = re.compile(r"票据代码[:：]\s*(\d+)")
_RE_INVOICE_NUMBER = re.compile(r"票据号码[:：]\s*(\d+)")
_RE_TAX_ID = re.compile(r"交款人统一社会信用代码[:：]\s*([\d\*]+)")
_RE_CHECK_CODE = re.compile(r"校验码[:：]\s*([A-Za-z0-9]+)")
_RE_PAYER_NAME_DATE = re.compile(r"交款人[:：]\s*(\S+?)\s*开票日期[:：]\s*(.+)")

# Parentheses can be full-width （） or half-width () depending on OCR
_P = r"[（(]"   # open paren (either width)
_PC = r"[）)]"  # close paren (either width)

_RE_TOTAL_LINE = re.compile(
    rf"金额合计\s*{_P}大写{_PC}\s*(.+?)\s*{_P}小写{_PC}\s*[¥￥]?\s*([\d,]+\.\d{{2}})"
)

# Some PDFs/OCR split 金额合计（大写）... and （小写）... onto different Y
# lines. This variant tolerates a newline between them.
_RE_TOTAL_LINE_SPLIT = re.compile(
    rf"金额合计\s*{_P}大写{_PC}\s*([^\n]+?)\n\s*{_P}小写{_PC}\s*[¥￥]?\s*([\d,]+\.\d{{2}})"
)

_RE_HOSPITAL = re.compile(r"医疗机构类型[:：]\s*(\S+)")
_RE_INSURANCE = re.compile(r"医保类型[:：]\s*(\S+)")
_RE_INSURANCE_ID = re.compile(r"医保编号[:：]\s*(\S+)")
_RE_GENDER = re.compile(r"性别[:：]\s*(\S+)")
_RE_FUND_PAY = re.compile(r"医保统筹基金支付[:：]\s*(\S+)")
_RE_OTHER_PAY = re.compile(r"其他支付[:：]\s*(\S+)")
_RE_ACCOUNT_PAY = re.compile(r"个人账户支付[:：]\s*(\S+)")
_RE_CASH_PAY = re.compile(r"个人现金支付[:：]\s*(\S+)")
_RE_SELF_PAY = re.compile(r"个人自付[:：]\s*(\S+)")
_RE_SELF_EXP = re.compile(r"个人自费[:：]\s*(\S+)")

# Date: YYYY年MM月DD日 or YYYY-MM-DD
_RE_DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_RE_DATE_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")

# Monetary amount
_RE_AMOUNT = re.compile(r"([\d,]+\.\d{2})")


class MedicalParser(Parser):
    name = "medical"

    def parse(self, blocks: list[TextBlock], file_path: str = "") -> ParsedInvoice:
        parsed = ParsedInvoice(
            source="local:medical",  # rewritten by backend on return
            invoice_type="中央医疗收费票据",
        )

        # Reconstruct text from blocks for regex matching. Block-level
        # scanning catches field labels that span across word boundaries.
        text = self._blocks_to_text(blocks)

        # Top-level identifiers
        for attr, regex in [
            ("invoice_code", _RE_INVOICE_CODE),
            ("invoice_number", _RE_INVOICE_NUMBER),
            ("buyer_tax_id", _RE_TAX_ID),
            ("check_code", _RE_CHECK_CODE),
        ]:
            if not getattr(parsed, attr):
                m = regex.search(text)
                if m:
                    setattr(parsed, attr, m.group(1).strip())

        # Payer name + date (may be on separate lines if PDF word-breaks)
        if not parsed.buyer_name:
            m = _RE_PAYER_NAME_DATE.search(text)
            if m:
                parsed.buyer_name = m.group(1).strip()
                parsed.invoice_date_raw = m.group(2).strip()
        if not parsed.invoice_date_raw:
            # Try standalone date
            m_date = re.search(
                r"开票日期[:：]\s*(\d{4}[年-]\d{1,2}[月-]\d{1,2}日?)", text
            )
            if m_date:
                parsed.invoice_date_raw = m_date.group(1).strip()

        # Total amount — try same-line first, then split-line variant
        if not parsed.amount_in_figures:
            m = _RE_TOTAL_LINE.search(text)
            if m:
                parsed.amount_in_words = m.group(1).strip()
                parsed.amount_in_figures = self._format_amount(m.group(2))
            else:
                m = _RE_TOTAL_LINE_SPLIT.search(text)
                if m:
                    parsed.amount_in_words = m.group(1).strip()
                    parsed.amount_in_figures = self._format_amount(m.group(2))

        # Medical-specific fields
        med = parsed.medical_info
        for label, regex, target in [
            ("hospital_type", _RE_HOSPITAL, "医疗机构类型"),
            ("insurance_type", _RE_INSURANCE, "医保类型"),
            ("insurance_id", _RE_INSURANCE_ID, "医保编号"),
            ("gender", _RE_GENDER, "性别"),
            ("insurance_fund_pay", _RE_FUND_PAY, "医保统筹基金支付"),
            ("other_pay", _RE_OTHER_PAY, "其他支付"),
            ("account_pay", _RE_ACCOUNT_PAY, "个人账户支付"),
            ("cash_pay", _RE_CASH_PAY, "个人现金支付"),
            ("self_pay", _RE_SELF_PAY, "个人自付"),
            ("self_expense", _RE_SELF_EXP, "个人自费"),
        ]:
            if label not in med:
                m = regex.search(text)
                if m:
                    med[target] = m.group(1).strip()

        # Items — best-effort extraction from blocks between header and 合计
        parsed.items = self._extract_items(blocks)

        # Post-processing (date normalization)
        parsed.invoice_date = self._normalize_date(parsed.invoice_date_raw)

        return parsed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _blocks_to_text(blocks: list[TextBlock]) -> str:
        """Reconstruct text from blocks, preserving Y-position grouping.

        Uses proper Y-clustering (not integer binning) so blocks whose
        Y values straddle a bin boundary stay on the same line.
        Blocks are clustered WITHIN each page — never across pages,
        otherwise rows at the same Y on different pages merge.
        """
        if not blocks:
            return ""
        # Group by page first, then cluster by Y within each page
        pages: dict[int, list] = {}
        for b in blocks:
            pages.setdefault(b.page, []).append(b)

        out_lines = []
        for page_idx in sorted(pages.keys()):
            page_blocks = pages[page_idx]
            sorted_blocks = sorted(page_blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
            bins: list[list] = []
            cur_line: list = []
            cur_y: Optional[float] = None
            for b in sorted_blocks:
                if cur_y is None or abs(b.bbox[1] - cur_y) <= 4.0:
                    cur_line.append(b)
                    cur_y = b.bbox[1] if cur_y is None else cur_y
                else:
                    if cur_line:
                        bins.append(sorted(cur_line, key=lambda x: x.bbox[0]))
                    cur_line = [b]
                    cur_y = b.bbox[1]
            if cur_line:
                bins.append(sorted(cur_line, key=lambda x: x.bbox[0]))

            for ws in bins:
                parts = []
                prev_x1 = None
                for i, w in enumerate(ws):
                    if i > 0 and prev_x1 is not None and w.bbox[0] - prev_x1 > 30:
                        parts.append(" ")
                    parts.append(w.text)
                    prev_x1 = w.bbox[2]
                out_lines.append("".join(parts))
        return "\n".join(out_lines)

    @staticmethod
    def _extract_items(blocks: list[TextBlock]) -> list[dict]:
        """Extract line items from the receipt table.

        Strategy:
        1. Find the table header row (contains 项目名称)
        2. Find the 合计 / 金额合计 row (end of items)
        3. Group blocks between them by Y→line
        4. For each line, extract name + amount using regex

        This is best-effort — multi-column items may merge. Post-processing
        cross-validation helps catch OCR errors.
        """
        # Find start (header has 项目名称) and end (合计 line)
        start_idx = None
        end_idx = None
        for i, b in enumerate(blocks):
            if start_idx is None and b.text == "项目名称":
                start_idx = i
            if start_idx is not None and ("合计" in b.text and "金额" not in b.text):
                # Found 合计 (not 金额合计)
                end_idx = i
                break
        if start_idx is None:
            return []
        if end_idx is None:
            end_idx = len(blocks)

        # Group blocks between [start_idx, end_idx] by Y
        item_blocks = blocks[start_idx + 1:end_idx]
        if not item_blocks:
            return []

        lines: dict[int, list] = {}
        for b in item_blocks:
            y = int(b.bbox[1] / 4.0)
            lines.setdefault(y, []).append(b)

        items = []
        for y in sorted(lines.keys()):
            ws = sorted(lines[y], key=lambda b: b.bbox[0])
            text = "".join(w.text for w in ws)
            # Find amount (last decimal in the line)
            amounts = _RE_AMOUNT.findall(text)
            if not amounts:
                continue
            amount = amounts[-1]
            # Strip amount from text to get name
            name = text
            for a in amounts:
                name = name.replace(a, " ", 1).strip()
            if len(name) < 2:
                continue
            items.append({
                "name": name,
                "quantity": "",
                "unit": "",
                "unit_price": "",
                "amount": f"¥{amount}",
                "remark": "",
            })
        return items

    @staticmethod
    def _normalize_date(raw: str) -> str:
        if not raw:
            return ""
        m = _RE_DATE_CN.search(raw)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = _RE_DATE_ISO.search(raw)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return raw

    @staticmethod
    def _format_amount(amount_str: str) -> str:
        m = _RE_AMOUNT.search(amount_str.replace(",", ""))
        if not m:
            return amount_str
        return f"¥{m.group(1)}"


# Register on import
register_parser(MedicalParser())
