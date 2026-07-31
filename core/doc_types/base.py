#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Document-type plugin contract.

Each registered DocType knows:
  * its OCR API action (Tencent Cloud's identifier)
  * how to detect whether a raw OCR response belongs to it
  * how to format that response into the app's structured dict

Adding a new invoice type (medical, train ticket, OFD, …) means dropping a
new module in this package, subclassing DocType, and calling register() at
import time. No edits to ocr_api.py, invoice_formatter.py, routes.py,
or templates are required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DocType(ABC):
    """Base class for one document type (e.g. VAT invoice, medical receipt)."""

    # --- Identity (must be set by subclass) ----------------------------------

    #: Stable string id used in code, settings, DB column, and CLI args.
    #: Lowercase, no spaces. Used as the value of Invoice.doc_type.
    type_id: str = ""

    #: Human-readable name shown in the UI ("增值税发票", "医疗票据").
    display_name: str = ""

    #: Tencent Cloud OCR API action for this type
    #: ("VatInvoiceOCR", "RecognizeMedicalInvoiceOCR", …).
    ocr_action: str = ""

    # --- Detection -----------------------------------------------------------

    @abstractmethod
    def detect_response(self, response_json: dict) -> bool:
        """Return True if `response_json` looks like this doc type.

        Called after the OCR call returns. The default signature checks
        Response.<key> presence; subclasses override for finer detection
        (e.g. checking a specific Name/Value pair).
        """

    # --- Formatting ----------------------------------------------------------

    @abstractmethod
    def format(self, response_json: dict) -> dict:
        """Convert raw OCR response JSON into the app's structured dict.

        The returned dict must contain at least:
          基本信息: { 发票类型, 发票代码, 发票号码, 开票日期, ... }
          金额信息: { 价税合计(小写), ... }
          商品信息: [ ... ]                # line items
        Doc-type-specific blocks (销售方信息 / 医保信息 / …) may also be added.
        """

    # --- OCR request extras --------------------------------------------------

    def ocr_request_extras(self) -> dict[str, Any]:
        """Extra fields merged into the OCR request payload.

        Default: enable PDF page-1 recognition. Override to add e.g.
        `PdfPageNumber` or type-specific flags.
        """
        return {"IsPdf": True, "PdfPageNumber": 1}

    # --- Field extraction helpers (used by formatters) ----------------------

    def _kv_from_items(self, response_json: dict, items_key: str) -> dict[str, str]:
        """Build a {Name: Value} dict from a Tencent response *Infos array.

        Tencent's responses nest field/value pairs under
        ``Response.<items_key>[].MedicalInvoiceItems[]`` (medical) or
        ``Response.<items_key>[]`` with Name/Value (VAT). This helper handles
        the common VAT shape. Subclasses override for non-standard shapes.
        """
        flat: dict[str, str] = {}
        for item in response_json.get("Response", {}).get(items_key, []):
            if "Name" in item and "Value" in item:
                flat[item["Name"]] = item["Value"]
        return flat
