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

### Ollama (local)

```bash
ollama pull frob/unlimited-ocr:q8_0   # community GGUF (works on CPU)
export VLLM_OCR_ENDPOINT=http://localhost:11434/v1
export VLLM_OCR_MODEL=frob/unlimited-ocr:q8_0
# no VLLM_OCR_API_KEY needed
```

**Caveat (tested 2026-08-02):** the Ollama `frob/unlimited-ocr` GGUF is a
**community conversion**, not the official model. It works on CPU
(~22s per invoice, core fields extracted) but is non-deterministic —
the table block sometimes truncates, losing line items.

The **official** Baidu Unlimited-OCR (https://recipes.vllm.ai/baidu/Unlimited-OCR)
is a DeepSeek-OCR-lineage model that emits the same `<|ref|>/<|det|>`
grounding tokens as DeepSeek-OCR — it requires a GPU (≥8GB VRAM) and
the dedicated vLLM image (`vllm/vllm-openai:unlimited-ocr`) with a
custom n-gram logits processor. Our format parser routes it correctly
(`_parse_deepseek`); only the serving hardware is the constraint.

Also tested, both failed on this 11GB CPU-only host:
- `deepseek-ocr:latest` (6.7GB GGUF) — didn't fit, Ollama timed out
  after 8m30s (HTTP 499).
- `glm-ocr:latest` (2.2GB, 0.9B) — fit but repetition loop, ~5min/invoice.

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
