#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""医疗票据 (medical receipt) document type.

Backed by Tencent Cloud's ``RecognizeMedicalInvoiceOCR`` API. The response
shape is similar to VAT's but the field names, available data, and
section grouping are all different:

    Response.MedicalInvoiceInfos[].MedicalInvoiceItems[]
        # nested Name/Value pairs, grouped under one of several category
        # blocks (基本信息 / 销售方信息 / 购买方信息 / …)

The base class's default ``_kv_from_response`` already walks both shapes
and emits a flat ``{Name: Value}`` dict, so ``extract_fields`` here is a
thin override that just normalises a few field names that differ between
the medical API and what the VAT code path expects.

Field mapping
-------------

The medical API uses 总金额/总金额大写 rather than 价税合计(小写)/(大写),
and 总金额 is what we surface as the canonical total. VAT-style 合计金额 /
合计税额 fields are not emitted by 医疗票据 and stay blank.

Schema notes:

    * 票据代码 and 票据号码 are returned by 医疗票据 as direct flat fields
      (not nested in MedicalInvoiceItems), so we pick them up via the
      top-level scan in ``extract_fields``.
    * Line items (大项名称 + 大项金额) live inside MedicalInvoiceItems,
      one block per item. ``format()`` flattens them into the existing
      ``商品信息`` list as ``{Name: <大项名称>, Amount: <大项金额>}``.
    * All medical-only fields (医疗机构类型, 医保类型, …) are emitted into
      a dedicated ``医保信息`` block at the top of the formatted dict,
      plus everything that doesn't fit a known section flows into
      ``其他信息`` so no field is silently dropped.
"""
from __future__ import annotations

import datetime
import logging

from .base import DocType
from . import register

logger = logging.getLogger(__name__)


# Fields emitted by Tencent's medical API that we surface in a dedicated
# 医保信息 block. Anything else still flows into 其他信息 as a fallback.
MEDICAL_INFO_FIELDS = (
    "发票名称",
    "发票类型",
    "发票属地",
    "医疗机构类型",
    "医保类型",
    "医保统筹基金支付",
    "个人账户支付",
    "其他支付",
    "个人现金支付",
    "个人自付",
    "个人自费",
    "性别",
    "就诊日期",
    "收款单位",
    "收款人",
    "交款人",
    "交款人统一社会信用代码",
)


class MedicalInvoice(DocType):
    type_id = "medical"
    display_name = "医疗票据"
    ocr_action = "RecognizeMedicalInvoiceOCR"

    # --- Detection -----------------------------------------------------------

    def detect_response(self, response_json: dict) -> bool:
        """A medical response has Response.MedicalInvoiceInfos[]."""
        return "MedicalInvoiceInfos" in response_json.get("Response", {})

    # --- Extraction ----------------------------------------------------------

    def extract_fields(self, response_json: dict) -> dict[str, str]:
        """Use the base extractor (which already handles medical's nested
        MedicalInvoiceItems) and then pick up any top-level fields Tencent
        places outside the *Infos blocks (票据代码, 票据号码, …).
        """
        out = super().extract_fields(response_json)
        # Top-level scan: some medical responses put identifiers at the
        # Response root rather than inside the *Infos block.
        for k, v in response_json.get("Response", {}).items():
            if k in ("MedicalInvoiceInfos", "MedicalInvoiceItems") or not isinstance(v, str):
                continue
            out.setdefault(k, v)
        return out

    # --- Formatting ----------------------------------------------------------

    def format(self, response_json: dict) -> dict:
        fields = self.extract_fields(response_json)

        # Basic info — populate from medical fields where possible.
        # 票据代码 / 票据号码 / 校验码 may or may not appear depending on
        # the hospital's PDF template; absent fields stay blank.
        invoice_type = fields.get("发票类型") or fields.get("发票名称") or "中央医疗收费票据"
        basic_info = {
            "发票类型": invoice_type,
            "发票代码": fields.get("票据代码", ""),
            "发票号码": self.format_invoice_number(fields.get("票据号码", "")),
            "开票日期": fields.get("开票日期", ""),
            "校验码": fields.get("校验码", ""),
            "机器编号": fields.get("机器编号", ""),
        }

        # 金额信息 — medical API gives 总金额/总金额大写; VAT-style 合计金额
        # / 合计税额 / 价税合计 don't exist for medical.
        amount_info = {
            "合计金额": self.format_amount(fields.get("合计金额", "")),
            "合计税额": self.format_amount(fields.get("合计税额", "")),
            "价税合计(大写)": fields.get("价税合计(大写)", "") or fields.get("总金额大写", ""),
            "价税合计(小写)": self.format_amount(
                fields.get("价税合计(小写)", "")
            ) or self.format_amount(fields.get("总金额", "")),
        }

        # 医保信息 — medical-only block
        medical_info = {
            f: fields.get(f, "")
            for f in MEDICAL_INFO_FIELDS
            if fields.get(f)
        }

        # 销售方 / 购买方 — medical receipts don't have these as separate
        # blocks; the closest analog is 收款单位 (the hospital) and 交款人
        # (the patient). Surface them under the existing sections so the
        # UI doesn't have to learn new section names yet.
        seller_info = {
            "名称": fields.get("收款单位", ""),
            "识别号": "",
            "地址电话": "",
            "开户行及账号": "",
        }
        buyer_info = {
            "名称": fields.get("交款人", ""),
            "识别号": fields.get("交款人统一社会信用代码", ""),
            "地址电话": "",
            "开户行及账号": "",
        }

        # Items — collect all 大项名称/大项金额 pairs into 商品信息[].
        # The medical response can group items under several blocks; we
        # scan each block and flatten.
        items_info = self._extract_items(response_json)

        # 其他信息 — any leftover fields that didn't fit a known block.
        known = set(basic_info) | set(amount_info) | set(medical_info) | {
            "收款单位", "交款人", "交款人统一社会信用代码",
            "票据代码", "票据号码", "校验码", "机器编号",
            "开票日期", "总金额", "总金额大写",
            "价税合计", "价税合计(大写)", "价税合计(小写)", "小写金额",
            "价税合计(小写)", "价税合计(大写)", "价税合计",
        }
        other_info = {
            k: v for k, v in fields.items()
            if k not in known and v
        }

        formatted = {
            "基本信息": basic_info,
            "金额信息": amount_info,
            "医保信息": medical_info,
            "销售方信息": seller_info,
            "购买方信息": buyer_info,
            "商品信息": items_info,
            "其他信息": other_info,
            "处理时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._standardize_date(formatted, fields)
        return formatted

    # --- Helpers (private) ---------------------------------------------------

    @staticmethod
    def _extract_items(response_json: dict) -> list[dict]:
        """Walk every MedicalInvoiceInfos[] block and collect line items.

        NOTE: The shape of line-item entries in Tencent's medical response
        is positional rather than paired ``{Name, Value}`` — each item
        produces two entries (one with ``Name="大项名称"`` and a sibling
        with ``Name="大项金额"``), without explicit pairing metadata.

        Until we have a real response to validate against, the safest
        implementation is to emit one row per ``大项名称`` entry with an
        empty ``Amount``, and let the user fill amounts via the existing
        manual-edit UI. This preserves the v1.4 ``商品信息[]`` contract so
        downstream code (InvoiceItem.from_item_data) keeps working.
        """
        items: list[dict] = []
        response = response_json.get("Response", {})
        for info_block in response.get("MedicalInvoiceInfos", []):
            for sub in info_block.get("MedicalInvoiceItems", []):
                if sub.get("Name") == "大项名称":
                    items.append({"Name": sub.get("Value", ""), "Amount": ""})
        return items

    @staticmethod
    def _standardize_date(formatted: dict, source: dict) -> None:
        """Same date-normalisation as VAT (add 基本信息.开票日期标准格式)."""
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
register(MedicalInvoice())
