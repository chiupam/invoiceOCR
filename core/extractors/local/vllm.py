"""VLLM-compatible OCR backend (single backend, env-var configured).

Speaks the OpenAI-compatible `/v1/chat/completions` protocol with an
image+text input. Any server that exposes that endpoint can serve
DeepSeek-OCR (or another VLM OCR model):

  - SiliconFlow (hosted, free tier)   — default endpoint
  - Ollama (local)                    — `VLLM_OCR_ENDPOINT=http://localhost:11434/v1`
  - Local vLLM server                 — `VLLM_OCR_ENDPOINT=http://localhost:8000/v1`
  - llama.cpp / LM Studio              — `VLLM_OCR_ENDPOINT=http://localhost:8080/v1`

Configuration is entirely via env vars — no per-provider presets:

  VLLM_OCR_API_KEY    optional Bearer token (SiliconFlow needs one;
                      Ollama/local vLLM don't)
  VLLM_OCR_MODEL      model name served by the endpoint
                      default: deepseek-ai/DeepSeek-OCR
  VLLM_OCR_ENDPOINT   base URL without /v1 suffix
                      default: https://api.siliconflow.cn/v1

The model returns text regions in grounding format:
  <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>
which we parse into TextBlock list for the layout parsers.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import time

import requests

from ..base import ParsedInvoice, TextBlock, register_backend
from .base import LocalBackend

logger = logging.getLogger(__name__)


class VLLMOCRBackend(LocalBackend):
    """OpenAI-compatible VLM OCR backend (SiliconFlow, Ollama, vLLM, ...)."""

    name = "vllm"
    display_name = "VLM OCR (OpenAI-compatible 后端)"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("VLLM_OCR_API_KEY", "")
        self.model = model or os.environ.get(
            "VLLM_OCR_MODEL", "deepseek-ai/DeepSeek-OCR"
        )
        self.endpoint = endpoint or os.environ.get(
            "VLLM_OCR_ENDPOINT", "https://api.siliconflow.cn/v1"
        )

    def is_available(self) -> bool:
        """True if the endpoint responds to GET /models.

        For Ollama/local vLLM this is a fast sub-second probe.
        For SiliconFlow it requires the API key to be set (else 401).
        """
        if not self.endpoint:
            return False
        # If an API key is configured, require it to be non-empty.
        try:
            resp = requests.get(f"{self.endpoint}/models", timeout=5)
            return resp.status_code < 500
        except Exception:
            return False

    def _call_ocr(self, file_path: str) -> list[TextBlock]:
        if not self.endpoint:
            raise RuntimeError(
                "VLLM OCR endpoint not configured. "
                "Set VLLM_OCR_ENDPOINT or pass endpoint=..."
            )

        # Read file as base64 data URL.
        # PDFs are rendered to PNG first: most VLM servers (Ollama,
        # local vLLM) accept images but NOT raw PDF data URLs.
        # DeepSeek-OCR on SiliconFlow accepts PDFs directly, but the
        # same request works with a rendered first page too — so we
        # always render PDFs to PNG for maximum compatibility.
        ext = file_path.lower().rsplit(".", 1)[-1]
        if ext == "pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                file_bytes = pix.tobytes("png")
                mime = "image/png"
            except ImportError:
                # No fitz — fall back to sending the PDF bytes raw
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                mime = "application/pdf"
        else:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            mime = f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(file_bytes).decode()}"

        # Call the endpoint. Only send Bearer header if we have a key.
        url = f"{self.endpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "<image>\n<|grounding|>OCR this image."},
                    ],
                }
            ],
        }

        logger.info(f"VLLMOCR: POST {url} model={self.model} file={file_path}")
        t0 = time.time()
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        elapsed = time.time() - t0
        logger.info(f"VLLMOCR: response in {elapsed:.1f}s, status={resp.status_code}")

        if resp.status_code != 200:
            raise RuntimeError(
                f"VLLM OCR failed: {resp.status_code} {resp.text[:500]}"
            )

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Delegate output parsing to the model's registered format parser
        # (see ocr_formats.py). New models with new output shapes just
        # register a parser — no backend changes.
        from .ocr_formats import get_format_parser
        parser = get_format_parser(self.model)
        blocks = parser(content)
        logger.info(f"VLLMOCR: parsed {len(blocks)} text blocks (model={self.model})")
        return blocks


# Register on import
register_backend(VLLMOCRBackend())
