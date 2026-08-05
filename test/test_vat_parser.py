"""VAT parser tests against sanitized pdfplumber fixtures.

Fixtures: test/fixtures/blocks/vat_*.json — block layouts (text + bbox)
from real 数电发票 / 成品油 / 出行 / 老版2023 invoices. Personal names
and tax IDs are masked (某公司 / 某乘客 / 9111**********); invoice numbers
are digit-masked. The layout SHAPE is preserved, which is what the parser
consumes.

Assertions use SHAPE (length, presence) rather than exact personal values.
"""
import pytest

from conftest import parse_fixture


def test_vat_jd_core_fields():
    parsed = parse_fixture("vat_jd.json", "vat")
    assert parsed.invoice_number, "invoice_number missing"
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "370.08", f"amount={amt!r}"
    assert "个人" in (parsed.buyer_name or ""), f"buyer={parsed.buyer_name!r}"
    assert "电商" in (parsed.seller_name or ""), f"seller={parsed.seller_name!r}"


def test_vat_fuel_core_fields():
    parsed = parse_fixture("vat_fuel.json", "vat")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "207.50", f"amount={amt!r}"
    assert "个人" in (parsed.buyer_name or ""), f"buyer={parsed.buyer_name!r}"
    assert "石化" in (parsed.seller_name or ""), f"seller={parsed.seller_name!r}"


def test_vat_travel_core_fields():
    parsed = parse_fixture("vat_travel_1.json", "vat")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "22.81", f"amount={amt!r}"
    assert "通信" in (parsed.buyer_name or ""), f"buyer={parsed.buyer_name!r}"


def test_vat_didi_core_fields():
    parsed = parse_fixture("vat_didi.json", "vat")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "98.22", f"amount={amt!r}"
    assert "通信" in (parsed.buyer_name or ""), f"buyer={parsed.buyer_name!r}"
    assert "出行" in (parsed.seller_name or ""), f"seller={parsed.seller_name!r}"


def test_vat_old2023_layout():
    """老版2023 发票: separate 发票代码/发票号码/校验码/机器编号 labels."""
    parsed = parse_fixture("vat_travel_old2023.json", "vat")
    assert parsed.invoice_code, f"code={parsed.invoice_code!r}"
    assert parsed.check_code, "check_code should be set"
    assert parsed.machine_number, "machine_number should be set"
    assert parsed.invoice_number, "invoice_number missing"


@pytest.mark.parametrize("fixture,min_items", [
    ("vat_jd.json", 1),
    ("vat_fuel.json", 1),
    ("vat_travel_1.json", 1),
    ("vat_travel_old2023.json", 1),
    ("vat_didi.json", 1),
])
def test_vat_has_items(fixture, min_items):
    parsed = parse_fixture(fixture, "vat")
    assert len(parsed.items) >= min_items, f"items={len(parsed.items)}"


def test_vat_items_have_tax_rate_and_tax():
    """The % word anchors amount (left) and tax (right); items carry
    tax_rate + tax (fix for empty 税额 in the UI)."""
    parsed = parse_fixture("vat_fuel.json", "vat")
    assert parsed.items, "fuel invoice should have items"
    item = parsed.items[0]
    assert item.get("tax_rate") == "13%", f"tax_rate={item.get('tax_rate')!r}"
    assert item.get("tax") == "¥23.87", f"tax={item.get('tax')!r}"
    amt = item.get("amount", "").replace("¥", "").replace(",", "")
    assert amt == "183.63", f"amount={item.get('amount')!r}"


def test_vat_travel_negative_items():
    """出行 invoices carry negative adjustment lines (refund)."""
    parsed = parse_fixture("vat_didi.json", "vat")
    amounts = [i.get("amount", "") for i in parsed.items]
    assert any("-" in a for a in amounts), f"no negative item: {amounts}"


def test_vat_personal_buyer_has_no_tax_id():
    """Swap-bug guard: buyer 个人 must NOT get a tax ID."""
    parsed = parse_fixture("vat_jd.json", "vat")
    assert "个人" in (parsed.buyer_name or "")
    assert parsed.buyer_tax_id == "", f"buyer_tax_id={parsed.buyer_tax_id!r}"
    assert parsed.seller_tax_id, "seller_tax_id should be set"
