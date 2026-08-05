# Beijing 财政电子票据 family (cid fonts + stamps)

## What these are

北京市财政电子票据 (Beijing municipal fiscal e-receipts) — e.g. 中央医疗门诊收费票据（电子）
issued by various Beijing hospitals. They share a PDF generation family with two properties that break the usual pipeline.

> **Privacy:** the two tested receipts belong to a private individual; names,
> masked IDs and hospital names in this file are placeholders. Only amounts
> / dates / numbers (non-personal) are kept exact.

## Property 1: custom-encoded fonts (cid glyphs)

Labels render as `(cid:NN)` sequences in pdfplumber text and are NOT recoverable:

```
(cid:50)(cid:38)(cid:16)(cid:45)(cid:8)11060125      ← 票据代码:11060125 (label is cid garbage)
(cid:35)(cid:40)(cid:53)(cid:8)某患者                ← 交款人:某患者
(cid:36)(cid:20)(cid:29)(cid:34)...陆佰零壹元壹角陆分   ← 金额合计（大写）:...
(cid:56)(cid:40)(cid:17)(cid:63)...某医院            ← 收款单位（章）：某医院
```

VALUES are in standard fonts and fully readable. Consequences:
- local-pdf backend returns empty code/number/date/buyer/seller → `has_content` fails → OCR fallback fires (this is **CORRECT** behavior, not a bug)
- Post-processor label-anchored patterns (`票据代码[:：]`, `金额合计...小写`, `收款单位（章）`) also miss because the label itself is cid garbage

## Property 2: stamp (公章) image covers the hospital name

The red 公章 is a raster image placed EXACTLY on top of the hospital name text
(verified: 某医院 text at (96,322); stamp image rect (95.7–150, 305–359.6)).

OCR models see the RENDERED page → the name is under the stamp → they hallucinate:
- DeepSeek-OCR: 某医院 → 北京市医院
- Qwen3-VL: 某医院 → XX大学第一医院 / 某医院 / 大学医院 (varies per run)

pdfplumber reads the TEXT LAYER under the stamp → correct 某医院.

## Working recipe (implemented, verified)

1. OCR (vllm) recovers code/number/date/buyer — the cid labels are visible to the VLM.
2. Post-processor (`pdf_text_verify.py`) overrides seller_name from pdfplumber ground truth:
   - try label `收\s*款\s*单\s*位\s*[（(]章[）)]` if readable
   - else CJK run ending in `医院|保健院|卫生院|服务中心` (skip 综合医院/中医医院/专科医院 type words)
3. Amounts: `_normalize_amount` keeps only `-?\d+(\.\d+)?` — fuzzy match drags `）` from `（小写）94.40` when the label is unreadable.
4. Item names: `无自付/全自付/有自付` are the 报销类型 remark column — legit data, not junk.

## Ground truth for the two tested receipts (sanitized)

> **Privacy**: 身份证 values are SYNTHETIC (synthetic_digits = `(d * 7 + 3) % 10`
> preserving the masked form's shape — no real digits leak).

| Field | 医院A (sanitized) | 妇幼B (sanitized) |
|-------|----------------------|----------------------|
| 票据代码 | 11060125 | 11060125 |
| 票据号码 | 0286781058 | 0130863297 |
| 开票日期 | 2025-12-02 | 2025-07-16 |
| 交款人 | 个人(患者) | 个人(患者) |
| 身份证 | 62**********7750 (synthetic, masked) | 62**********7750 (synthetic, masked) |
| 销售方 | 某医院 | 某区妇幼保健计划生育服务中心 |
| 价税合计 | ¥601.16 | ¥94.40 |
| 医保类型 | 城镇职工 | 自费 |

Note: 妇幼B's pdfplumber text truncates the name at a font boundary
(`...区妇幼 (cid:22)...00136院区`) — the 保健院 part is in another cid font.
The 服务中心-suffix fallback still catches the full 服务中心 name.

## Things that explicitly WORK on Beijing receipts

- **Buyer (交款人) extraction** — OCR handles it because the value is in standard fonts.
- **Money amounts** — totally fine; the 金额合计（小写）¥xxx.00 line is clean.
- **Hospital seller name** — pdfplumber ground truth via the 服务中心-suffix fallback.
- **医保类型, 统筹信息** — extracted normally (the labels are sometimes even readable in the text layer).

## Things that DON'T work

- **Code/number/date from local-pdf** — cid garbage for the LABELS, so we can't extract them. Drop to OCR.
- **Post-processor's pattern-based overrides** — `_RE_INVOICE_CODE = r"票据代码[:：]\s*(\d+)"` fails because pdfplumber emits `(cid:NN)(cid:NN)10...` (no literal label). The post-processor must fall back to fuzzy matching when the label is unreadable.
- **医院 name from OCR** — the stamp occludes it. Always override from pdfplumber.

## See also

- `parser-architecture.md` — Parser/post-processor architecture
- `sanitized-fixture-tests.md` — How to test Beijing-receipt parsers
- `../agents/parser-architecture.md` — Backend ABC + post-process flow
