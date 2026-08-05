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

# Dense lines on medical receipts pack multiple labels together
# ("医疗机构类型：综合医院医保类型：普通"). Each value must stop at the
# NEXT label. Rather than per-field \S+ regexes, define a helper that
# splits a text on a sequence of known labels.
_MED_LABELS = [
    "医疗机构类型", "医保类型", "医保编号", "性别", "医保统筹基金支付",
    "其他支付", "个人账户支付", "个人现金支付", "个人自付", "个人自费",
]


def _med_field(text: str, label: str) -> str:
    """Extract the value for `label` from a dense medical-info block.

    The value runs from after `label:` until the next known label (or
    end of line/block). This handles lines like
    '医疗机构类型：综合医院医保类型：普通' correctly.
    """
    import re as _re
    start = text.find(label)
    if start < 0:
        return ""
    rest = text[start + len(label):]
    rest = _re.sub(r"^\s*[:：]?\s*", "", rest)
    # Find the earliest next label OR end of line
    stops = [rest.find(nl) for nl in _MED_LABELS if nl != label and rest.find(nl) >= 0]
    stops = [s for s in stops if s >= 0]
    newline_pos = rest.find("\n")
    if newline_pos >= 0:
        stops.append(newline_pos)
    if stops:
        rest = rest[:min(stops)]
    # Clean whitespace/newlines and stray box chars (他/信/息 are the
    # vertical-text padding characters on some receipts)
    rest = rest.replace("他", "").replace("信", "").replace("息", "").strip()
    return rest


_RE_HOSPITAL = re.compile(r"医疗机构类型[:：]\s*([^医\s][^保]*)")
_RE_INSURANCE = re.compile(r"医保类型[:：]\s*([^医][^保][^编]*)")
_RE_INSURANCE_ID = re.compile(r"医保编号[:：]\s*([^性别]*)")
_RE_GENDER = re.compile(r"性别[:：]\s*([^医保]*)")
_RE_FUND_PAY = re.compile(r"医保统筹基金支付[:：]\s*([^其]*)")
_RE_OTHER_PAY = re.compile(r"其他支付[:：]\s*([^个]*)")
_RE_ACCOUNT_PAY = re.compile(r"个人账户支付[:：]\s*([^个]*)")
_RE_CASH_PAY = re.compile(r"个人现金支付[:：]\s*([^个]*)")
_RE_SELF_PAY = re.compile(r"个人自付[:：]\s*([^个]*)")
_RE_SELF_EXP = re.compile(r"个人自费[:：]\s*([^\n]*)")

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
        # Standalone buyer_name fallback (Qwen/clean OCR output puts
        # 交款人 and 开票日期 on separate lines).
        if not parsed.buyer_name:
            m = re.search(r"交款人[:：]\s*(\S+)", text)
            if m:
                parsed.buyer_name = m.group(1).strip()
        # Seller = the hospital. Two label variants:
        #   收款单位（章）：某医院   (pdfplumber dense)
        #   ...某医院                       (Qwen/clean OCR, bare name
        #   near the 医保交易流水号 footer)
        if not parsed.seller_name:
            m = re.search(
                r"收款单位\s*[（(]章[）)]\s*[:：]?\s*([\u4e00-\u9fff·（）()]+)",
                text,
            )
            if m:
                parsed.seller_name = m.group(1).strip()
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
        for label, target in [
            ("医疗机构类型", "医疗机构类型"),
            ("医保类型", "医保类型"),
            ("医保编号", "医保编号"),
            ("性别", "性别"),
            ("医保统筹基金支付", "医保统筹基金支付"),
            ("其他支付", "其他支付"),
            ("个人账户支付", "个人账户支付"),
            ("个人现金支付", "个人现金支付"),
            ("个人自付", "个人自付"),
            ("个人自费", "个人自费"),
        ]:
            if label not in med:
                val = _med_field(text, label)
                if val:
                    med[target] = val

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
        # Find start (header has 项目名称) and end (金额合计 total row).
        # The full-width DETAIL table has a 数量/单位 header (quantity
        # column). Page 0 may contain a narrower 3-column SUMMARY table
        # (项目名称/金额/备注) — skip it and anchor on the detail table's
        # header row instead.
        start_idx = None
        end_idx = None
        header_y = None
        for i, b in enumerate(blocks):
            if b.text == "数量/单位":
                # This header only exists in the full-width detail table.
                header_y = b.bbox[1]
                break
        for i, b in enumerate(blocks):
            if start_idx is None and b.text == "项目名称":
                if header_y is not None and abs(b.bbox[1] - header_y) > 4.0:
                    continue  # not the detail-table header row
                start_idx = i
            if start_idx is not None and "金额合计" in b.text:
                # 金额合计（大写）... is the total row — END of items.
                # Only stop at a 金额合计 on a LATER page (the summary
                # table on page 0 has one too — but we anchored start on
                # the detail table, so this is the detail table's total).
                if b.page >= (blocks[start_idx].page):
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

        # Group by (page, y-bin): the same Y on different pages must NOT
        # merge (multi-page receipts repeat the table layout per page).
        lines: dict[tuple[int, int], list] = {}
        for b in item_blocks:
            y = int(b.bbox[1] / 4.0)
            lines.setdefault((b.page, y), []).append(b)

        # Detect column split from the DETAIL table's own header row only.
        # (The page-0 3-column SUMMARY table has its own headers that
        # would pollute the X analysis — exclude it by anchoring on the
        # header row that contains 数量/单位.)
        mid_x = None
        if header_y is not None:
            # Restrict to the SAME page as header_y — multi-page receipts
            # repeat the header row on each page and cross-page blocks
            # would inflate the count and produce a bogus mid_x.
            header_page = None
            for b in blocks:
                if b.text == "数量/单位" and abs(b.bbox[1] - header_y) <= 4.0:
                    header_page = b.page
                    break
            header_blocks = [
                b for b in blocks
                if b.text in ("项目名称", "数量/单位", "金额（元）", "备注")
                and abs(b.bbox[1] - header_y) <= 4.0
                and (header_page is None or b.page == header_page)
            ]
            if len(header_blocks) >= 8:
                hxs = sorted(b.bbox[0] for b in header_blocks)
                gap = hxs[4] - hxs[3]
                if gap > 30:
                    mid_x = (hxs[3] + hxs[4]) / 2

        def _split_row(ws: list) -> list[tuple[float, list]]:
            """Split a row's words into left/right groups by mid_x."""
            if mid_x is None:
                return [(0.0, ws)]
            left = [w for w in ws if w.bbox[0] < mid_x]
            right = [w for w in ws if w.bbox[0] >= mid_x]
            groups = []
            if left:
                groups.append((0.0, left))
            if right:
                groups.append((mid_x, right))
            return groups

        items = []
        for key in sorted(lines.keys()):
            ws = sorted(lines[key], key=lambda b: b.bbox[0])
            for _, group in _split_row(ws):
                text = "".join(w.text for w in group)
                # Skip total rows: 合计 / 金额合计 (the detail-table total
                # row says just 合计; the page-0 summary says 金额合计).
                if "合计" in text:
                    continue
                # Find amount (last decimal in the group)
                amounts = _RE_AMOUNT.findall(text)
                if not amounts:
                    continue
                amount = amounts[-1]
                # Name = everything before the first quantity+unit token.
                # Medical units include 日/小时/人次/科/次/床日/每胎/例/个/
                # 套/袋/瓶/支/根/盒/包/片/半小时. The qty is a decimal or
                # integer immediately before the unit. Anything after the
                # qty (amount already stripped, remark like 00全自付) is
                # discarded.
                m_qty = re.search(
                    r"\d+(\.\d+)?\s*(?:日|小时|人次|科/次|床日|床位·日|每胎|半小时|例|个|套|袋|瓶|支|根|盒|包|片|项|次)",
                    text,
                )
                if m_qty:
                    name = text[:m_qty.start()].strip()
                else:
                    name = text
                name = name.replace(amount, " ", 1).strip()
                name = name.strip()
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
