#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""火车票 (train ticket) document type.

Backed by Tencent Cloud's ``TrainTicketOCR`` API. The response is the
simplest of all the supported types — flat top-level keys under
``Response`` (no ``*Infos[]`` arrays):

    Response.TicketNum          编号
    Response.StartStation       出发站
    Response.DestinationStation 到达站
    Response.Date               出发时间
    Response.TrainNum           车次
    Response.Seat               座位号
    Response.Name               姓名
    Response.Price              票价
    Response.SeatCategory       席别
    Response.ID                 身份证号
    Response.SerialNumber       序列号
    Response.AdditionalCost     加收票价
    Response.HandlingFee        手续费
    Response.LegalAmount        大写金额
    Response.TicketStation      售票站
    Response.OriginalPrice      原票价
    Response.InvoiceStyle       发票类型 (火车票/补票/退票凭证)
    Response.IsReceipt          仅供报销 (1/0)

Because the response is already flat, ``extract_fields`` just returns
``Response`` directly (with the RequestId stripped). The format step
maps those keys to the existing 基本信息/金额信息/乘车人信息 sections so
the existing UI templates can render them with no changes.

Train tickets have no concept of a 销售方/购买方 pair (the carrier and
the buyer are implicit in the ticket), so those sections are left
empty and the passenger info goes into its own block.

Train tickets have no line items — ``商品信息`` is always empty.
"""
from __future__ import annotations

import datetime
import logging

from .base import DocType
from . import register

logger = logging.getLogger(__name__)


# Fields Tencent's TrainTicketOCR returns but that aren't useful in the UI
# (RequestId is just the API call ID).
_TRAIN_NOISE_FIELDS = frozenset({"RequestId"})


class TrainTicket(DocType):
    type_id = "train"
    display_name = "火车票"
    ocr_action = "TrainTicketOCR"

    # --- Detection -----------------------------------------------------------

    def detect_response(self, response_json: dict) -> bool:
        """A train-ticket response has TicketNum + TrainNum at the top
        level.

        Note: with the planned upload-form doc-type picker (M3), this
        detection logic becomes a safety net for non-UI callers (CLI
        tools, batch jobs) rather than the primary routing mechanism.
        The user picks the type at upload time → the right OCR endpoint
        gets called → the response shape matches → no detection needed.

        The current implementation requires both TicketNum AND TrainNum
        (the unique combination that no other Tencent endpoint returns).
        """
        response = response_json.get("Response", {})
        return bool(response.get("TicketNum")) and bool(response.get("TrainNum"))

    # --- Extraction ----------------------------------------------------------

    def extract_fields(self, response_json: dict) -> dict[str, str]:
        """Train tickets are already flat — just copy Response minus noise."""
        out: dict[str, str] = {}
        for k, v in response_json.get("Response", {}).items():
            if k in _TRAIN_NOISE_FIELDS or not isinstance(v, (str, int, float)):
                continue
            out[k] = str(v)
        return out

    # --- Formatting ----------------------------------------------------------

    def format(self, response_json: dict) -> dict:
        fields = self.extract_fields(response_json)

        # 基本信息 — direct mappings from Tencent's flat fields
        basic_info = {
            "发票类型": fields.get("InvoiceStyle", "火车票"),
            "发票代码": "",  # 火车票 has no 发票代码
            "发票号码": fields.get("TicketNum", "") or fields.get("SerialNumber", ""),
            "开票日期": fields.get("Date", ""),
            "校验码": "",
            "机器编号": "",
        }

        # 金额信息 — Price is the canonical total. OriginalPrice and
        # AdditionalCost surface when there's a surcharge (补票).
        amount_info = {
            "合计金额": self.format_amount(fields.get("合计金额", "")),
            "合计税额": "",
            "价税合计(大写)": fields.get("LegalAmount", ""),
            "价税合计(小写)": self.format_amount(fields.get("Price", "")),
            "加收票价": self.format_amount(fields.get("AdditionalCost", "")),
            "手续费": self.format_amount(fields.get("HandlingFee", "")),
            "原票价": self.format_amount(fields.get("OriginalPrice", "")),
        }

        # 乘车信息 — train-specific block: from/to, train number, seat, date
        travel_info = {
            "出发站": fields.get("StartStation", ""),
            "到达站": fields.get("DestinationStation", ""),
            "车次": fields.get("TrainNum", ""),
            "出发时间": fields.get("Date", ""),
            "座位号": fields.get("Seat", ""),
            "席别": fields.get("SeatCategory", ""),
            "售票站": fields.get("TicketStation", ""),
        }

        # 乘车人信息 — passenger name + ID, mapped to 购买方 fields so the
        # existing UI templates render something sensible.
        buyer_info = {
            "名称": fields.get("Name", ""),
            "识别号": fields.get("ID", ""),
            "地址电话": "",
            "开户行及账号": "",
        }

        # 其他信息 — ReceiptNumber, IsReceipt, SerialNumber, InvoiceType
        # (the "发票消费类型：交通" marker).
        other_info = {
            k: v
            for k, v in fields.items()
            if k not in {
                "TicketNum", "SerialNumber", "StartStation", "DestinationStation",
                "Date", "TrainNum", "Seat", "Name", "Price", "SeatCategory",
                "ID", "InvoiceType", "AdditionalCost", "HandlingFee",
                "LegalAmount", "TicketStation", "OriginalPrice", "InvoiceStyle",
            }
        }

        # 火车票 has no seller block
        seller_info = {
            "名称": "", "识别号": "", "地址电话": "", "开户行及账号": "",
        }

        formatted = {
            "基本信息": basic_info,
            "金额信息": amount_info,
            "乘车信息": travel_info,
            "销售方信息": seller_info,
            "购买方信息": buyer_info,
            "商品信息": [],  # 火车票 has no line items
            "其他信息": other_info,
            "处理时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._standardize_date(formatted, fields)
        return formatted

    # --- Helpers (private) ---------------------------------------------------

    @staticmethod
    def _standardize_date(formatted: dict, source: dict) -> None:
        """开票日期 on a train ticket is a ``出发时间`` like
        ``2017年12月23日10:33`` — keep the raw value but also expose a
        YYYY-MM-DD form under ``开票日期标准格式`` for sortable lists.
        """
        d = source.get("Date", "")
        if not d:
            return
        try:
            # Try Chinese form first: 2017年12月23日10:33 → 2017-12-23
            if "年" in d and "月" in d and "日" in d:
                year_end = d.find("年")
                month_end = d.find("月")
                day_end = d.find("日")
                year = d[:year_end]
                month = d[year_end + 1 : month_end].zfill(2)
                day = d[month_end + 1 : day_end].zfill(2)
                formatted["基本信息"]["开票日期标准格式"] = f"{year}-{month}-{day}"
                return
            # ISO-like: 2017-12-23T10:33
            for sep in ("-", "/", "."):
                if sep in d:
                    ys = d.split(sep)
                    if len(ys) >= 3:
                        formatted["基本信息"]["开票日期标准格式"] = (
                            f"{ys[0]}-{ys[1].zfill(2)}-{ys[2][:2].zfill(2)}"
                        )
                        return
        except Exception as e:
            logger.warning(f"日期格式化失败: {e}")
        # Fall back to raw value
        formatted["基本信息"]["开票日期标准格式"] = d


# Register on import
register(TrainTicket())
