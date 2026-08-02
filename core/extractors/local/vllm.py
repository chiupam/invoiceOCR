"""OpenAI-compatible VLM OCR backend.

Works with any service that exposes `/v1/chat/completions` and supports
image+text inputs. Concrete deployments include:

  - SiliconFlow (hosted)  - default endpoint, requires SF_API_KEY
  - Ollama (local)         - http://localhost:11434/v1, no auth, needs
                             the model pulled locally (e.g. `ollama pull
                             deepseek-ocr`)
  - Local vLLM server       - http://localhost:8000/v1, optional auth
  - llama.cpp / LM Studio   - http://localhost:8080/v1 etc.
  - Together.ai, OpenRouter, etc

The DeepSeek-OCR model (`PaddlePaddle/PaddleOCR-VL-1.5` on SiliconFlow,
`deepseek-ocr` on Ollama) is loaded by the configured endpoint. The backend
doesn't care which — it just POSTs to `{endpoint}/v1/chat/completions`.

Why VLLM, not "SiliconFlow":
  The original implementation was named after SiliconFlow as the only
  configured provider. But the protocol is OpenAI-compatible — any
  vLLM-style server works. We keep SiliconFlow as the default endpoint
  for backwards compatibility, but Ollama/local vLLM work without code
  changes.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import time
from typing import Optional

import requests

from ..base import ParsedInvoice, TextBlock, register_backend
from .base import LocalBackend

logger = logging.getLogger(__name__)


# DeepSeek-OCR output format: <|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>
_RE_OCR_RE = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>",
    re.DOTALL,
)


class VLLMOCRBackend(LocalBackend):
    """OpenAI-compatible VLM OCR backend (SiliconFlow, Ollama, vLLM, …)."""

    name = "vllm"
    display_name = "VLM OCR (通用 vLLM 后端)"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ):
        # Back-compat: SF_* env vars still work.
        self.api_key = (
            api_key
            or os.environ.get("VLLM_OCR_API_KEY")
            or os.environ.get("SF_API_KEY")
            or ""
        )
        self.model = (
            model
            or os.environ.get("VLLM_OCR_MODEL")
            or os.environ.get("SF_OCR_MODEL")
            or "deepseek-ai/DeepSeek-OCR"
        )
        self.endpoint = (
            endpoint
            or os.environ.get("VLLM_OCR_ENDPOINT")
            or os.environ.get("SF_OCR_ENDPOINT")
            or "https://api.siliconflow.cn/v1"
        )

    def is_available(self) -> bool:
        # Ollama + local vLLM typically don't require auth; we treat
        # them as available if the endpoint responds.
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

        # Read file as base64 data URL
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        ext = file_path.lower().rsplit(".", 1)[-1]
        mime = "application/pdf" if ext == "pdf" else f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(file_bytes).decode()}"

        # Call the endpoint. Most vLLM servers don't require auth;
        # only send the Bearer header if we have a key.
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

        blocks = []
        for m in _RE_OCR_RE.finditer(content):
            text = m.group(1).strip()
            x0, y0, x1, y1 = map(int, m.groups()[1:5])
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    bbox=(x0, y0, x1, y1),
                    confidence=1.0,
                )
            )
        logger.info(f"VLLMOCR: parsed {len(blocks)} text blocks")
        return blocks


# Preset for Ollama (no key, localhost endpoint, model name differs)
class OllamaOCRBackend(VLLMOCRBackend):
    """Pre-configured for local Ollama serving DeepSeek-OCR.

    Default: http://localhost:11434/v1, model `deepseek-ocr`.
    No API key required.
    """

    name = "ollama"
    display_name = "本地 Ollama (DeepSeek-OCR)"

    def __init__(self, endpoint: str | None = None, model: str | None = None):
        super().__init__(
            api_key="",  # Ollama doesn't require auth
            model=model or os.environ.get("OLLAMA_OCR_MODEL", "deepseek-ocr"),
            endpoint=endpoint or os.environ.get(
                "OLLAMA_OCR_ENDPOINT", "http://localhost:11434/v1"
            ),
        )

    def is_available(self) -> bool:
        # Ollama only needs the endpoint to respond
        try:
            resp = requests.get(
                f"{self.endpoint}/models",
                timeout=2,
            )
            return resp.status_code < 500
        except Exception:
            return False


# Register on import. The `siliconflow` name is kept for backwards compat
# — it points at the same VLLMOCRBackend class with default SiliconFlow
# endpoint.
_siliconflow_default = VLLMOCRBackend()
_siliconflow_default.name = "siliconflow"
_siliconflow_default.display_name = "SiliconFlow (DeepSeek-OCR)"
register_backend(_siliconflow_default)
register_backend(OllamaOCRBackend())
register_backend(VLLMOCRBackend())  # `vllm` for any other endpoint
