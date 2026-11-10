"""Invoice statistics (pure functions over model instances)."""
from __future__ import annotations

import re
from datetime import datetime


def _amount_of(invoice) -> float:
    if not invoice.amount_in_figures:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", invoice.amount_in_figures)
    try:
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


def get_invoice_statistics(invoices) -> dict:
    invoice_count = len(invoices)
    total_amount = sum(_amount_of(inv) for inv in invoices)

    month_stats: dict[str, dict] = {}
    for inv in invoices:
        if not inv.invoice_date:
            continue
        key = inv.invoice_date.strftime("%Y-%m")
        bucket = month_stats.setdefault(key, {"count": 0, "amount": 0.0})
        bucket["count"] += 1
        bucket["amount"] += _amount_of(inv)
    sorted_months = sorted(month_stats)

    type_stats: dict[str, int] = {}
    for inv in invoices:
        if inv.invoice_type:
            type_stats[inv.invoice_type] = type_stats.get(inv.invoice_type, 0) + 1

    current_month_key = datetime.now().strftime("%Y-%m")
    current = month_stats.get(current_month_key, {"count": 0, "amount": 0.0})

    return {
        "invoice_count": invoice_count,
        "total_amount": "{:,.2f}".format(total_amount),
        "monthly_data": {
            "labels": sorted_months,
            "counts": [month_stats[m]["count"] for m in sorted_months],
            "amounts": [month_stats[m]["amount"] for m in sorted_months],
        },
        "type_data": {
            "labels": list(type_stats.keys()),
            "counts": list(type_stats.values()),
        },
        "current_month": {
            "month": "本月",
            "count": current["count"],
            "amount": current["amount"],
        },
    }
