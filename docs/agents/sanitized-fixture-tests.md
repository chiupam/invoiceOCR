# Test infrastructure: sanitized pdfplumber fixtures

## Why this project tests with sanitized block layouts

The parser reads `TextBlock`s (text + bbox) from the PDF text layer — the **shape** is what determines parse quality, not the personal values. So the test suite uses sanitized block layouts (extracted from real invoices, names + tax IDs + IDs masked) instead of real PDFs. The PDFs never enter the repo; the (sanitized) shape does.

**Privacy rule (HARD):** never store real personal data — even a "masked" ID-card number like `xxxxxx19******xxxx` leaks real digits (region + birthdate). Always synthesize ALL digits; keep only the star pattern/shape.

## How fixtures are built

`scripts/extract_fixtures.py` reads each real PDF via `local_pdf._call_ocr(path)`, then sanitizes the text per block:

```python
NAME_MAP = [...]  # real names -> placeholders
TAX_ID_PATTERN = re.compile(r"\b([0-9A-Z]{8})[0-9A-Z*]{10,12}\b")
MASKED_ID_PATTERN = re.compile(r"\b(\d+)(\*+)(\d+)\b")  # protect first
DIGIT_RUN = re.compile(r"(\d{6,})")                      # mask plain digits

def sanitize_text(t):
    for real, fake in NAME_MAP: t = t.replace(real, fake)
    protected = []
    def _synth(m):
        protected.append(m.group(0))
        return f"\x00{len(protected)-1}\x00"
    t = MASKED_ID_PATTERN.sub(_synth, t)       # 1. PROTECT masked IDs
    t = TAX_ID_PATTERN.sub(lambda m: m.group(1) + "*"*(len(m.group(0))-8), t)  # 2. mask tax IDs
    t = DIGIT_RUN.sub(lambda m: mask_digits(m.group(1)), t)  # 3. mask plain digits
    for i, orig in enumerate(protected):
        t = t.replace(f"\x00{i}\x00", synthetic_id(re.match(r"\b(\d+)(\*+)(\d+)\b", orig)))
    return t
```

The sanitized TextBlock list (text + bbox + page + confidence) is saved as `test/fixtures/blocks/<name>.json`. Conftest loads them into `TextBlock` objects and the parser runs unchanged.

## SANITIZER ORDER — the bug that bit me

The `TAX_ID_PATTERN` char class `[0-9A-Z*]` includes `*`, so it can match masked IDs. If TAX_ID runs before MASKED_ID protection, it eats `0436910661****3385` (a synthetic masked ID) → `04369106**********`, destroying the ID shape. The parser's `_RE_ID` regex (`\d{6}\d{4}\*+\d{4}`) no longer matches → passenger-name extraction silently skipped.

**The fix: protect masked IDs FIRST, then mask tax IDs, then plain digit runs.** The placeholder list is restored at the end.

## TF `*.json` is gitignored

`repo .gitignore` has `*.json` to ignore some other data. The fixtures are committed with `git add -f test/fixtures/`.

## Why this approach

- **No PDFs in the repo** — privacy + size. A 3-page inpatient receipt has 658 blocks.
- **Tests exercise real parser code** — the parser consumes the same `TextBlock` shape whether blocks come from real PDFs or sanitized fixtures.
- **Assertions are shape-based** — amounts (correct to the cent), presence (`not empty`), counts (`>= 50`), junk absence (`合计` not in name), buyer/seller shape (`"个人" in buyer_name`). Never exact personal values.
- **Refactor-safe** — change the parser code, fixtures still parse; the test suite catches regressions.

## Test style

```python
def test_vat_personal_buyer_has_no_tax_id():
    parsed = parse_fixture("vat_jd.json", "vat")
    assert "个人" in (parsed.buyer_name or "")
    assert parsed.buyer_tax_id == "", f"buyer_tax_id={parsed.buyer_tax_id!r}"
    assert parsed.seller_tax_id, "seller_tax_id should be set"
```

Shape + presence, not exact values. The test that asserts the buyer is 个人 AND has no tax_id catches the tax-id swap bug — the real assertion is "empty" not "exactly ''".

## Masking gotchas

- **Masked ID synthesis** — must replace ALL digits (not just the middle), keep only the star pattern/shape. Otherwise you leak region + birthdate.
- **Masking `\d{6,}` runs breaks invoice numbers that span blocks** — a 20-digit 数电 number splits into 8+12 digit chunks in separate TextBlocks; each chunk masks differently and the parser only sees the first run. If tests need the number, assert SHAPE (length ≥ 8, numeric) — or mask the value after the 发票号码/票据号码 label only.
- **Amounts `xx.xx` are NOT matched by `\d{6,}`** — they survive unchanged (good: amounts are the primary correctness bar).

## How to add a new test

1. Find a real PDF that exercises the new case (keep it in a gitignored local dir).
2. Run the parser, save the block layout to `test/fixtures/blocks/<name>.json` (sanitized).
3. Add a test to `test/test_<doc_type>_parser.py` using `parse_fixture(name, doc_type)`.
4. Assert SHAPE, not personal values.

## How to run tests

```bash
python3 -m pytest test/           # all tests
python3 -m pytest test/ -v        # verbose
python3 -m pytest test/test_vat_parser.py::test_vat_items_have_tax_rate_and_tax  # one
```

## Where the data lives

- `test/conftest.py` — `load_blocks(name)`, `parse_fixture(name, doc_type)`, fixture dir
- `test/fixtures/blocks/*.json` — 9 sanitized block layouts (VAT×5, train×1, medical×3)
- `test/test_vat_parser.py` — 12 tests
- `test/test_medical_parser.py` — 6 tests
- `test/test_train_parser.py` — 4 tests
- `pytest.ini` — pytest config
- `scripts/sanity_check.py` — re-runnable DB sanity check (post-extraction, reads DB)
- `scripts/extract_fixtures.py` — generate fixtures from real PDFs (local dev tool, not committed)

## Why this test suite exists

The test suite catches regressions that the earlier manual "ship and see" approach missed:
- Tax-ID swap bug (buyer 个人 got a tax ID)
- Multi-page medical table extraction (3-column vs detail)
- VAT item tax_rate/tax extraction (empty in UI)
- JD space-split layout (no colon in 称)

If you're tempted to add a new invoice type, the test suite is the FIRST thing to extend.
