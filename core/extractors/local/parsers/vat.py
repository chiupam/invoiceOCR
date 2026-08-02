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
_RE_INVOICE_NUMBER = re.compile(r"发票号码[:：]\s*(\d+)")
_RE_INVOICE_DATE = re.compile(r"开票日期[:：]\s*(\d{4}[年-]\d{1,2}[月-]\d{1,2}日?)")

# Names: many VAT receipts have "名称:xxx" on left and right halves.
# We use X-coordinate to split left (buyer) vs right (seller).
# Patterns below capture either "名称: XXX" or "XXX统一社会信用代码" lines.
_RE_TAX_ID = re.compile(r"统一社会信用代码/纳税人识别号[:：]\s*(\S+)")
_RE_ISSUER = re.compile(r"开票人[:：]\s*(\S+)")

_RE_TOTAL = re.compile(
    r"价税合计\s*[（(]大写[）)]\s*(.+?)\s*[（(]小写[）)]\s*[¥￥]?\s*([\d,]+\.\d{2})"
)

# Date
_RE_DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_RE_DATE_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")

# Monetary
_RE_AMOUNT = re.compile(r"([\d,]+\.\d{2})")


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

        # Date
        if not parsed.invoice_date_raw:
            m = _RE_INVOICE_DATE.search(text)
            if m:
                parsed.invoice_date_raw = m.group(1).strip()
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
                if "：" in t or ":" in t:
                    value = t.split("：", 1)[-1].split(":", 1)[-1].strip()
                    if value:
                        name_blocks.append((b, value))
                else:
                    name_blocks.append((b, ""))

        if name_blocks:
            # Sort by X — left is buyer, right is seller
            name_blocks.sort(key=lambda x: x[0].bbox[0])
            if name_blocks[0][1]:
                parsed.buyer_name = name_blocks[0][1]
            if len(name_blocks) >= 2 and name_blocks[1][1]:
                parsed.seller_name = name_blocks[1][1]
            # If value was empty (label only), find the next block
            for b, value in name_blocks:
                if not value:
                    idx = blocks.index(b)
                    for nb in blocks[idx + 1:]:
                        if nb.text.strip() and not nb.text.strip().startswith("统一"):
                            if parsed.buyer_name is None or parsed.buyer_name == "":
                                parsed.buyer_name = nb.text.strip()
                            elif parsed.seller_name is None or parsed.seller_name == "":
                                parsed.seller_name = nb.text.strip()
                            break

        # Tax IDs from 统一社会信用代码 lines
        tax_ids = []
        for b in blocks:
            if "统一社会信用代码" in b.text:
                m = _RE_TAX_ID.search(b.text)
                if m:
                    tax_ids.append((b, m.group(1)))
        # Sort by X; left = buyer, right = seller
        tax_ids.sort(key=lambda x: x[0].bbox[0])
        if tax_ids:
            if not parsed.buyer_tax_id:
                parsed.buyer_tax_id = tax_ids[0][1]
            if len(tax_ids) >= 2 and not parsed.seller_tax_id:
                parsed.seller_tax_id = tax_ids[1][1]

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
            # Skip total row
            if "合计" in text and "金额" in text:
                continue
            # Skip 价税合计
            if "价税合计" in text:
                continue
            amounts = _RE_AMOUNT.findall(text)
            if not amounts:
                continue
            amount = amounts[-1]
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
