"""Account change history.

`change_event` answers "who changed what, when" — the resource you want when a
campaign starts behaving differently and nobody remembers touching it.

Two API constraints shape this module: the resource **requires** a `LIMIT`
clause, and it only retains the **last 30 days** of history.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from google_ads_cli.errors import CliError

MAX_LOOKBACK_DAYS = 30
MAX_LIMIT = 10_000

CHANGE_RESOURCE_TYPES = (
    "AD",
    "AD_GROUP",
    "AD_GROUP_AD",
    "AD_GROUP_ASSET",
    "AD_GROUP_BID_MODIFIER",
    "AD_GROUP_CRITERION",
    "AD_GROUP_FEED",
    "ASSET",
    "ASSET_SET",
    "ASSET_SET_ASSET",
    "CAMPAIGN",
    "CAMPAIGN_ASSET",
    "CAMPAIGN_BUDGET",
    "CAMPAIGN_CRITERION",
    "CAMPAIGN_FEED",
    "CUSTOMER_ASSET",
    "FEED",
    "FEED_ITEM",
)

_QUERY = """
SELECT
  change_event.change_date_time,
  change_event.change_resource_type,
  change_event.change_resource_name,
  change_event.resource_change_operation,
  change_event.client_type,
  change_event.user_email,
  change_event.changed_fields,
  change_event.campaign,
  change_event.ad_group
FROM change_event
WHERE {conditions}
ORDER BY change_event.change_date_time DESC
LIMIT {limit}
"""


def render_change_query(
    *,
    customer_id: str,
    days: int,
    limit: int,
    resource_type: str | None = None,
    campaign_id: str | None = None,
    now: datetime | None = None,
) -> str:
    if not 1 <= days <= MAX_LOOKBACK_DAYS:
        raise CliError(
            f"change_event only retains {MAX_LOOKBACK_DAYS} days of history; "
            f"--days must be 1-{MAX_LOOKBACK_DAYS}."
        )
    if not 1 <= limit <= MAX_LIMIT:
        raise CliError(f"--limit must be between 1 and {MAX_LIMIT}.")

    # change_event rejects an open-ended window ("infinite range"), so both
    # bounds are always supplied. The upper bound is nudged into the future so
    # changes made seconds ago are still included.
    until = (now or datetime.now(UTC)) + timedelta(days=1)
    since = until - timedelta(days=days + 1)
    conditions = [
        f"change_event.change_date_time >= '{since.strftime('%Y-%m-%d %H:%M:%S')}'",
        f"change_event.change_date_time <= '{until.strftime('%Y-%m-%d %H:%M:%S')}'",
    ]
    if resource_type:
        normalized = resource_type.upper()
        if normalized not in CHANGE_RESOURCE_TYPES:
            raise CliError(
                f"Unknown resource type `{resource_type}`. "
                f"Choose: {', '.join(CHANGE_RESOURCE_TYPES)}"
            )
        conditions.append(f"change_event.change_resource_type = '{normalized}'")
    if campaign_id:
        if not re.fullmatch(r"\d+", campaign_id):
            raise CliError("Campaign ID must be numeric.")
        conditions.append(
            f"change_event.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'"
        )
    return " ".join(_QUERY.format(conditions=" AND ".join(conditions), limit=limit).split())
