# Project: parser architecture

- **Upstream**: `chiupam/invoiceOCR`

## Architecture

```
app/utils.py  process_invoice_image(): local-pdf auto first-pass → has_content check → fall back to selected OCR backend
core/extractors/
  base.py          # Backend ABC, TextBlock, ParsedInvoice
  to_formatted.py  # ParsedInvoice → formatted_data dict (the REAL contract)
  local/
    pdfplumber.py  # auto-pass, hidden from UI
    vllm.py        # OpenAI-compatible endpoint
    ocr_formats.py  # model-family output-format registry (deepseek grounding / unlimited label / plain text)
    parsers/       # medical.py, vat.py, train.py (per-doc-type)
    postprocess/pdf_text_verify.py  # pdfplumber ground-truth correction
  tencent.py       # legacy path, NOT in registry — keep as-is
```

**The real contract is the formatted dict + DB columns, NOT ParsedInvoice.** Templates read `invoice.invoice_code` etc. (DB columns) and `json_data` section keys (`基本信息`, `销售方信息`, `购买方信息`, `金额信息`, `商品信息`, `其他信息`, `医保信息`, `乘车信息`). Tencent produces the dict directly via `InvoiceFormatter`; new backends produce `ParsedInvoice` → `parsed_to_formatted()`. Both converge on the same dict shape — the frontend never needs to know which backend ran.

## DocType contract

Each registered DocType knows:
- `type_id` — stable string id (`vat` / `medical` / `train`)
- `display_name` — human-readable Chinese name
- `ocr_action` — Tencent API action (`VatInvoiceOCR`, `RecognizeMedicalInvoiceOCR`, `TrainTicketOCR`)
- `detect_response(response_json)` — returns True if the raw response belongs to this type
- `extract_fields(response_json)` / `format(response_json)` — Tencent path
- `extra_section_keys` + `extra_schema_version` + `extra_sections(formatted_data)` — for the new contract

Adding a new invoice type means dropping a new module in `core/doc_types/` and calling `register()` at import time. No edits to `ocr_api.py`, `invoice_formatter.py`, `routes.py`, or templates required.

## extra_data contract

Type-specific sections (医保信息 / 乘车信息) that don't fit fixed columns are persisted to `Invoice.extra_data` as a versioned JSON blob:

```json
{"v": 1, "sections": {"乘车信息": {"车次": "G1234", "出发站": "北京南", ...}}}
```

Three parts (all on the DocType, not magic strings in utils.py):

1. **DocType-declared sections** — `DocType.extra_section_keys` (medical: `("医保信息",)`, train: `("乘车信息",)`, vat: `()`) + `extra_sections(formatted_data)` on the base class. `app/utils.py` calls `dt.extra_sections(formatted_data)` instead of the hardcoded `("医保信息", "乘车信息")` list — adding a new type requires zero utils.py edits.
2. **Schema version** — `DocType.extra_schema_version` (int), wrapped as `{"v": N, "sections": {...}}`. **No back-compat**: medical/train are brand new (no legacy rows), so consumers only read the versioned shape; a bare sections dict is treated as empty.
3. **Canonical field names** — `core/doc_types/sections.py` holds `MEDICAL_SECTION_FIELDS` / `TRAIN_SECTION_FIELDS` (field order + names). Both backend families emit them; the canonical list is the single source of truth.

### Why the contract matters

- `app/utils.py` line 286-292 used to hardcode `for k in ("医保信息", "乘车信息")` — the new DocType contract breaks that magic-string coupling. Adding a new type = declaring its keys, no utils.py edits.
- The Tencent vs local-parsers divergence (local had `电子客票号`/`乘车人`, Tencent had `售票站`) is resolved by the canonical list — each side populates what it recognizes, order is canonical.

## Backend types

### Cloud backend (Tencent — legacy, not in registry)

`TencentOCR` calls `core/ocr_api.py` which dispatches to `DocType.ocr_action` based on `doc_type`. Returns raw JSON. `InvoiceFormatter.format_invoice_data` dispatches to `DocType.format()` which produces the formatted dict directly.

### Local backends (in registry)

- **local-pdf** (`pdfplumber.py`) — auto-fallback on PDFs. Probes pdfplumber text extraction (≥50 chars in first page). Reads text blocks with bbox via `_get_blocks`. The parser dispatch (`get_parser(doc_type)`) selects the per-doc-type parser (`medical.py` / `vat.py` / `train.py`). The parser returns a `ParsedInvoice` which `to_formatted.py` then converts to the formatted dict.
- **vllm** (`vllm.py`) — OpenAI-compatible VLM endpoint. Renders PDF → PNG via PyMuPDF before sending (most servers reject raw PDF data URLs; only SiliconFlow DeepSeek-OCR accepted them). The output format is parsed via `ocr_formats.py` registry (deepseek grounding / unlimited label / plain text) based on model name.

### Why OCR-first is NOT better for text PDFs — keep local-pdf first

Tested: DeepSeek-OCR hallucinates item names (`DMA产` for DNA, `BioWa` for BioGaia, bare `3%` as a name) while pdfplumber gets clean items on the same text-PDFs. Header fields are identical either way. vLLM's only real advantage is scanned/image PDFs where pdfplumber can't extract text — exactly what the fallback already handles. OCR-first would be slower, costlier, and worse.

## Processor ABC contract

```python
class Backend(ABC):
    name: str
    display_name: str
    def extract(self, file_path: str, doc_type: str = "") -> ParsedInvoice: ...
    def is_available(self) -> bool: ...
```

`extract` flow: call `_call_ocr(file_path)` → get `list[TextBlock]` → route to `get_parser(doc_type)` if specified → produce `ParsedInvoice`. If `_should_post_process(file_path)` (text PDF) → run post-processors (pdfplumber ground-truth correction).

`TextBlock` is `text` + `bbox` (x0, top, x1, bottom) + `confidence` + `page` (0-indexed). Coords in PDF points (1pt = 1/72 inch).

`ParsedInvoice` is backend-agnostic. Fields:
- `source` (`pdfplumber` | `siliconflow` | `self_hosted`)
- `invoice_type`, `invoice_code`, `invoice_number`, `invoice_date` (ISO), `invoice_date_raw`
- `total_amount`, `total_tax`, `amount_in_words`, `amount_in_figures`
- `seller_name`, `seller_tax_id`, `seller_address`, `seller_bank_info`
- `buyer_name`, `buyer_tax_id`, `buyer_address`, `buyer_bank_info`
- `issuer`, `remarks`
- `medical_info` (dict), `travel_info` (dict) — type-specific
- `items` (list of `{name, quantity, unit, unit_price, amount, tax_rate, tax, remark}`)
- `post_processed`, `corrections`, `raw` — audit trail

## Output format registry (`ocr_formats.py`)

The output format is keyed by model-name glob (`register_format("deepseek*", parse_deepseek_grounding)` etc.). Default = plain text. The parser for `*unlimited-ocr*` parses `label [bbox]content` lines; for `deepseek*` parses `<|ref|>text<|/ref|><|det|>[[x0,y0,x1,y1]]<|/det|>` grounding. Pick the right parser based on the model name returned by the VLM — you cannot tell from the output alone which format produced it.

## Pitfalls (architecture-related)

- **Tencent legacy path is OUT of the registry** — keep as-is. Don't try to wrap it in `ParsedInvoice` (rejected decision: too invasive, breaks working code).
- **The contract is `formatted_data`**, not `ParsedInvoice`. New backends should produce `ParsedInvoice` → `parsed_to_formatted()` (one converter) → dict. Switching the frontend to read `ParsededInvoice` directly would couple it to the backend shape.
- **DocType requires `display_name` not `type_id` in the UI** — dropdowns show `display_name` only; `type_id` stays as the form value.
- **Output format ≠ model** — the format is identified by name glob, not by behavior. The `*unlimited-ocr` official vs `*unlimited-ocr:*` GGUF distinction is a tag, not a serving choice.
- **Parser/extractor split** — `core/extractors/local/parsers/` is the per-doc-type parser registry. `get_parser(doc_type)` resolves it. Adding a new parser = module + register_parser(). Don't put parser logic in `core/extractors/base.py` (that's the backend ABC, shared).
- **InvoiceItem.from_item_data accepts 3 key styles** — English (`Name`, `Price`), Chinese (`项目名称`, `单价`), and lowercase snake_case (`name`, `price`). Any missing style = silent empty fields. Don't restructure without testing all three.
- **Post-processors must refresh derived fields** — when correcting `invoice_date_raw`, must recompute `invoice_date` (ISO), else DB stores raw date but the detail page shows `-`.
- **The `PYTHONUNBUFFERED=1` flag** in the Dockerfile keeps `process_invoice_image` logs visible in container platforms; otherwise the buffered log dumps after the function returns and you don't see progress.

## How to add a new invoice type

1. `core/doc_types/<new>.py` — define `class Foo(DocType): type_id=..., display_name=..., ocr_action="..."`, implement `detect_response`, `extract_fields`, `format`. Register at import time.
2. (Optional) `core/extractors/local/parsers/<new>.py` for local-pdf fallback — `class FooParser(Parser): name="..."`, implement `parse(blocks, file_path)`. Register.
3. (Optional) `core/doc_types/sections.py` — add canonical field list for `extra_data` section (`FOO_SECTION_FIELDS`).
4. `app/templates/index.html` — dropdown auto-populates from the registry. Done.
5. `app/templates/invoice_detail.html` — type-aware labels use the existing `{% if invoice.doc_type == 'foo' %}` pattern. Add a branch.

No edits to `app/utils.py`, `routes.py`, `invoice_formatter.py`, or `app/__init__.py` required.

## Where the doc types live

- `core/doc_types/base.py` — `DocType` ABC + `extra_sections` + `extra_section_keys` + `extra_schema_version`
- `core/doc_types/vat.py` — `VatInvoice` (invoice_type, 销售方/购买方/金额/商品/其他 sections)
- `core/doc_types/medical.py` — `MedicalInvoice` (overrides: 收款单位 as seller, 医保信息 section)
- `core/doc_types/train.py` — `TrainTicket` (overrides: 乘车人 as buyer, 乘车信息 section)
- `core/doc_types/sections.py` — `MEDICAL_SECTION_FIELDS`, `TRAIN_SECTION_FIELDS`

## Local parsers

- `core/extractors/local/parsers/base.py` — `Parser` ABC, `register_parser()`
- `core/extractors/local/parsers/medical.py` — `MedicalParser` (text+bbox → ParsedInvoice for 二维码电子票)
- `core/extractors/local/parsers/vat.py` — `VatParser` (text+bbox → ParsedInvoice for 增值税)
- `core/extractors/local/parsers/train.py` — `TrainParser` (text+bbox → ParsedInvoice for 铁路电子客票)
- `core/extractors/local/pdfplumber.py` — `LocalPdfBackend` (extracts TextBlocks)
- `core/extractors/local/vllm.py` — `VllmBackend` (OpenAI-compatible)
- `core/extractors/local/postprocess/pdf_text_verify.py` — `PdfTextVerify` (label-anchored re-extraction, overrides seller_name from pdfplumber ground truth for medical)
