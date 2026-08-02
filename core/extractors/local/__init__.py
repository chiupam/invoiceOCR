"""Local backend: text+bbox OCR engines (vLLM-compatible, pdfplumber, etc).

Unlike cloud backends (Tencent, Baidu), local backends return text+bbox
blocks from the OCR engine. The backend then:

  1. Hands blocks to a per-doc-type Parser (parsers/medical.py, parsers/vat.py)
     which finds field labels and extracts structured values.
  2. For text-based PDFs, runs PostProcessor (postprocess/pdf_text_verify.py)
     which uses pdfplumber's lossless text to double-check OCR output and
     correct any hallucinated fields.

The LocalBackend ABC handles the dispatch boilerplate so subclasses
(VLLM-compatible OCR like SiliconFlow / Ollama / local vLLM, pure
pdfplumber, etc.) only need to implement `_call_ocr()` which returns the
raw OCR output.
"""
from .base import LocalBackend, pdf_to_blocks  # noqa: F401
from . import vllm  # noqa: F401  -- registers "siliconflow", "ollama", "vllm" backends
from . import pdfplumber  # noqa: F401  -- registers "local" backend
from . import parsers  # noqa: F401  -- registers parsers
from . import postprocess  # noqa: F401  -- registers post-processors
