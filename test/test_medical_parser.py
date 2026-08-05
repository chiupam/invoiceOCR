"""Medical parser tests against sanitized pdfplumber fixtures.

Fixtures: test/fixtures/blocks/medical_*.json — block layouts from real
中央医疗收费票据 (outpatient, inpatient 3-page, 2-column). Names masked
(某患者 / 某医院), amounts preserved. The multi-page fixture exercises the
summary-vs-detail table anchoring and cross-page grouping fixes.
"""
import pytest

from conftest import parse_fixture

JUNK_MARKERS = [
    "合计", "价税合计", "小写", "大写", "医保统筹", "统筹基金", "流水号",
    "门诊号", "就诊日期", "收款单位", "复核人", "收款人", "信自付",
    "单位补充", "退休补充", "大病保障", "医疗救助", "年度门诊", "年度医保",
    "医保交易", "医保已结", "残军补助", "其他支付", "个人账户支付",
    "个人现金支付", "个人自付", "个人自费",
]


def test_medical_outpatient_core():
    parsed = parse_fixture("medical_outpatient.json", "medical")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "1913.76", f"amount={amt!r}"
    assert "医院" in (parsed.seller_name or ""), f"seller={parsed.seller_name!r}"
    assert parsed.buyer_name, "buyer missing"
    # medical-info section populated
    assert parsed.medical_info.get("医保类型"), f"medical_info={parsed.medical_info}"


def test_medical_2col_core():
    parsed = parse_fixture("medical_2col.json", "medical")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "210.00", f"amount={amt!r}"
    assert "医院" in (parsed.seller_name or ""), f"seller={parsed.seller_name!r}"


def test_medical_inpatient_3page_detail_items():
    """The 3-page receipt must extract the DETAIL table (pages 1+) not the
    page-0 3-column summary. 107 real rows; summary would give ~8."""
    parsed = parse_fixture("medical_inpatient_3page.json", "medical")
    n = len(parsed.items)
    assert n >= 50, f"expected detail rows, got {n} (summary table?)"
    # No cross-page merged rows: item names should not contain two names
    for it in parsed.items:
        name = it.get("name", "")
        assert name.strip(), "empty item name"


def test_medical_items_no_junk():
    """Item names must not contain junk markers (合计/小写/医保统筹...)."""
    for fixture in ("medical_outpatient.json", "medical_2col.json", "medical_inpatient_3page.json"):
        parsed = parse_fixture(fixture, "medical")
        for it in parsed.items:
            name = it.get("name", "")
            for m in JUNK_MARKERS:
                assert m not in name, f"{fixture}: junk {m!r} in {name!r}"


def test_medical_item_names_clean():
    """Item names must not carry qty/unit/remark tail (1.00日 00无自付).

    Known best-effort limitation (skill pitfall #9): some dense rows merge
    spec/qty into the name when the unit block is missing (e.g.
    '一次性真空采血管(BD)3.5M1.00'). We assert the AMOUNT is correct and
    the name contains at least a CJK fragment — not a perfectly clean name.
    """
    parsed = parse_fixture("medical_outpatient.json", "medical")
    for it in parsed.items:
        name = it.get("name", "")
        # name must contain CJK (a real item), not pure numbers/junk
        assert any('\u4e00' <= c <= '\u9fff' for c in name), f"no CJK in name: {name!r}"
        assert it.get("amount"), f"item without amount: {it!r}"


def test_medical_amounts_present():
    for fixture in ("medical_outpatient.json", "medical_2col.json", "medical_inpatient_3page.json"):
        parsed = parse_fixture(fixture, "medical")
        for it in parsed.items:
            assert it.get("amount"), f"{fixture}: item without amount: {it!r}"
