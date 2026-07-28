from __future__ import annotations

import re
from dataclasses import dataclass

from google_ads_cli.errors import CliError


@dataclass(frozen=True, slots=True)
class ReportPreset:
    name: str
    description: str
    query: str


REPORT_PRESETS = {
    "summary": ReportPreset(
        "summary",
        "Account-wide delivery and conversion totals.",
        """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.currency_code,
          metrics.impressions,
          metrics.clicks,
          metrics.interactions,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM customer
        WHERE {date_filter}
        """,
    ),
    "campaigns": ReportPreset(
        "campaigns",
        "Campaign delivery, cost, and conversion performance.",
        """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign.advertising_channel_sub_type,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM campaign
        WHERE campaign.status != 'REMOVED' AND {date_filter}
        ORDER BY metrics.cost_micros DESC
        """,
    ),
    "ad-groups": ReportPreset(
        "ad-groups",
        "Ad group delivery, cost, and conversion performance.",
        """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM ad_group
        WHERE ad_group.status != 'REMOVED' AND {date_filter}
        ORDER BY metrics.cost_micros DESC
        """,
    ),
    "ads": ReportPreset(
        "ads",
        "Ad-level delivery, approval state, cost, and conversions.",
        """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.ad.type,
          ad_group_ad.status,
          ad_group_ad.policy_summary.approval_status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED' AND {date_filter}
        ORDER BY metrics.cost_micros DESC
        """,
    ),
    "daily": ReportPreset(
        "daily",
        "Daily account trend.",
        """
        SELECT
          segments.date,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM customer
        WHERE {date_filter}
        ORDER BY segments.date
        """,
    ),
    "conversion-actions": ReportPreset(
        "conversion-actions",
        "Performance split by conversion action.",
        """
        SELECT
          segments.conversion_action,
          segments.conversion_action_name,
          metrics.conversions,
          metrics.conversions_value,
          metrics.all_conversions,
          metrics.all_conversions_value
        FROM customer
        WHERE {date_filter}
        ORDER BY metrics.all_conversions_value DESC
        """,
    ),
}

PREDEFINED_RANGES = {
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "THIS_MONTH",
    "LAST_MONTH",
}


def date_filter(value: str) -> str:
    normalized = value.upper()
    if normalized in PREDEFINED_RANGES:
        return f"segments.date DURING {normalized}"
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})", value)
    if match:
        start, end = match.groups()
        if start > end:
            raise CliError("Custom date range start must not be after its end.")
        return f"segments.date BETWEEN '{start}' AND '{end}'"
    raise CliError(
        "Date range must be a supported name (for example LAST_30_DAYS) or YYYY-MM-DD:YYYY-MM-DD."
    )


def render_report_query(name: str, date_range: str) -> str:
    try:
        preset = REPORT_PRESETS[name]
    except KeyError as error:
        raise CliError(f"Unknown report `{name}`. Choose: {', '.join(REPORT_PRESETS)}") from error
    return " ".join(preset.query.format(date_filter=date_filter(date_range)).split())
