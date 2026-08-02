"""Cloud OCR backends: structured-data OCR services (Tencent, Baidu, ...).

Unlike local backends, cloud OCR services return structured fields
directly (Name/Value pairs). The Tencent backend wraps the pre-existing
OCRClient + DocType layer and converts its formatted dict into a
ParsedInvoice (via formatted_to_parsed) so it fits the backend contract.
"""
from . import tencent  # noqa: F401  -- registers "tencent" backend
