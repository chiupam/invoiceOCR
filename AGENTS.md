# invoiceOCR — agent guide

Multi-backend OCR for Chinese invoices: 增值税发票 (VAT), 医疗票据 (medical), 铁路电子客票 (train e-ticket). Multiple pluggable OCR backends (local-pdf / vllm / tencent) converge on one `formatted_data` dict, which is persisted to DB columns + `extra_data` JSON. The frontend never knows which backend ran.

## Quick start

```bash
pip install -r requirements.txt pytest
python3 -m pytest test/     # run the test suite
python3 run.py              # dev server on :5001
```

## Non-negotiable rules

- **No real personal data in the repo.** No real names, tax IDs, ID-card numbers, or invoice numbers in code, fixtures, comments, or docs. Even a "masked" ID leaks region + birthdate. Test fixtures are sanitized block layouts (`test/fixtures/blocks/`) — the PDFs they came from never enter the repo. Real invoices must stay in a gitignored local dir.
- **Test before committing parser changes.** `pytest test/` must pass. For a new layout case, add a sanitized fixture rather than relying on manual document re-runs.
- **Item amounts are the correctness bar; item NAMES are best-effort.** Dense layouts interleave columns; don't chase perfect names at the expense of correct amounts and no junk rows.
- **Verify before claiming.** Check the actual file/DB/endpoint, not your mental model.

## Where the detail lives

| Doc | Covers |
|---|---|
| `docs/agents/parser-architecture.md` | DocType contract, `extra_data` schema, backend design, format registry |
| `docs/agents/local-pdf-parsing.md` | pdfplumber backend: layout parsing, parties, items, multi-page tables, fonts |
| `docs/agents/sanitized-fixture-tests.md` | fixture workflow, sanitizer order, masking gotchas |
| `docs/agents/invoice-layouts.md` | layout families + quirks per doc type |
| `docs/agents/beijing-e-invoice-family.md` | cid-font + stamp receipts |
