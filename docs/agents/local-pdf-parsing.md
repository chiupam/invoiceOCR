# Local-pdf parsing pitfalls (text+bbox extraction)

This covers the `local-pdf` backend — pdfplumber text-layer extraction with
word-coordinate layout parsing. These are the layout quirks and traps that
break naive parsers on Chinese invoices. The `local-pdf` backend is ONE of
several OCR backends; see `parser-architecture.md` for the high-level
backend design.

## Layout parsing fundamentals

- `page.extract_words()` → `{text, x0, top, x1, bottom}` — the raw material.
  **`extract_tables()` is useless for borderless modern e-invoices** (no
  ruling lines → each Y-band merges into one giant cell). Hand-rolled word
  clustering is strictly better.
- **Group words into lines by Y-clustering** (walk sorted-by-Y, new line when
  gap > tolerance), NOT Y-binning (`int(y/tol)`). Binning splits words whose
  Y straddles a bin boundary. Group WITHIN each page — never across pages, or
  same-Y rows on different pages merge.
- Join by X with a gap threshold (>30pt gap → space).
- X-coordinate splits side-by-side columns (buyer left / seller right).

## Party-name extraction (buyer/seller)

- **Tax-ID swap bug** — assigning a single non-empty tax_id to buyer when
  buyer is 个人. Fix: dedupe `tax_pairs` by value; sort by X; with 1 pair
  assign to seller only (personal buyers have no tax ID).
- **JD space-split `名 称` (no colon)** — distinct from the 老版2023
  `名 称:` (with colon). Accept both, but cap X-distance when assigning
  values so a left-side label can't grab the right-side value.
- **Party-name label below the value** — label at y+2 with empty colon
  value; always append `(block, value)` even when empty, then find the value
  to the RIGHT of the label (x > label.x), same/adjacent Y.

## Item extraction

- **VAT item amount = 金额, NOT the last decimal** — an item row is
  `名称 单价 数量 金额 税率% 税额`; `amounts[-1]` picks the TAX (wrong). Anchor
  on the `%` word: amount = decimal LEFT of `%`, tax = decimal RIGHT of `%`.
  Same anchor extracts `tax_rate` (`13%`) and `tax`.
- **Quantities are also decimals** (`1.00项`) — split item name at the FIRST
  qty+unit token BEFORE stripping the price amount (only strip the LAST
  decimal).
- **Item name junk** — skip rows containing 合计/价税合计/（大写/（小写; the
  total row may contain 合计 but NOT 金额 (match 合计 alone); filter
  symbol-only names (`￥ ¥` leaks from 价税合计小写).
- **Negative amounts (refunds)** — amount regex must capture a leading minus:
  `(-?[\d,]+\.\d{2})`.
- **`\b` after Chinese units doesn't work** — `\d+(\.\d+)?\s*(?:日|小时|...)`
  with a trailing `\b` silently kills the match (Chinese unit + digit have no
  word boundary in Python re).

## Multi-page tables

- **Group rows by `(page, y)` not `y`** — same Y on different pages merges.
- **Column-split `mid_x` must use header blocks from the SAME page only** —
  repeated headers on each page inflate the count → bogus split.
- **Medical 3-page receipts**: page 0 may be a 3-column SUMMARY table; pages
  1+ are the full-width DETAIL table. Anchor on the detail-table header
  (`数量/单位` — unique to the detail table) to start item extraction at the
  right place. ~107 real detail items; the summary rows must NOT be extracted
  as items.

## Font/encoding quirks

- **Full-width digits** — Chinese PDFs use `２６３...`. Normalize via
  str.maketrans (1:1 aligned; an off-by-one silently mangles ¥→,).
- **Full-width （） vs half-width () parens** — regexes must accept both
  (`[（(]` / `[）)]`).
- **cid custom fonts (北京财政电子票据)** — labels render as `(cid:NN)`
  garbage in pdfplumber text but VALUES are in standard fonts → local-pdf
  fails core fields → OCR fallback required. See
  `beijing-e-invoice-family.md`.
- **Stamps (公章) cover the hospital name** — OCR hallucinates; pdfplumber
  reads the TEXT LAYER under the stamp where the name is intact. Post-process
  overrides OCR with pdfplumber ground truth.

## Amount formatting

- Amounts may have 2-4 decimals + thousands separators (`1,913.76`,
  `1,500.0000`). A `\d{2}`-only amount regex matches the *quantity* `1.00`
  instead of the amount.
- `_normalize_amount` must keep only digits/dot/minus — a fuzzy match can
  drag stray punctuation (`')94.40'` from `（小写）94.40`).
