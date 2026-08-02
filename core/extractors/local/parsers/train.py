"""Train ticket / 铁路电子客票 parser (text+bbox → ParsedInvoice).

Handles:
  - 电子发票（铁路电子客票）— the modern digital e-ticket (like the sample)
  - physical 火车票 scans (via OCR backends)

Fields (from the 铁路电子客票 layout):
  - 发票号码        invoice_number (full-width digits, normalized)
  - 开票日期        invoice_date
  - 出发站/到达站    travel_info["出发站"/"到达站"]
  - 车次            travel_info["车次"]
  - 出发时间        travel_info["出发时间"] (date + time)
  - 座位号          travel_info["座位号"]
  - 席别            travel_info["席别"]
  - 票价            amount_in_figures (价税合计)
  - 姓名            buyer_name
  - 身份证号        buyer_tax_id (masked)
  - 电子客票号       travel_info["电子客票号"]
  - 购买方名称/信用代码 seller_name / seller_tax_id

NOTE: full-width digits (２６３...) are normalized to ASCII before regex.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ...base import ParsedInvoice, TextBlock
from .base import Parser, register_parser

logger = logging.getLogger(__name__)


# Full-width → half-width digit/letter normalization
_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９：．￥，－",
    "0123456789:.$,-",
)


def _norm(s: str) -> str:
    """Normalize full-width digits/punct to ASCII (also strips spaces)."""
    return s.translate(_FULLWIDTH).replace(" ", "")


_RE_INVOICE_NUMBER = re.compile(r"发票号码[:：]\s*(\d+)")
_RE_DATE = re.compile(r"开票日期[:：]\s*(\d{4})[年](\d{1,2})[月](\d{1,2})[日]")
_RE_DEPART = re.compile(r"(\d{4})[年](\d{1,2})[月](\d{1,2})[日]\s*(\d{1,2})[:：](\d{2})[开]")
# Price: 票价: <￥>340.50 — the 票价 label and amount may be on separate
# lines. Match either '$340.50' (normalized) or '票价:' followed by digits
# on the SAME line (no newline crossing).
_RE_PRICE = re.compile(r"\$\s*(\d+\.\d{1,2})|票价[:：]?\s*(\d+\.\d{1,2})")
_RE_ID = re.compile(r"(\d{6}\d{4}\*+\d{4})")
_RE_TICKET_NO = re.compile(r"电子客票号[:：]\s*(\d+)")
_RE_BUYER = re.compile(r"购买方名称[:：]\s*([^\s]+)")
_RE_TAX_ID = re.compile(r"统一社会信用代码[:：]\s*(\d{18}|[A-Z0-9]{18})")


class TrainParser(Parser):
    name = "train"

    def parse(self, blocks: list[TextBlock], file_path: str = "") -> ParsedInvoice:
        parsed = ParsedInvoice(
            source="local:train",
            invoice_type="铁路电子客票",
        )

        # Reconstruct text (same Y-clustering as other parsers)
        text = self._blocks_to_text(blocks)

        # Normalize full-width → half-width for digit fields
        norm_text = _norm(text)

        # 发票号码
        m = _RE_INVOICE_NUMBER.search(norm_text)
        if m:
            parsed.invoice_number = m.group(1)

        # 开票日期
        m = _RE_DATE.search(norm_text)
        if m:
            parsed.invoice_date_raw = f"{m.group(1)}年{m.group(2)}月{m.group(3)}日"
            parsed.invoice_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # 票价 → 价税合计(小写)
        m = _RE_PRICE.search(norm_text)
        if m:
            parsed.amount_in_figures = f"¥{m.group(1) or m.group(2)}"
        # 出发/到达站 + 车次 — 站名之间夹着车次 (e.g. "婺源 G9871 厦门")
        # 找包含车次的那一行，取车次前后的中文为出发站/到达站
        m = re.search(r"[GDCZK]\d{1,4}", norm_text)
        if m:
            parsed.travel_info["车次"] = m.group(0)
            # 在原始文本中定位车次所在行
            train_no = m.group(0)
            for line in text.split("\n"):
                if train_no in line:
                    # 车次前的中文 = 出发站，车次后的中文 = 到达站
                    parts = line.split(train_no)
                    if len(parts) == 2:
                        dep = re.search(r"([\u4e00-\u9fff]{2,4})", parts[0])
                        arr = re.search(r"([\u4e00-\u9fff]{2,4})", parts[1])
                        if dep:
                            parsed.travel_info["出发站"] = dep.group(1)
                        if arr:
                            parsed.travel_info["到达站"] = arr.group(1)
                    break

        # 出发时间 (date + HH:MM开)
        m = _RE_DEPART.search(norm_text)
        if m:
            parsed.travel_info["出发时间"] = (
                f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d} "
                f"{m.group(4)}:{m.group(5)}"
            )

        # 座位号 (X车Y号) + 席别
        m = re.search(r"(\d+车\d+[A-Z]?号)", norm_text)
        if m:
            parsed.travel_info["座位号"] = m.group(1)
        m = re.search(r"(商务座|一等座|二等座|硬座|软座|硬卧|软卧|无座)", text)
        if m:
            parsed.travel_info["席别"] = m.group(1)

        # 电子客票号
        m = _RE_TICKET_NO.search(norm_text)
        if m:
            parsed.travel_info["电子客票号"] = m.group(1)

        # 姓名 + 身份证号 — OCR may emit them on the same line
        # ("1309841994****0056 刘佳亮") or on separate adjacent lines.
        lines = text.split("\n")
        for i, line in enumerate(lines):
            norm_line = _norm(line)
            id_match = _RE_ID.search(norm_line)
            if id_match:
                parsed.buyer_tax_id = id_match.group(1)
                # Name after the ID on the same line
                after = norm_line[id_match.end():]
                name_match = re.search(r"([\u4e00-\u9fff]{2,4})", after)
                if not name_match:
                    # Name on an adjacent line (before or after)
                    for j in (i - 1, i + 1):
                        if 0 <= j < len(lines):
                            nm = re.search(
                                r"([\u4e00-\u9fff]{2,4})", lines[j]
                            )
                            if nm:
                                name_match = nm
                                break
                if name_match:
                    parsed.buyer_name = name_match.group(1)
                break

        # 购买方 (company) + 信用代码
        m = _RE_BUYER.search(text)
        if m:
            parsed.seller_name = m.group(1)
        m = _RE_TAX_ID.search(norm_text)
        if m:
            parsed.seller_tax_id = m.group(1)

        return parsed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _blocks_to_text(blocks: list[TextBlock]) -> str:
        if not blocks:
            return ""
        pages: dict[int, list] = {}
        for b in blocks:
            pages.setdefault(b.page, []).append(b)
        out_lines = []
        for page_idx in sorted(pages.keys()):
            page_blocks = pages[page_idx]
            sorted_blocks = sorted(page_blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
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


# Register on import
register_parser(TrainParser())
