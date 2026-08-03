"""VAT invoice parser (text+bbox → ParsedInvoice).

Handles 增值税电子普通发票 and 增值税电子专用发票 (and 数电发票 variants).

Recognized fields:
  - 发票号码        invoice_number (no 发票代码 on 数电发票)
  - 开票日期        invoice_date (ISO)
  - 名称 + 统一社会信用代码/纳税人识别号  → seller / buyer
  - 价税合计（大写）/（小写）¥       amount_in_words / amount_in_figures
  - 备注 + 开票人                     remark fields

Items: extracted from the table block (项目名称/单价/数量/金额/税率/税额 or
项目名称/金额 in 数电发票 variants). Refined by pdfplumber post-processing.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ...base import ParsedInvoice, TextBlock
from .base import Parser, register_parser

logger = logging.getLogger(__name__)


# Patterns
_RE_TITLE = re.compile(r"电子发票[（(]普通发票[）)]")
_RE_INVOICE_NUMBER = re.compile(r"发票号码[:：]?\s*(\d+)")
_RE_INVOICE_CODE = re.compile(r"发票代码[:：]?\s*(\d+)")
_RE_INVOICE_DATE = re.compile(r"开票日期[:：]?\s*(\d{4})[年\s-]?(\d{1,2})[月\s-]?(\d{1,2})日?")
_RE_CHECK_CODE = re.compile(r"校验码[:：]?\s*([\d\s]+)")
_RE_MACHINE_NUMBER = re.compile(r"机器编号[:：]?\s*(\d+)")

# Names: many VAT receipts have "名称:xxx" on left and right halves.
# We use X-coordinate to split left (buyer) vs right (seller).
# Patterns below capture either "名称: XXX" or "XXX统一社会信用代码" lines.
_RE_TAX_ID = re.compile(r"(?:统一社会信用代码/纳税人识别号|纳税人识别号)[:：]?\s*([0-9A-Z\*]{10,20})")
_RE_ISSUER = re.compile(r"开票人[:：]\s*(\S+)")

_RE_TOTAL = re.compile(
    r"价税合计\s*[（(]大写[）)]\s*(.+?)\s*[（(]小写[）)]\s*[¥￥]?\s*([\d,]+\.\d{2})"
)

# Date
_RE_DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_RE_DATE_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")

# Monetary
_RE_AMOUNT = re.compile(r"(-?[\d,]+\.\d{2})")


class VatParser(Parser):
    name = "vat"

    def parse(self, blocks: list[TextBlock], file_path: str = "") -> ParsedInvoice:
        parsed = ParsedInvoice(
            source="local:vat",
            invoice_type="增值税电子普通发票",
        )

        # Reconstruct text + bbox-grouped blocks for parsing
        text = self._blocks_to_text(blocks)

        # Title detection
        if _RE_TITLE.search(text):
            parsed.invoice_type = "增值税电子普通发票"

        # Invoice number — search for label + digit
        if not parsed.invoice_number:
            m = _RE_INVOICE_NUMBER.search(text)
            if m:
                parsed.invoice_number = m.group(1)

        # Invoice code (traditional 普票 has 发票代码; 数电发票 doesn't)
        if not parsed.invoice_code:
            m = _RE_INVOICE_CODE.search(text)
            if m:
                parsed.invoice_code = m.group(1)

        # Check code + machine number (traditional layout)
        if not parsed.check_code:
            m = _RE_CHECK_CODE.search(text)
            if m:
                # Old-style check codes have spaces: "58136 09516 34677 86085"
                parsed.check_code = m.group(1).replace(" ", "").strip()
        if not parsed.machine_number:
            m = _RE_MACHINE_NUMBER.search(text)
            if m:
                parsed.machine_number = m.group(1)

        # Date
        if not parsed.invoice_date_raw:
            m = _RE_INVOICE_DATE.search(text)
            if m:
                # Handle "2023 年 11 月15日" (old layout spaces)
                parsed.invoice_date_raw = (
                    f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日"
                )
        parsed.invoice_date = self._normalize_date(parsed.invoice_date_raw)

        # Parties (buyer on left, seller on right at top of invoice)
        self._extract_parties(blocks, parsed)

        # Total amount
        if not parsed.amount_in_figures:
            m = _RE_TOTAL.search(text)
            if m:
                parsed.amount_in_words = m.group(1).strip()
                parsed.amount_in_figures = self._format_amount(m.group(2))

        # Issuer
        if not parsed.issuer:
            m = _RE_ISSUER.search(text)
            if m:
                parsed.issuer = m.group(1)

        # Items (best-effort)
        parsed.items = self._extract_items(blocks)

        return parsed

    # ------------------------------------------------------------------
    # Party extraction (X-coordinate-split)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_parties(blocks: list[TextBlock], parsed: ParsedInvoice) -> None:
        """Extract buyer/seller names + tax IDs.

        Two layouts are possible:
          - OCR merges label+value: '名称：中国联合网络通信有限公司北京市分公司'
          - OCR splits them: '名称' + '中国联合网络通信有限公司北京市分公司'

        We handle both by scanning for blocks that START with 名称 and
        extracting the value after the colon. X-coordinate splits
        buyer (left) from seller (right).
        """
        # Names: blocks containing 名称 label
        name_blocks = []
        for b in blocks:
            t = b.text.strip()
            # Match '名称：XXX' or exactly '名称'
            if t.startswith("名称") and "信息" not in t:
                # Extract value after 名称：
                value = ""
                if "：" in t or ":" in t:
                    value = t.split("：", 1)[-1].split(":", 1)[-1].strip()
                name_blocks.append((b, value))

        # Old-style layout: 名 and 称: are SEPARATE blocks (名 at x=38,
        # 称: at x=82). Detect adjacent 名 + 称: pairs and treat the
        # value as the block to the right of 称:.
        if not name_blocks:
            for i, b in enumerate(blocks):
                if b.text.strip() != "名":
                    continue
                # Look for 称/称: nearby (same row)
                for nb in blocks:
                    if nb is b or not nb.text.strip().startswith("称"):
                        continue
                    if abs(nb.bbox[1] - b.bbox[1]) <= 5.0:
                        # Found the 称: label block; the name value is to
                        # its right on the same row
                        val = ""
                        if ":" in nb.text or "：" in nb.text:
                            val = nb.text.split(":", 1)[-1].split("：", 1)[-1].strip()
                        name_blocks.append((nb, val))
                        break
        # Sort name_blocks by Y so buyer (top) comes before seller (bottom)
        if name_blocks and not any(v for _, v in name_blocks):
            # All values empty → old-style: buyer block is the top one,
            # seller is the bottom one (NOT left/right!)
            name_blocks.sort(key=lambda x: x[0].bbox[1])

        if name_blocks:
            # Sort by X — left is buyer, right is seller
            name_blocks.sort(key=lambda x: x[0].bbox[0])
            if name_blocks[0][1]:
                parsed.buyer_name = name_blocks[0][1]
            if len(name_blocks) >= 2 and name_blocks[1][1]:
                parsed.seller_name = name_blocks[1][1]
            # If value was empty (label only), find the name value in a
            # nearby block — the value may be ABOVE or BELOW the label
            # (this layout puts the name at y=100.6 and 名称： at y=102.7),
            # or on the same row to the right.
            for b, value in name_blocks:
                if not value:
                    best = None
                    best_dist = 999
                    for nb in blocks:
                        if nb is b or not nb.text.strip():
                            continue
                        if nb.text.strip().startswith("统一"):
                            continue
                        if nb.text.strip().startswith("名称"):
                            continue  # skip other labels
                        if "方" in nb.text and len(nb.text) <= 2:
                            continue  # skip 买/售/方/信/息 vertical text
                        # Value is to the RIGHT of the label, same/adjacent row
                        dy = abs(nb.bbox[1] - b.bbox[1])
                        if dy <= 8.0 and nb.bbox[0] > b.bbox[0]:
                            if dy < best_dist:
                                best = nb
                                best_dist = dy
                    if best is None:
                        # Fallback: any nearby block within 10pt Y (to the right)
                        for nb in blocks:
                            if nb is b or not nb.text.strip():
                                continue
                            if nb.text.strip().startswith("统一"):
                                continue
                            if nb.text.strip().startswith("名称"):
                                continue
                            if "方" in nb.text and len(nb.text) <= 2:
                                continue
                            if nb.bbox[0] > b.bbox[0] and abs(nb.bbox[1] - b.bbox[1]) <= 10.0:
                                best = nb
                                break
                    if best:
                        val = best.text.strip()
                        if parsed.buyer_name is None or parsed.buyer_name == "":
                            parsed.buyer_name = val
                        elif parsed.seller_name is None or parsed.seller_name == "":
                            parsed.seller_name = val

        # Tax IDs from 统一社会信用代码/纳税人识别号 labels.
        # Modern 数电发票 has TWO label blocks side-by-side: left (buyer)
        # and right (seller). The right one usually embeds the value
        # within the same text block (e.g. "统一社会信用代码/纳税人识别号
        # :91110302MA01LR25XA"); the left may be empty (个人 has no code)
        # or have a separate value block.
        # Old-style (2023) invoices use plain "纳税人识别号:" labels in
        # top (buyer) and bottom (seller) blocks.
        #
        # Robust strategy: collect all (x, value) pairs where the block
        # has BOTH the label AND a value, plus any (x, value) pair on the
        # SAME ROW as a label block. Sort by X, assign leftmost to buyer
        # and rightmost to seller. If only one pair is found, it could
        # be either side — but on a 数电发票 it's almost always the
        # seller's (the side that has a value), so default to seller.
        tax_pairs: list[tuple[float, str]] = []
        for b in blocks:
            if "统一社会信用代码" not in b.text and "纳税人识别号" not in b.text:
                continue
            # 1. Value within the same block
            m = _RE_TAX_ID.search(b.text)
            if m and m.group(1):
                tax_pairs.append((b.bbox[0], m.group(1)))
            # 2. Value on a nearby block at similar Y (same row, just to
            # the right — for layouts where label and value are separate
            # blocks on the same horizontal line)
            if not m or not m.group(1):
                for nb in blocks:
                    if nb is b or not nb.text.strip():
                        continue
                    if abs(nb.bbox[1] - b.bbox[1]) > 4.0:
                        continue
                    if nb.bbox[0] < b.bbox[0]:
                        continue  # value is to the right of the label
                    # Heuristic: a 18-char alphanumeric (with * allowed) is
                    # a credit code
                    vm = re.match(r"^\s*([0-9A-Z\*]{15,20})\s*$", nb.text)
                    if vm:
                        tax_pairs.append((nb.bbox[0], vm.group(1)))
                        break
        tax_pairs.sort(key=lambda p: p[0])
        if len(tax_pairs) >= 2:
            if not parsed.buyer_tax_id:
                parsed.buyer_tax_id = tax_pairs[0][1]
            if not parsed.seller_tax_id:
                parsed.seller_tax_id = tax_pairs[-1][1]
        elif len(tax_pairs) == 1:
            # Only one tax_id found. If we already have buyer_name=个人
            # (no tax ID expected) and seller_name is set, the single
            # value is the seller's. Otherwise default to seller (safer
            # for B2B invoices).
            x, val = tax_pairs[0]
            if parsed.buyer_name in ("个人", "personal", "Personal"):
                if not parsed.seller_tax_id:
                    parsed.seller_tax_id = val
            else:
                # No way to know for sure — leave both empty rather
                # than risk misassignment
                if not parsed.seller_tax_id:
                    parsed.seller_tax_id = val

    # ------------------------------------------------------------------
    # Items extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_items(blocks: list[TextBlock]) -> list[dict]:
        """Extract line items from the item table.

        Heuristic: split blocks into lines by Y, then for each line that
        contains a positive decimal value, treat the text as one item.
        Multi-column items may merge — this is the limitation that the
        post-processing step is designed to mitigate.
        """
        lines: dict[int, list] = {}
        for b in blocks:
            y = int(b.bbox[1] / 4.0)
            lines.setdefault(y, []).append(b)

        items = []
        for y in sorted(lines.keys()):
            ws = sorted(lines[y], key=lambda b: b.bbox[0])
            text = "".join(w.text for w in ws)
            # Skip header row
            if "项目名称" in text and "金额" in text:
                continue
            # Skip total rows: 合计 / 价税合计 / （大写）…（小写）
            # (The 合计 row may not literally contain 金额, e.g. "合计
            # ¥23.87" or "合计¥ ¥" — match the markers directly.)
            if any(t in text for t in ("合计", "价税合计", "（大写", "（小写", "(大写", "(小写")):
                continue
            # Find the item AMOUNT using word X positions. A VAT item row
            # is: 名称 单价 数量 金额 税率% 税额. The 金额 is the decimal
            # word immediately LEFT of the 税率% word. Grabbing the last
            # decimal would pick the 税额 (wrong) — e.g. "22.15 3% 0.66".
            amount = None
            for i, w in enumerate(ws):
                if "%" in w.text:
                    # Look left for the previous decimal word
                    for j in range(i - 1, -1, -1):
                        m = _RE_AMOUNT.search(ws[j].text)
                        if m:
                            amount = m.group(1)
                            break
                    break
            if amount is None:
                amounts = _RE_AMOUNT.findall(text)
                if not amounts:
                    continue
                amount = amounts[-1]
            name = text
            for a in _RE_AMOUNT.findall(text):
                name = name.replace(a, " ", 1).strip()
            # Skip names that are only currency symbols / whitespace (e.g.
            # a leaked ￥ from the 价税合计（小写）row).
            name_clean = name.replace("¥", "").replace("￥", "").replace(" ", "")
            if not name_clean or len(name_clean) < 2:
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _blocks_to_text(blocks: list[TextBlock]) -> str:
        """Same Y+X grouping as medical parser (proper clustering)."""
        if not blocks:
            return ""
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        bins: list[list] = []
        cur_line: list = []
        cur_y = None
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

        out_lines = []
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


register_parser(VatParser())
