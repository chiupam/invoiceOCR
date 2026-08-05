"""Train ticket parser tests against sanitized pdfplumber fixtures.

Fixtures: test/fixtures/blocks/train_eticket.json — block layout from a
real 铁路电子客票. Names masked (某乘客 / 某通信公司), amounts preserved.
"""
import pytest

from conftest import parse_fixture


def test_train_core_fields():
    parsed = parse_fixture("train_eticket.json", "train")
    amt = (parsed.amount_in_figures or "").replace("¥", "").replace(",", "").strip()
    assert amt == "340.50", f"amount={amt!r}"
    # buyer = 抬头 company (NOT the passenger)
    assert "通信" in (parsed.buyer_name or ""), f"buyer={parsed.buyer_name!r}"
    # passenger goes into travel_info, not seller
    assert parsed.travel_info.get("乘车人"), f"travel_info={parsed.travel_info}"


def test_train_no_items():
    """E-tickets have no line items."""
    parsed = parse_fixture("train_eticket.json", "train")
    assert len(parsed.items or []) == 0, f"items={parsed.items}"


def test_train_travel_info_populated():
    parsed = parse_fixture("train_eticket.json", "train")
    ti = parsed.travel_info
    assert ti.get("车次"), f"车次 missing: {ti}"
    assert ti.get("出发站"), f"出发站 missing: {ti}"
    assert ti.get("到达站"), f"到达站 missing: {ti}"
    assert ti.get("席别") or ti.get("座位号"), f"seat info missing: {ti}"


def test_train_buyer_not_passenger():
    """The 抬头 company must NOT land in the seller slot."""
    parsed = parse_fixture("train_eticket.json", "train")
    assert parsed.seller_name == "", f"seller should be empty, got {parsed.seller_name!r}"
