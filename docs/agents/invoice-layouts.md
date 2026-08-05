# Invoice layout types & quirks

## Three doc types (registered in `core/doc_types/`)

| type_id | display_name | Sample PDF (local) | Notes |
|---|---|---|---|
| `vat` | 增值税发票 | `didi_vat_test.pdf`, `vat_sample2.pdf`, `jd_invoice.pdf`, `travel_invoice*.pdf` | 电子普通发票 / 成品油 / 出行发票 / 老版2023 |
| `medical` | 医疗票据 | `medical/1_00060125_0128391715.PDF` (门诊), `medical/1_00060226_0002176941.PDF` (住院 3-page) | 中央医疗门诊 / 住院收费票据 |
| `train` | 铁路电子客票 | `train_ticket.pdf` | 12306电子客票 |

## Sanitized ground truth (for sanity_check.py)

> **Privacy:** the source PDFs contain real personal data. The table below
> records ONLY non-personal invariants (type, number, date, amounts, item
> counts). Names are described by shape (个人 / 公司), tax IDs masked.

| File | Type | 发票号码 | 发票代码 | 价税合计 | 买方 | 卖方 | Seller tax ID |
|---|---|---|---|---|---|---|---|
| `medical/1_00060125_0128391715.PDF` | 中央医疗门诊 | 5001201283 | 00060125 | ¥1,913.76 | 个人(患者) | 某医院 | — |
| `medical/1_00060226_0002176941.PDF` | 中央医疗 住院 (3 pages) | 5557621496 | 00060226 | ¥33,032.84 | 个人(患者) | 某医院 | — |
| `didi_vat_test.pdf` | 增值税电子普通发票 (数电) | digital | ❌ none | ¥98.22 | 公司(抬头) | 某出行公司 | 91110108MA01***** |
| `vat_sample2.pdf` | 增值税电子普通发票 (成品油, 数电) | digital | ❌ none | ¥207.50 | 个人 | 某石化销售分公司 | 9111000080******** |
| `jd_invoice.pdf` | 增值税电子普通发票 (数电) | digital | ❌ none | ¥370.08 | 个人 | 某电商健康公司 | 91110302MA01***** |
| `jd_invoice2.pdf` | 增值税电子普通发票 (数电) | digital | ❌ none | ¥89.99 | 个人 | 某电商信息公司 | 9111030256******** |
| `train_ticket.pdf` | 铁路电子客票 | digital | ❌ none | ¥340.50 | 个人(乘客) | 某通信公司北京分公司 | 9111000080******** |
| `medical/1_00060125_0127499358.PDF` | 中央医疗门诊 | 5001201283 | 00060125 | ¥175.80 | 个人(患者) | 某医院 | — |

## Layout quirks that break parsers

### JD 数电发票

```
买 名 称 个人 卖 名 称 某京东健康公司
统一社会信用代码/纳税人识别号 统一社会信用代码/纳税人识别号91110302MA01*****
```

- 买/卖 markers; space-split 名 称; buyer value empty (个人 has no credit code).
- In pdfplumber blocks the label and value may be SEPARATE blocks on the same Y row — scan rightward on same Y for the value.
- 价税合计（大写）叁佰柒拾圆零捌分（小写）¥370.08 — the （小写）¥ can leak a bare `￥ ¥` item row; filter symbol-only names.

### Fuel 数电发票 (成品油)

- Total row is `合 计 ¥183.63 ¥23.87` — contains 合计 but NOT 金额; skip-rule must match 合计 alone.
- Item line: `*汽油*92号京标车用汽油92号 升 29.899135456.14164916 183.6313% 23.87` — spec/unit/qty/price/rate all interleave into the name; amount (last decimal) is reliable.

### Medical 2-column table

```
项目名称 数量/单位 金额（元） 备注 | 项目名称 数量/单位 金额（元） 备注
检查费 56.00 | 化验费 1,834.00
胎盘生长因子（PLGF）检测 1.00项 330.0000 无自付 | 一次性真空采血管 1.00支 1.4300 无自付
```

- Column boundary = gap between 4th header token (备注) and 5th (项目名称). Header token X for 门诊1: 126/201/252/301 | 365/439/490/539, boundary ≈ 333.
- qty values (1.00项) are also decimals — strip the name at the first `\d+(\.\d+)?[项次支盒袋剂片]` BEFORE removing the price amount, else the qty gets eaten and `1.00` becomes `00`.
- The 门诊1 receipt lists BOTH category totals (检查费/治疗费/化验费/卫生材料费 = 1913.76) AND 9 detail rows (~1913.76) — the sum double-counts by design; it's a property of the source document, not a parser bug.

### Medical multi-page detail table (住院 3-page, ¥33,032.84)

- **Page 0**: 3-column SUMMARY table (大项: 项目名称/金额/备注 per column)
- **Pages 1+**: full-width DETAIL table (项目名称/数量/单位/金额/备注)
- Anchor item extraction on the detail table: find `数量/单位` header Y (only exists in the detail table), accept only a `项目名称` at that Y as start.
- Group rows by `(page, y)` NOT `y` — same Y on different pages merges rows.
- `mid_x` column-split must use header blocks from the SAME page only (cross-page header blocks inflate count → bogus split).
- Item name = text before first qty+unit token: `\d+(\.\d+)?\s*(?:日|小时|人次|科/次|床日|床位·日|每胎|半小时|例|个|套|袋|瓶|支|根|盒|包|片|项|次)` — NO `\b` (Chinese unit + digit has no word boundary in Python re).
- ~107 real detail items; the 3-col summary rows must NOT be extracted as items.

### Train 铁路电子客票

- Full-width digits: `２６３...` `￥３４０．５０`. Normalize via str.maketrans (must be 1:1 aligned — an off-by-one silently maps ￥→, and ！→$).
- 出发站/到达站: `婺源 G9871 厦门` — find the line containing the train number, take Chinese before/after.
- Passenger name + masked ID may be on the same line OR adjacent lines in OCR output — check both.
- 购买方名称 = company (抬头), NOT the passenger. Post-processor must NOT apply the VAT 名称： pattern to train/medical — it grabs the wrong entity.

### Medical header block (dense labels)

- Seller = hospital from `收款单位（章）：某医院` at the bottom of the receipt — medical has no 销售方 block; without this extraction seller_name stays empty.
- Info line packs labels with no separator: `医疗机构类型：综合医院医保类型：普通医保编号：12784457300S性别：女`. Per-field `\S+` regexes over-capture. Use stop-at-next-known-label: value runs from after `label:` until the earliest next label OR end of line; strip vertical-text padding chars 他/信/息.

## OCR model observations

- SiliconFlow DeepSeek-OCR: 4-8s, faithful, grounding-token output; occasionally misses the date line or tax-id block entirely (variance, not a code bug).
- Qwen3-VL-8B: plain labeled text, 20-60s, reliable.
- Ollama local `frob/unlimited-ocr:q8_0`: 3.1GB GGUF, ~22s on CPU, works but non-deterministic (sometimes truncates the table block).
- GLM-OCR via Ollama: repetition loop (10K+ chars garbage) — its n-gram logits processor isn't wired into the GGUF, and Ollama's API doesn't expose ngram_size/window_size. Not viable on CPU.
- DeepSeek-OCR GGUF (6.7GB) doesn't load on 11GB-RAM hosts.
- Official Baidu Unlimited-OCR emits DeepSeek-style grounding tokens; the community GGUF emits `label [bbox]content` — the `ocr_formats` registry distinguishes them by quantization tag (`*unlimited-ocr` official vs `*unlimited-ocr:*` GGUF).

## How to debug parser failures

1. **Run the parser on the raw PDF text** (not the UI): `local_pdf.extract(path, doc_type)` → print the `ParsedInvoice`. Compare fields to expected.
2. **Look at the raw text blocks** — `blocks = local_pdf._call_ocr(path)` then print positions of the labels (e.g. `名`, `称`, `统一社会信用代码`, `京东京`) and the values around them.
3. **Check the Y-bin** — items in `(page, y)` groups; if a row doesn't appear, the Y-bin is wrong (Y tolerance is `±4pt`).
4. **Check the mid_x** — for 2-column layouts, the column boundary is the gap between the 4th header token (备注) and the 5th, NOT the biggest gap.
5. **Check the unit regex** — the qty+unit alternation must include the actual unit chars used in your layout. Add new units there if needed.

## See also

- `parser-architecture.md` — DocType contract, backend split, format registry
- `sanitized-fixture-tests.md` — how to test parser changes via sanitized pdfplumber blocks
- `beijing-e-invoice-family.md` — cid-font + stamp receipt variant
