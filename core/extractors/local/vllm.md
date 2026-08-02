# VLLM OCR backend configuration

The `vllm` backend speaks the OpenAI-compatible `/v1/chat/completions`
protocol. Point it at any server that can serve an OCR-capable VLM.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VLLM_OCR_API_KEY` | *(none)* | Bearer token. SiliconFlow needs it; Ollama/local vLLM don't. |
| `VLLM_OCR_MODEL` | `deepseek-ai/DeepSeek-OCR` | Model name served by the endpoint. |
| `VLLM_OCR_ENDPOINT` | `https://api.siliconflow.cn/v1` | Base URL (no `/v1` suffix). |

## Providers / models

### SiliconFlow (hosted, free tier) — recommended

Default configuration — works out of the box with `VLLM_OCR_API_KEY` set.

```bash
export VLLM_OCR_API_KEY=sk-...
# model defaults to deepseek-ai/DeepSeek-OCR
```

DeepSeek-OCR is the recommended default: dedicated OCR model, faithful
transcription with grounding boxes, accepts PDFs directly.

Qwen3-VL-8B is a strong alternative — its output is plain labeled text
(not grounding boxes), which our regex parsers handle cleanly. Slower
(~20-60s/page vs ~5s for DeepSeek-OCR) but more thorough on some layouts.

```bash
export VLLM_OCR_API_KEY=sk-...
export VLLM_OCR_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

Other hosted options (untested): `Qwen/Qwen3-VL-32B-Instruct`,
`Qwen/Qwen3-VL-30B-A3B-Instruct`, `zai-org/GLM-4.5V` (智谱视觉模型).
Note: 智谱 GLM-OCR (dedicated OCR) is NOT hosted on SiliconFlow.

### Ollama (local) — caveat for CPU-only hardware

```bash
ollama pull deepseek-ocr
export VLLM_OCR_ENDPOINT=http://localhost:11434/v1
export VLLM_OCR_MODEL=deepseek-ocr
# no VLLM_OCR_API_KEY needed
```

**Caveat (tested 2026-08-02):** local Ollama OCR on commodity CPU is
unworkable for the 3B DeepSeek-OCR. We tested on a 6-core i7-13620H
with 11GB RAM:

- `deepseek-ocr:latest` (6.7GB GGUF) — Ollama couldn't load it; gave
  up after 8m30s with HTTP 499 "load failed: timed out waiting for
  llama-server to start". The 6.7GB GGUF needs ~8GB just to mmap,
  leaving no room for KV cache on an 11GB host.
- `glm-ocr:latest` (2.2GB, 0.9B) — fits in RAM but the model falls into a
  repetition loop (10K+ chars of `./image.png` / ```skip``` garbage);
  ~5 min per invoice.

A GPU box would make both work, but on CPU-only hardware the hosted
SiliconFlow path (DeepSeek-OCR / Qwen3-VL) is dramatically more reliable.
The Ollama path is documented as an option for users with GPUs.

### Local vLLM server — requires GPU

```bash
# serve DeepSeek-OCR or Qwen3-VL with your own vLLM (needs CUDA/ROCm)
export VLLM_OCR_ENDPOINT=http://localhost:8000/v1
export VLLM_OCR_MODEL=deepseek-ai/DeepSeek-OCR
```

vLLM does not support CPU execution meaningfully. For a self-hosted GPU
box, use vLLM. For a CPU box, use the hosted SiliconFlow path above.

### llama.cpp / LM Studio

```bash
export VLLM_OCR_ENDPOINT=http://localhost:8080/v1
export VLLM_OCR_MODEL=deepseek-ocr-q4
```

## Output format handling

The backend parses two output shapes:

1. **Grounding boxes** (DeepSeek-OCR): `<|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]</|/det|>`
   → parsed into `TextBlock(bbox=...)` for coordinate-aware parsing.

2. **Plain labeled text** (Qwen3-VL, GLM-4.5V, etc.): one field per line
   like `发票号码：26117000001120479318`. These fall back to
   line-based `TextBlock`s (no coordinates) — the regex parsers still
   extract fields correctly since they mostly work on reconstructed text.
