"""Account funding readouts.

The Google Ads API exposes account funding through `account_budget` and
`billing_setup`. Both work for prepay accounts, where `account_budget` reports
the *net* spendable amount: a prepay top-up that shows as a gross figure in the
web UI (tax included) arrives here already divided by the local tax rate.

Promotional credits ("spend X, get X") are **not** exposed by the API at all —
they remain a web-UI-only readout.
"""

from __future__ import annotations

from typing import Any

from google_ads_cli.errors import CliError

MICROS = 1_000_000

ACCOUNT_BUDGET_QUERY = """
SELECT
  account_budget.id,
  account_budget.name,
  account_budget.status,
  account_budget.approved_spending_limit_micros,
  account_budget.approved_spending_limit_type,
  account_budget.adjusted_spending_limit_micros,
  account_budget.amount_served_micros,
  account_budget.total_adjustments_micros,
  account_budget.approved_start_date_time,
  account_budget.approved_end_time_type,
  account_budget.billing_setup
FROM account_budget
"""

BILLING_SETUP_QUERY = """
SELECT
  billing_setup.id,
  billing_setup.status,
  billing_setup.start_date_time,
  billing_setup.end_time_type,
  billing_setup.payments_account_info.payments_account_id,
  billing_setup.payments_account_info.payments_account_name
FROM billing_setup
"""

DAILY_BUDGET_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign_budget.resource_name,
  campaign_budget.amount_micros
FROM campaign
WHERE campaign.status = 'ENABLED'
"""


def _micros_to_units(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return int(value) / MICROS
    except (TypeError, ValueError):
        return None


def _budget_field(row: dict[str, Any], name: str) -> Any:
    return (row.get("account_budget") or {}).get(name)


def summarize_funding(
    budget_rows: list[dict[str, Any]],
    *,
    daily_budget_units: float | None = None,
    tax_rate: float | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    """Turn raw account_budget rows into a spend-runway readout.

    `tax_rate` (for example 0.06) only adds a *gross-equivalent* column so the
    number can be reconciled against the web UI's "Available funds". The API
    figures themselves are always reported unchanged.
    """
    if tax_rate is not None and not 0 <= tax_rate < 1:
        raise CliError("--tax-rate must be between 0 and 1 (for example 0.06 for 6%).")

    summaries: list[dict[str, Any]] = []
    for row in budget_rows:
        approved = _micros_to_units(_budget_field(row, "approved_spending_limit_micros"))
        adjusted = _micros_to_units(_budget_field(row, "adjusted_spending_limit_micros"))
        served = _micros_to_units(_budget_field(row, "amount_served_micros")) or 0.0
        limit = adjusted if adjusted is not None else approved

        summary: dict[str, Any] = {
            "account_budget_id": _budget_field(row, "id"),
            "status": _budget_field(row, "status"),
            "currency": currency,
            "spending_limit_net": None if limit is None else round(limit, 2),
            "amount_served": round(served, 2),
            "remaining_net": None if limit is None else round(limit - served, 2),
            "limit_type": _budget_field(row, "approved_spending_limit_type"),
            "start": _budget_field(row, "approved_start_date_time"),
            "end_type": _budget_field(row, "approved_end_time_type"),
        }

        if tax_rate is not None and limit is not None:
            summary["spending_limit_gross_equivalent"] = round(limit * (1 + tax_rate), 2)
            summary["remaining_gross_equivalent"] = round((limit - served) * (1 + tax_rate), 2)
            summary["tax_rate_applied"] = tax_rate

        if daily_budget_units and limit is not None:
            remaining = max(limit - served, 0.0)
            summary["daily_budget_total"] = round(daily_budget_units, 2)
            summary["runway_days"] = round(remaining / daily_budget_units, 1)

        summary["note"] = (
            "account_budget reports NET spendable amount (tax excluded). The web UI's "
            "'Available funds' is usually the gross top-up. Promotional credits are not "
            "exposed by the API."
        )
        summaries.append(summary)
    return summaries


def total_daily_budget_units(campaign_rows: list[dict[str, Any]]) -> float:
    """Sum enabled campaigns' daily budgets, counting each budget resource once."""
    seen: dict[str, float] = {}
    for row in campaign_rows:
        budget = row.get("campaign_budget") or {}
        amount = _micros_to_units(budget.get("amount_micros"))
        resource = budget.get("resource_name") or str(id(budget))
        if amount is not None:
            seen[resource] = amount
    return sum(seen.values())
