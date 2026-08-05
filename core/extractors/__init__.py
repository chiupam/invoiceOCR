"""extractors package: OCR backends that produce a ParsedInvoice.

Backends are pluggable. Each backend extracts structured data from a
file (PDF or image) and returns a ParsedInvoice. There are two flavours:

  - CloudBackend (Tencent, Baidu, Aliyun, ...): server returns structured
    Name/Value pairs. The backend's job is to map those into ParsedInvoice.

  - LocalBackend (pdfplumber for text PDFs, DeepSeek-OCR for scans,
    etc.): returns text+bbox blocks. The backend invokes a layout parser
    to turn blocks into ParsedInvoice. For text-based PDFs, post-processing
    cross-validates against pdfplumber's lossless text.

The ParsedInvoice contract is the same for both — DocType.format() in
core/invoice_formatter.py consumes it and produces the app's UI sections.

Backends register themselves via register_backend() at module import time.
"""
from .base import (  # noqa: F401
    Backend,
    TextBlock,
    ParsedInvoice,
    register_backend,
    unregister_backend,
    get_backend,
    all_backends,
)

# Eager-register built-in backends (siliconflow, etc.)
from . import local  # noqa: F401
from . import cloud  # noqa: F401
