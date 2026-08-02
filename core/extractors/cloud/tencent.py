"""Tencent Cloud OCR backend (cloud).

Wraps the pre-existing OCRClient + DocType layer (core/ocr_api.py and
core/invoice_formatter.py, merged upstream in earlier PRs) so Tencent
becomes a proper Backend that returns a ParsedInvoice like the others.

Information preservation: the legacy formatter produces the full
formatted dict (基本信息/销售方/购买方/金额/商品/其他信息/医保信息 +
rich 其他信息 like 业务流水号, 门诊号, 收款单位). We convert that dict
to ParsedInvoice via formatted_to_parsed(), which keeps everything that
doesn't fit a typed field in ParsedInvoice.extra. The reverse bridge
(parsed_to_formatted) merges extra back, so the round-trip is lossless.
"""
from __future__ import annotations

import logging
import os

from ..base import Backend, ParsedInvoice, register_backend
from ..to_formatted import formatted_to_parsed

logger = logging.getLogger(__name__)


class TencentBackend(Backend):
    """腾讯云 OCR — existing cloud path wrapped as a Backend."""

    name = "tencent"
    display_name = "腾讯云 OCR"

    def is_available(self) -> bool:
        # Tencent needs credentials; check env or DB settings.
        if os.environ.get("TENCENT_SECRET_ID") and os.environ.get("TENCENT_SECRET_KEY"):
            return True
        try:
            from flask import current_app
            if current_app:
                from app.models import Settings
                sid = Settings.get_value("TENCENT_SECRET_ID")
                skey = Settings.get_value("TENCENT_SECRET_KEY")
                return bool(sid and skey)
        except Exception:
            pass
        return False

    def extract(self, file_path: str, doc_type: str = "") -> ParsedInvoice:
        """Run Tencent OCR + the legacy DocType formatter, return a ParsedInvoice."""
        from core.ocr_api import OCRClient
        from core.invoice_formatter import InvoiceFormatter

        # 1. Tencent OCR raw JSON
        ocr_api = OCRClient()
        response_json = ocr_api.recognize(image_path=file_path, doc_type=doc_type)

        # 2. Legacy formatter → full formatted dict (no info lost)
        formatted_data = InvoiceFormatter.format_invoice_data(
            json_string=response_json, doc_type=doc_type,
        )

        # 3. Convert to ParsedInvoice, keeping everything in extra
        return formatted_to_parsed(formatted_data, source="tencent")


# Register on import
register_backend(TencentBackend())
