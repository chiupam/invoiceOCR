#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发票数据格式化（dispatcher）。

Public surface is unchanged from v1.4 — callers still do
``InvoiceFormatter.format_invoice_data(json_string=…)`` and get back the
same structured dict. Internally the call is routed through the
``core.doc_types`` registry so each document type owns its own formatting
rules (see ``core/doc_types/vat.py``).

The legacy free function ``format_invoice_data()`` is preserved for any
external callers (e.g. ``core/ocr_process.py``).
"""
from __future__ import annotations

import json
import logging
import sys

from core.doc_types import detect as _detect, get as _get_type

logger = logging.getLogger(__name__)


class InvoiceFormatter:
    """发票数据格式化（入口类）。

    真正的格式化逻辑由 ``core.doc_types`` 中的各 DocType 实现。
    本类只做调度。
    """

    # Mapping of (Chinese) header name → display label, kept here because
    # it's purely cosmetic and shared across all doc types.
    STANDARD_SECTIONS = (
        "基本信息", "销售方信息", "购买方信息", "金额信息",
        "商品信息", "其他信息",
    )

    @staticmethod
    def format_invoice_data(
        json_file: str | None = None,
        json_string: str | None = None,
        doc_type: str | None = None,
    ) -> dict:
        """将OCR识别的发票数据格式化为更直观的结构。

        Parameters
        ----------
        json_file / json_string:
            原始OCR响应（二选一）。
        doc_type:
            Optional. ``"vat"`` / ``"medical"`` / etc. When omitted, the
            registry's ``detect()`` is asked to identify the type from the
            response shape. Falls back to the registered "vat" type if
            detection fails — preserves v1.4 behaviour where only VAT
            existed.
        """
        # 1. Load JSON
        if json_file:
            with open(json_file, "r", encoding="utf-8") as f:
                response_json = json.load(f)
        elif json_string:
            response_json = json.loads(json_string)
        else:
            raise ValueError("需要提供JSON文件路径或JSON字符串")

        if "Response" not in response_json:
            logger.error("无法找到有效的发票数据")
            return {"error": "无法找到有效的发票数据"}

        # 2. Resolve the DocType to use
        dt: object | None = None
        if doc_type:
            dt = _get_type(doc_type)
            if dt is None:
                logger.warning(f"未注册的 doc_type={doc_type!r}, 尝试自动识别")
        if dt is None:
            dt = _detect(response_json)
        if dt is None:
            # Last-resort fallback: behave like v1.4 (VAT path).
            # If even the VAT type isn't registered, fail loudly — this
            # means the registry is empty (forgot to import core.doc_types).
            dt = _get_type("vat")
            if dt is None:
                raise RuntimeError(
                    "No document types registered. "
                    "Did you forget to `import core.doc_types`?"
                )
            logger.warning("无法识别文档类型, 默认为增值税")

        logger.info(f"使用 doc_type={dt.type_id} ({dt.display_name}) 进行格式化")

        # 3. Delegate
        return dt.format(response_json)

    # ------------------------------------------------------------------
    # Backwards-compatible static helpers. They delegate to the VAT
    # implementation so callers that imported them directly keep working.
    # ------------------------------------------------------------------

    @staticmethod
    def format_invoice_number(number: str) -> str:
        from core.doc_types.vat import VatInvoice
        return VatInvoice.format_invoice_number(number)

    @staticmethod
    def format_amount(amount: str) -> str:
        from core.doc_types.vat import VatInvoice
        return VatInvoice.format_amount(amount)


# 兼容旧代码的自由函数
def format_invoice_data(json_file: str | None = None, json_string: str | None = None) -> dict:
    """为了兼容旧代码，提供与类相同的静态方法。"""
    return InvoiceFormatter.format_invoice_data(json_file=json_file, json_string=json_string)


# ---------------------------------------------------------------------------
# 命令行入口点（保留 v1.4 行为）
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("使用方法: python invoice_formatter.py <json_file>")
        sys.exit(1)
    json_file = sys.argv[1]
    try:
        formatted_data = format_invoice_data(json_file=json_file)
        print(json.dumps(formatted_data, ensure_ascii=False, indent=4))
    except Exception as e:
        print(f"处理发票数据时出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
