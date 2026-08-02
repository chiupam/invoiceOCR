"""Bridge: ParsedInvoice ⇄ the app's formatted_data dict shape.

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

Two directions:

  - parsed_to_formatted(): local backends produce a ParsedInvoice →
    convert to the dict shape for downstream code.

  - formatted_to_parsed(): the legacy Tencent formatter already
    produces the dict. To make Tencent a proper backend (returning a
    ParsedInvoice like the others), we convert the dict back into a
    ParsedInvoice. Anything that doesn't fit a typed field is kept in
    `extra` so the round-trip is lossless.
"""
from __future__ import annotations

from .base import ParsedInvoice


# Keys consumed by parsed_to_formatted / formatted_to_parsed that are
# NOT part of the dict's round-trip payload (they're ParsedInvoice
# metadata, not invoice fields).
_META_KEYS = {"OCR后端", "后处理修正", "处理后"}


def parsed_to_formatted(parsed: ParsedInvoice) -> dict:
    """Convert a ParsedInvoice into the formatted_data dict shape."""
    fmt = {
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
    # Merge the catch-all `extra` back so nothing is lost on round-trip.
    # Top-level extra keys override the defaults above when present
    # (e.g. a richer 其他信息 from the Tencent formatter).
    for k, v in parsed.extra.items():
        fmt[k] = v
    return fmt


def formatted_to_parsed(fmt: dict, source: str = "tencent") -> ParsedInvoice:
    """Convert a formatted_data dict (from InvoiceFormatter) into a
    ParsedInvoice. Used to make the legacy Tencent path a proper backend.

    Everything that doesn't map to a typed ParsedInvoice field is kept
    in `extra` so parsed_to_formatted() reproduces the dict unchanged.
    """
    basic = fmt.get("基本信息", {})
    seller = fmt.get("销售方信息", {})
    buyer = fmt.get("购买方信息", {})
    amount = fmt.get("金额信息", {})
    other = fmt.get("其他信息", {})

    parsed = ParsedInvoice(
        source=source,
        invoice_type=basic.get("发票类型", ""),
        invoice_code=basic.get("发票代码", ""),
        invoice_number=basic.get("发票号码", ""),
        invoice_date_raw=basic.get("开票日期", ""),
        invoice_date=basic.get("开票日期标准格式", ""),
        check_code=basic.get("校验码", ""),
        machine_number=basic.get("机器编号", ""),
        seller_name=seller.get("名称", ""),
        seller_tax_id=seller.get("识别号", ""),
        seller_address=seller.get("地址电话", ""),
        seller_bank_info=seller.get("开户行及账号", ""),
        buyer_name=buyer.get("名称", ""),
        buyer_tax_id=buyer.get("识别号", ""),
        buyer_address=buyer.get("地址电话", ""),
        buyer_bank_info=buyer.get("开户行及账号", ""),
        total_amount=amount.get("合计金额", ""),
        total_tax=amount.get("合计税额", ""),
        amount_in_words=amount.get("价税合计(大写)", ""),
        amount_in_figures=amount.get("价税合计(小写)", ""),
        remarks=other.get("备注", ""),
        issuer=other.get("开票人", ""),
        medical_info=fmt.get("医保信息", {}) or {},
        travel_info=fmt.get("乘车信息", {}) or {},
        items=fmt.get("商品信息", []) or [],
        # corrections/post_processed are not populated by the Tencent
        # formatter (it doesn't run post-processing) — read them back
        # from the dict if present for a faithful round-trip.
        corrections=fmt.get("后处理修正", []) or [],
        post_processed=bool(fmt.get("处理后", False)),
    )

    # Capture everything else into `extra` for lossless round-trip.
    # The rich 其他信息 (业务流水号, 门诊号, 收款单位, ...) is the main
    # content at risk — preserve it wholesale.
    extra = {}
    for k, v in fmt.items():
        if k in _META_KEYS:
            continue
        # Skip sections already consumed into typed fields.
        if k in ("基本信息", "销售方信息", "购买方信息", "金额信息", "商品信息"):
            continue
        if k in ("医保信息", "乘车信息") and v == parsed.medical_info or \
           k in ("乘车信息",) and v == parsed.travel_info:
            # handled above; only keep if non-empty and not duplicated
            pass
        extra[k] = v
    # 其他信息: keep the FULL original (including fields beyond 备注/开票人)
    if fmt.get("其他信息"):
        extra["其他信息"] = fmt.get("其他信息")
    # 处理时间 from the legacy formatter
    if fmt.get("处理时间"):
        extra["处理时间"] = fmt.get("处理时间")

    parsed.extra = extra
    return parsed
