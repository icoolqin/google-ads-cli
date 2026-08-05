from __future__ import annotations

from datetime import UTC, datetime

import pytest

from google_ads_cli.billing import summarize_funding, total_daily_budget_units
from google_ads_cli.changes import render_change_query
from google_ads_cli.errors import CliError


def _budget(limit_micros: int, served_micros: int | None = None) -> dict:
    account_budget = {
        "id": "8888888888",
        "status": "APPROVED",
        "approved_spending_limit_micros": str(limit_micros),
        "adjusted_spending_limit_micros": str(limit_micros),
    }
    if served_micros is not None:
        account_budget["amount_served_micros"] = str(served_micros)
    return {"account_budget": account_budget}


def test_funding_reports_net_amount_and_runway() -> None:
    summary = summarize_funding([_budget(1_000_000_000)], daily_budget_units=100.0, currency="XXX")[
        0
    ]
    assert summary["spending_limit_net"] == 1000.0
    assert summary["remaining_net"] == 1000.0
    assert summary["runway_days"] == 10.0
    assert summary["currency"] == "XXX"


def test_tax_rate_reconstructs_the_gross_ui_figure() -> None:
    # A prepay top-up shows gross in the UI but arrives here net of local tax.
    summary = summarize_funding([_budget(1_000_000_000)], tax_rate=0.06)[0]
    assert summary["spending_limit_gross_equivalent"] == 1060.0
    assert summary["tax_rate_applied"] == 0.06


def test_served_amount_reduces_remaining_and_runway() -> None:
    summary = summarize_funding([_budget(1_000_000_000, 400_000_000)], daily_budget_units=100.0)[0]
    assert summary["amount_served"] == 400.0
    assert summary["remaining_net"] == 600.0
    assert summary["runway_days"] == 6.0


def test_tax_rate_is_validated() -> None:
    with pytest.raises(CliError, match="between 0 and 1"):
        summarize_funding([_budget(1_000_000)], tax_rate=6)


def test_missing_limit_does_not_crash() -> None:
    summary = summarize_funding([{"account_budget": {"id": "1"}}], daily_budget_units=150.0)[0]
    assert summary["spending_limit_net"] is None
    assert "runway_days" not in summary


def test_shared_budgets_are_counted_once() -> None:
    rows = [
        {
            "campaign_budget": {
                "resource_name": "customers/1/campaignBudgets/7",
                "amount_micros": "150000000",
            }
        },
        {
            "campaign_budget": {
                "resource_name": "customers/1/campaignBudgets/7",
                "amount_micros": "150000000",
            }
        },
        {
            "campaign_budget": {
                "resource_name": "customers/1/campaignBudgets/8",
                "amount_micros": "50000000",
            }
        },
    ]
    assert total_daily_budget_units(rows) == 200.0


def test_change_query_windows_and_limits() -> None:
    now = datetime(2026, 8, 4, 10, 30, 0, tzinfo=UTC)
    query = render_change_query(customer_id="123", days=14, limit=50, now=now)
    # change_event rejects an open-ended window, so both bounds must be present.
    assert "change_event.change_date_time >= '2026-07-21 10:30:00'" in query
    assert "change_event.change_date_time <= '2026-08-05 10:30:00'" in query
    assert query.rstrip().endswith("LIMIT 50")


def test_change_query_filters_are_injection_safe() -> None:
    with pytest.raises(CliError, match="Unknown resource type"):
        render_change_query(customer_id="123", days=7, limit=10, resource_type="CAMPAIGN; DROP")
    with pytest.raises(CliError, match="numeric"):
        render_change_query(customer_id="123", days=7, limit=10, campaign_id="1 OR 1=1")


def test_change_query_rejects_windows_beyond_retention() -> None:
    with pytest.raises(CliError, match="30 days of history"):
        render_change_query(customer_id="123", days=45, limit=10)


def test_change_query_scopes_campaign_to_customer() -> None:
    query = render_change_query(customer_id="1234567890", days=7, limit=10, campaign_id="123456789")
    assert "customers/1234567890/campaigns/123456789" in query
