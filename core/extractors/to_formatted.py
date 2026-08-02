"""Bridge: ParsedInvoice → the app's formatted_data dict shape.

The rest of the app (app/utils.py, app/models.py, templates) consumes the
formatted_data dict produced by InvoiceFormatter.format_invoice_data():

    {
      "基本信息": {...},
      "销售方信息": {...},
      "购买方信息": {...},
      "金额信息": {...},
      "商品信息": [...],
      "其他信息": {...},
    }

Cloud OCR backends (Tencent/Baidu) already produce this via the DocType
layer. Local backends produce a ParsedInvoice — this module converts it
to the same dict so downstream code doesn't care which backend ran.
"""
from __future__ import annotations

from .base import ParsedInvoice


def parsed_to_formatted(parsed: ParsedInvoice) -> dict:
    """Convert a ParsedInvoice into the formatted_data dict shape."""
    return {
        "基本信息": {
            "发票类型": parsed.invoice_type,
            "发票代码": parsed.invoice_code,
            "发票号码": parsed.invoice_number,
            "开票日期": parsed.invoice_date_raw or parsed.invoice_date,
            "开票日期标准格式": parsed.invoice_date,
            "校验码": parsed.check_code,
            "机器编号": parsed.machine_number,
        },
        "销售方信息": {
            "名称": parsed.seller_name,
            "识别号": parsed.seller_tax_id,
            "地址电话": parsed.seller_address,
            "开户行及账号": parsed.seller_bank_info,
        },
        "购买方信息": {
            "名称": parsed.buyer_name,
            "识别号": parsed.buyer_tax_id,
            "地址电话": parsed.buyer_address,
            "开户行及账号": parsed.buyer_bank_info,
        },
        "金额信息": {
            "合计金额": parsed.total_amount,
            "合计税额": parsed.total_tax,
            "价税合计(大写)": parsed.amount_in_words,
            "价税合计(小写)": parsed.amount_in_figures,
        },
        "商品信息": parsed.items,
        "其他信息": {
            "备注": parsed.remarks,
            "开票人": parsed.issuer,
        },
        # Extra data for doc-type-specific rendering (医保信息, 乘车信息, ...)
        "医保信息": parsed.medical_info,
        "乘车信息": parsed.travel_info,
        # Post-processing audit trail
        "OCR后端": parsed.source,
        "后处理修正": parsed.corrections,
        "处理后": parsed.post_processed,
    }
