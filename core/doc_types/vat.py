#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""增值税发票 (VAT invoice) document type.

Self-registers as ``"vat"`` on import. This module is the only place that
knows about 增值税发票 specifics; callers go through the registry.

Two invoice subtypes fall under VAT (both share the same Tencent response
shape, differ only in which fields are populated):
  * 增值税专用发票 (special) — seller + buyer info both populated
  * 增值税普通发票 (general) — one side often missing
"""
from __future__ import annotations

import datetime
import logging

from .base import DocType
from . import register

logger = logging.getLogger(__name__)


class VatInvoice(DocType):
    type_id = "vat"
    display_name = "增值税发票"
    ocr_action = "VatInvoiceOCR"

    # --- Detection -----------------------------------------------------------

    def detect_response(self, response_json: dict) -> bool:
        """A VAT response always has Response.VatInvoiceInfos[]."""
        return "VatInvoiceInfos" in response_json.get("Response", {})

    # --- Formatting ----------------------------------------------------------

    def format(self, response_json: dict) -> dict:
        # Look at the 发票类型/发票名称 field to decide whether this is the
        # special (专票) or general (普票) variant. Both branches produce the
        # same output shape — only the field-extraction rules differ.
        invoice_data = self.extract_fields(response_json)

        invoice_type = (
            invoice_data.get("发票类型")
            or invoice_data.get("发票名称")
            or ""
        )
        if not invoice_type:
            invoice_type = "增值税专用发票"

        if "普通发票" in invoice_type:
            invoice_data = self._enrich_general_invoice(invoice_data)
            invoice_type = invoice_data.get("发票类型") or "增值税普通发票"
            logger.info("识别为增值税普通发票")

        items_info = response_json["Response"].get("Items", [])

        formatted = {
            "基本信息": {
                "发票类型": invoice_type,
                "发票代码": invoice_data.get("发票代码", ""),
                "发票号码": self.format_invoice_number(
                    invoice_data.get("发票号码", "")
                ),
                "开票日期": invoice_data.get("开票日期", ""),
                "校验码": invoice_data.get("校验码", ""),
                "机器编号": invoice_data.get("机器编号", ""),
            },
            "销售方信息": {
                "名称": invoice_data.get("销售方名称", ""),
                "识别号": invoice_data.get("销售方识别号", ""),
                "地址电话": invoice_data.get("销售方地址、电话", ""),
                "开户行及账号": invoice_data.get("销售方开户行及账号", ""),
            },
            "购买方信息": {
                "名称": invoice_data.get("购买方名称", ""),
                "识别号": invoice_data.get("购买方识别号", ""),
                "地址电话": invoice_data.get("购买方地址、电话", ""),
                "开户行及账号": invoice_data.get("购买方开户行及账号", ""),
            },
            "金额信息": {
                "合计金额": self.format_amount(invoice_data.get("合计金额", "")),
                "合计税额": self.format_amount(invoice_data.get("合计税额", "")),
                "价税合计(大写)": invoice_data.get("价税合计(大写)", ""),
                "价税合计(小写)": self.format_amount(
                    invoice_data.get("小写金额", "")
                ),
            },
            "商品信息": items_info,
            "其他信息": {
                "备注": invoice_data.get("备注", ""),
                "收款人": invoice_data.get("收款人", ""),
                "复核": invoice_data.get("复核", ""),
                "开票人": invoice_data.get("开票人", ""),
            },
            "处理时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._standardize_date(formatted, invoice_data)
        return formatted

    # --- Extraction ----------------------------------------------------------

    def extract_fields(self, response_json: dict) -> dict[str, str]:
        """Override the default extractor to also handle the long-form 普票
        field-name aliases (``购买方统一社会信用代码/纳税人识别号`` and
        ``销售方统一社会信用代码/纳税人识别号``)."""
        out = super().extract_fields(response_json)
        # Map long-form names → short-form when present (only 普票 uses them)
        renames = {
            "购买方统一社会信用代码/纳税人识别号": "购买方识别号",
            "销售方统一社会信用代码/纳税人识别号": "销售方识别号",
        }
        for long, short in renames.items():
            if long in out and short not in out:
                out[short] = out.pop(long)
        return out

    # --- Helpers (private) ---------------------------------------------------

    def _enrich_general_invoice(self, data: dict) -> dict:
        """Apply 普票-specific fallbacks (code from number, aliases for totals)."""
        # 普票 sometimes omits 合计金额 — fall back to whichever sum field exists.
        if "合计金额" not in data and "金额" in data:
            data["合计金额"] = data["金额"]

        # 普票 sometimes omits 小写金额 — try the sum field aliases.
        if "小写金额" not in data:
            for field in ("价税合计", "总计金额", "总金额", "金额", "价税合计(小写)"):
                if field in data:
                    data["小写金额"] = data[field]
                    break

        # 普票 may not have a separate 发票代码 — derive from the number prefix.
        # ONLY for traditional 普票 (8-digit 发票号码). 数电发票 has a 20-digit
        # 发票号码 and NO 发票代码 — deriving a fake code from its prefix is
        # wrong (issue #11). Guard by number length.
        code, number = data.get("发票代码", ""), data.get("发票号码", "")
        if not code and number and len(number) <= 10:
            code = number[:10]
            logger.info(f"从发票号码中提取发票代码: {code}")
            data["发票代码"] = code
        return data

    @staticmethod
    def _standardize_date(formatted: dict, source: dict) -> None:
        """Add 基本信息.开票日期标准格式 ('YYYY-MM-DD') when possible."""
        try:
            d = source.get("开票日期", "")
            if not d:
                return
            if "年" in d and "月" in d and "日" in d:
                parts: list[str] = []
                cursor = 0
                for sep in ("年", "月", "日"):
                    idx = d.find(sep, cursor)
                    if idx <= 0:
                        return
                    parts.append(d[cursor:idx + 1])
                    cursor = idx + 1
                year = parts[0].replace("年", "")
                month = parts[1].replace("月", "").zfill(2)
                day = parts[2].replace("日", "").zfill(2)
                if len(year) == 2:
                    year = "20" + year
                formatted["基本信息"]["开票日期标准格式"] = f"{year}-{month}-{day}"
            else:
                for sep in ("-", "/", "."):
                    if sep in d:
                        ys = d.split(sep)
                        if len(ys) >= 3:
                            formatted["基本信息"]["开票日期标准格式"] = (
                                f"{ys[0]}-{ys[1].zfill(2)}-{ys[2].zfill(2)}"
                            )
                            return
        except Exception as e:
            logger.warning(f"日期格式化失败: {e}")
            formatted["基本信息"]["开票日期标准格式"] = source.get("开票日期", "")


# Register on import
register(VatInvoice())
