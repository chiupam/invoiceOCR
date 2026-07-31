#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Document-type plugin contract.

Each registered DocType knows:
  * its OCR API action (Tencent Cloud's identifier)
  * how to detect whether a raw OCR response belongs to it
  * how to flatten that response into a ``{field_name: value}`` dict
  * how to format that flat dict into the app's structured sections

Adding a new invoice type (medical, train ticket, OFD, …) means dropping a
new module in this package, subclassing DocType, and calling register() at
import time. No edits to ocr_api.py, invoice_formatter.py, routes.py,
or templates are required.

Why ``extract_fields`` is its own hook
--------------------------------------

Tencent's per-type response shapes vary widely:

    VAT invoice : Response.VatInvoiceInfos[]            (Name/Value pairs)
    Medical     : Response.MedicalInvoiceInfos[].MedicalInvoiceItems[]
                                                          (Name/Value pairs,
                                                           grouped under
                                                           a category block)
    Train ticket: Response.{TicketNum, StartStation, …} (flat top-level keys)

Splitting "flatten the response" out of "map fields to UI sections" lets each
DocType own one well-defined transformation. ``format()`` then becomes pure
field-mapping logic over the flat dict, with no nested-response spelunking.
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

    # --- Field extraction ----------------------------------------------------

    def extract_fields(self, response_json: dict) -> dict[str, str]:
        """Flatten the OCR response into a single ``{field_name: value}`` dict.

        ``format()`` consumes the output of this method. Default implementation
        handles the most common shape — ``Response.<items_key>[]`` with
        ``Name``/``Value`` pairs — and is what the VAT type uses. Subclasses
        with different response shapes (medical's nested
        ``MedicalInvoiceInfos``, train's flat top-level keys, OFD's <yet
        another shape>, …) override this method.
        """
        return self._kv_from_response(response_json)

    def _kv_from_response(
        self, response_json: dict, items_key: str | None = None
    ) -> dict[str, str]:
        """Default extractor: walk ``Response.<items_key>[]`` (or one of the
        known array keys) and collect Name/Value pairs.

        Subclasses normally override ``extract_fields``; this helper exists so
        VAT's ``format()`` keeps a thin implementation.
        """
        response = response_json.get("Response", {})
        if items_key is None:
            # Try every known array key — first one with data wins.
            for k in ("VatInvoiceInfos", "MedicalInvoiceInfos", "Items"):
                if response.get(k):
                    items_key = k
                    break
        if items_key is None:
            return {}

        flat: dict[str, str] = {}
        for item in response.get(items_key, []):
            if not isinstance(item, dict):
                continue
            # VAT shape: item has Name/Value
            if "Name" in item and "Value" in item:
                flat[item["Name"]] = item["Value"]
                continue
            # Medical shape: item has MedicalInvoiceItems[] of Name/Value
            for sub in item.get("MedicalInvoiceItems", []):
                if "Name" in sub and "Value" in sub:
                    flat[sub["Name"]] = sub["Value"]
        return flat

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

    # --- Helpers (used by formatters) ----------------------------------------

    @staticmethod
    def format_invoice_number(number: str) -> str:
        """Strip leading No/No. prefix."""
        if not number:
            return ""
        if number.startswith("No."):
            return number[3:]
        if number.startswith("No"):
            return number[2:]
        return number

    @staticmethod
    def format_amount(amount: str) -> str:
        """Normalize currency prefix (collapse duplicate ¥/￥ into one)."""
        if not amount:
            return ""
        amount = amount.replace("¥", "").replace("￥", "").strip()
        return f"¥{amount}"

