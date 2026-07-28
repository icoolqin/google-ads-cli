from __future__ import annotations

import pytest

from google_ads_cli.errors import CliError
from google_ads_cli.presets import date_filter, render_report_query
from google_ads_cli.query import selected_fields


def test_selected_fields_handles_multiline_query() -> None:
    query = """
    SELECT campaign.id,
           campaign.name,
           metrics.cost_micros
    FROM campaign
    """
    assert selected_fields(query) == [
        "campaign.id",
        "campaign.name",
        "metrics.cost_micros",
    ]


def test_report_date_filters_are_injection_safe() -> None:
    assert date_filter("LAST_30_DAYS") == "segments.date DURING LAST_30_DAYS"
    assert (
        date_filter("2026-01-01:2026-01-31")
        == "segments.date BETWEEN '2026-01-01' AND '2026-01-31'"
    )
    with pytest.raises(CliError):
        date_filter("LAST_30_DAYS' OR 1=1")
    with pytest.raises(CliError, match="start"):
        date_filter("2026-02-01:2026-01-01")


def test_report_query_renders() -> None:
    query = render_report_query("campaigns", "LAST_7_DAYS")
    assert "segments.date DURING LAST_7_DAYS" in query
    assert "{date_filter}" not in query
