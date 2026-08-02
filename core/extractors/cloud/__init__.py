"""Cloud OCR backends: structured-data OCR services (Tencent, Baidu, etc).

Unlike local backends, cloud OCR services return structured fields
directly (Name/Value pairs) — no layout parser needed. Each backend
maps its vendor's JSON response into ParsedInvoice.

Empty for now — Tencent adapter is being refactored from core/ocr_api.py.
"""
