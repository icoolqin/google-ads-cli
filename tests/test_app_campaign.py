from __future__ import annotations

import pytest

from google_ads_cli.ads_client import schema_client
from google_ads_cli.app_campaign import AppCampaignSpec, build_app_campaign_plan, money_to_micros
from google_ads_cli.errors import CliError
from google_ads_cli.mutations import compile_operations

CUSTOMER_ID = "1234567890"


def make_spec(**overrides: object) -> AppCampaignSpec:
    values = {
        "customer_id": CUSTOMER_ID,
        "name": "Example App US Install",
        "app_id": "123456789",
        "app_store": "APPLE_APP_STORE",
        "daily_budget": "50",
        "target_cpa": "2.5",
        "headlines": ["AI Photo Magic", "One Shot, Endless Wonder"],
        "descriptions": [
            "Turn one photo into endless creative styles.",
            "Create, remix, and share in seconds.",
        ],
        "locations": ["2840"],
        "languages": ["1000"],
    }
    values.update(overrides)
    return AppCampaignSpec(**values)


def test_money_to_micros_is_exact() -> None:
    assert money_to_micros("2.500001", "amount") == 2_500_001
    with pytest.raises(CliError, match="at most 6"):
        money_to_micros("0.0000001", "amount")


def test_app_campaign_plan_is_paused_atomic_and_v25_valid() -> None:
    plan = build_app_campaign_plan(make_spec())
    assert plan.partial_failure is False
    assert [operation.resource for operation in plan.operations] == [
        "campaign_budget",
        "campaign",
        "campaign_criterion",
        "campaign_criterion",
        "ad_group",
        "ad_group_ad",
    ]
    campaign = plan.operations[1].data
    assert campaign["status"] == "PAUSED"
    assert campaign["campaignBudget"].endswith("/-1")
    assert campaign["appCampaignSetting"]["appId"] == "123456789"
    assert campaign["targetCpa"]["targetCpaMicros"] == "2500000"
    assert plan.operations[-2].data["status"] == "ENABLED"
    assert plan.operations[-1].data["status"] == "ENABLED"

    compiled = compile_operations(schema_client("v25"), plan.operations, api_version="v25")
    assert len(compiled) == len(plan.operations)


def test_goal_requiring_conversions_fails_closed() -> None:
    with pytest.raises(CliError, match="conversion-action"):
        build_app_campaign_plan(make_spec(goal="in-app-actions"))


def test_v25_no_target_goal_uses_maximize_conversions() -> None:
    plan = build_app_campaign_plan(make_spec(goal="installs-no-target", target_cpa=None))
    campaign = plan.operations[1].data
    assert campaign["maximizeConversions"] == {}
    assert (
        campaign["appCampaignSetting"]["biddingStrategyGoalType"]
        == "OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST"
    )
    compile_operations(schema_client("v25"), plan.operations, api_version="v25")


def test_creative_text_limits_are_checked_locally() -> None:
    with pytest.raises(CliError, match="2-5 headlines"):
        build_app_campaign_plan(make_spec(headlines=["Only one"]))
    with pytest.raises(CliError, match="1-30"):
        build_app_campaign_plan(make_spec(headlines=["x" * 31, "valid"]))
