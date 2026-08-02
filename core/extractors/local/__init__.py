"""Local backend: text+bbox OCR engines (pdfplumber, DeepSeek-OCR, etc).

Unlike cloud backends (Tencent, Baidu), local backends return text+bbox
blocks from the OCR engine. The backend then:

  1. Hands blocks to a per-doc-type Parser (parsers/medical.py, parsers/vat.py)
     which finds field labels and extracts structured values.
  2. For text-based PDFs, runs PostProcessor (postprocess/pdf_text_verify.py)
     which uses pdfplumber's lossless text to double-check OCR output and
     correct any hallucinated fields.

The LocalBackend ABC handles the dispatch boilerplate so subclasses
(DeepSeek-OCR via SiliconFlow, local vLLM server, etc.) only need to
implement `_call_ocr()` which returns the raw OCR output.
"""
from .base import LocalBackend, pdf_to_blocks  # noqa: F401
from . import siliconflow  # noqa: F401  -- registers "siliconflow" backend
from . import pdfplumber  # noqa: F401  -- registers "local" backend
from . import parsers  # noqa: F401  -- registers parsers
from . import postprocess  # noqa: F401  -- registers post-processors
