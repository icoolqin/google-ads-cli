from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from google_ads_cli.errors import CliError
from google_ads_cli.mutations import MutationOperation, MutationPlan
from google_ads_cli.runtime import normalize_customer_id

GOAL_SETTINGS: dict[str, dict[str, Any]] = {
    "installs": {
        "goal": "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
        "bid_field": "targetCpa",
        "needs_target_cpa": True,
        "needs_conversions": False,
    },
    "installs-and-actions": {
        "goal": "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST",
        "bid_field": "targetCpa",
        "needs_target_cpa": True,
        "needs_conversions": True,
    },
    "in-app-actions": {
        "goal": "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST",
        "bid_field": "targetCpa",
        "needs_target_cpa": True,
        "needs_conversions": True,
    },
    "roas": {
        "goal": "OPTIMIZE_RETURN_ON_ADVERTISING_SPEND",
        "bid_field": "targetRoas",
        "needs_target_cpa": False,
        "needs_conversions": True,
    },
    "installs-no-target": {
        "goal": "OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST",
        "bid_field": "maximizeConversions",
        "needs_target_cpa": False,
        "needs_conversions": False,
    },
    "in-app-actions-no-target": {
        "goal": "OPTIMIZE_IN_APP_CONVERSIONS_WITHOUT_TARGET_CPA",
        "bid_field": "maximizeConversions",
        "needs_target_cpa": False,
        "needs_conversions": True,
    },
    "value-no-target": {
        "goal": "OPTIMIZE_TOTAL_VALUE_WITHOUT_TARGET_ROAS",
        "bid_field": "maximizeConversionValue",
        "needs_target_cpa": False,
        "needs_conversions": True,
    },
}


def money_to_micros(value: str | float | Decimal, label: str) -> int:
    try:
        decimal = Decimal(str(value))
    except InvalidOperation as error:
        raise CliError(f"{label} must be a decimal amount") from error
    if decimal <= 0:
        raise CliError(f"{label} must be greater than zero")
    micros = decimal * Decimal(1_000_000)
    if micros != micros.to_integral_value():
        raise CliError(f"{label} supports at most 6 decimal places")
    return int(micros)


def _resource(value: str, collection: str, customer_id: str | None = None) -> str:
    if "/" in value:
        return value
    if not value.isdigit():
        raise CliError(f"Expected a numeric ID or resource name, got `{value}`")
    if collection in {"geoTargetConstants", "languageConstants"}:
        return f"{collection}/{value}"
    if not customer_id:
        raise CliError(f"A customer ID is required to build {collection} resource names")
    return f"customers/{customer_id}/{collection}/{value}"


def _validate_text_assets(headlines: list[str], descriptions: list[str]) -> None:
    if not 2 <= len(headlines) <= 5:
        raise CliError("App ads require 2-5 headlines.")
    if not 2 <= len(descriptions) <= 5:
        raise CliError("App ads require 2-5 descriptions.")
    for text in headlines:
        if not text.strip() or len(text) > 30:
            raise CliError(f"Headline must be 1-30 characters: `{text}`")
    for text in descriptions:
        if not text.strip() or len(text) > 90:
            raise CliError(f"Description must be 1-90 characters: `{text}`")


@dataclass(slots=True)
class AppCampaignSpec:
    customer_id: str
    name: str
    app_id: str
    app_store: str
    daily_budget: str
    goal: str = "installs"
    target_cpa: str | None = None
    target_roas: float | None = None
    ad_group_name: str = "Default"
    ad_name: str = "Default App Ad"
    headlines: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    conversion_actions: list[str] = field(default_factory=list)
    image_assets: list[str] = field(default_factory=list)
    video_assets: list[str] = field(default_factory=list)
    start_date_time: str | None = None
    end_date_time: str | None = None

    def validate(self) -> None:
        self.customer_id = normalize_customer_id(self.customer_id)
        if not self.name.strip():
            raise CliError("Campaign name cannot be empty.")
        if not self.app_id.strip():
            raise CliError("App ID cannot be empty.")
        self.app_store = self.app_store.upper()
        if self.app_store not in {"APPLE_APP_STORE", "GOOGLE_APP_STORE"}:
            raise CliError("app_store must be APPLE_APP_STORE or GOOGLE_APP_STORE")
        if self.goal not in GOAL_SETTINGS:
            raise CliError(f"Unknown goal `{self.goal}`. Choose: {', '.join(GOAL_SETTINGS)}")
        settings = GOAL_SETTINGS[self.goal]
        if settings["needs_target_cpa"] and self.target_cpa is None:
            raise CliError(f"Goal `{self.goal}` requires --target-cpa.")
        if self.goal == "roas" and (self.target_roas is None or self.target_roas <= 0):
            raise CliError("Goal `roas` requires a positive --target-roas ratio.")
        if settings["needs_conversions"] and not self.conversion_actions:
            raise CliError(f"Goal `{self.goal}` requires at least one --conversion-action.")
        _validate_text_assets(self.headlines, self.descriptions)
        money_to_micros(self.daily_budget, "daily budget")
        if self.target_cpa is not None:
            money_to_micros(self.target_cpa, "target CPA")


def build_app_campaign_plan(spec: AppCampaignSpec) -> MutationPlan:
    spec.validate()
    customer_id = spec.customer_id
    budget_resource = f"customers/{customer_id}/campaignBudgets/-1"
    campaign_resource = f"customers/{customer_id}/campaigns/-2"
    ad_group_resource = f"customers/{customer_id}/adGroups/-3"
    settings = GOAL_SETTINGS[spec.goal]

    campaign: dict[str, Any] = {
        "resourceName": campaign_resource,
        "name": spec.name,
        "campaignBudget": budget_resource,
        "status": "PAUSED",
        "advertisingChannelType": "MULTI_CHANNEL",
        "advertisingChannelSubType": "APP_CAMPAIGN",
        "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "appCampaignSetting": {
            "appId": spec.app_id,
            "appStore": spec.app_store,
            "biddingStrategyGoalType": settings["goal"],
        },
    }
    bid_field = settings["bid_field"]
    if bid_field == "targetCpa":
        campaign[bid_field] = {
            "targetCpaMicros": str(money_to_micros(spec.target_cpa or "", "target CPA"))
        }
    elif bid_field == "targetRoas":
        campaign[bid_field] = {"targetRoas": spec.target_roas}
    else:
        campaign[bid_field] = {}
    if spec.conversion_actions:
        campaign["selectiveOptimization"] = {
            "conversionActions": [
                _resource(value, "conversionActions", customer_id)
                for value in spec.conversion_actions
            ]
        }
    if spec.start_date_time:
        campaign["startDateTime"] = spec.start_date_time
    if spec.end_date_time:
        campaign["endDateTime"] = spec.end_date_time

    operations = [
        MutationOperation(
            resource="campaign_budget",
            action="create",
            data={
                "resourceName": budget_resource,
                "name": f"{spec.name} Budget",
                "amountMicros": str(money_to_micros(spec.daily_budget, "daily budget")),
                "deliveryMethod": "STANDARD",
                "explicitlyShared": False,
            },
        ),
        MutationOperation(resource="campaign", action="create", data=campaign),
    ]
    for location in spec.locations:
        operations.append(
            MutationOperation(
                resource="campaign_criterion",
                action="create",
                data={
                    "campaign": campaign_resource,
                    "status": "ENABLED",
                    "negative": False,
                    "location": {"geoTargetConstant": _resource(location, "geoTargetConstants")},
                },
            )
        )
    for language in spec.languages:
        operations.append(
            MutationOperation(
                resource="campaign_criterion",
                action="create",
                data={
                    "campaign": campaign_resource,
                    "status": "ENABLED",
                    "negative": False,
                    "language": {"languageConstant": _resource(language, "languageConstants")},
                },
            )
        )
    operations.append(
        MutationOperation(
            resource="ad_group",
            action="create",
            data={
                "resourceName": ad_group_resource,
                "name": spec.ad_group_name,
                "campaign": campaign_resource,
                "status": "ENABLED",
            },
        )
    )
    app_ad: dict[str, Any] = {
        "headlines": [{"text": text} for text in spec.headlines],
        "descriptions": [{"text": text} for text in spec.descriptions],
    }
    if spec.image_assets:
        app_ad["images"] = [
            {"asset": _resource(value, "assets", customer_id)} for value in spec.image_assets
        ]
    if spec.video_assets:
        app_ad["youtubeVideos"] = [
            {"asset": _resource(value, "assets", customer_id)} for value in spec.video_assets
        ]
    operations.append(
        MutationOperation(
            resource="ad_group_ad",
            action="create",
            data={
                "adGroup": ad_group_resource,
                "status": "ENABLED",
                "ad": {
                    "name": spec.ad_name,
                    "appAd": app_ad,
                },
            },
        )
    )
    return MutationPlan(
        customer_id=customer_id,
        operations=operations,
        partial_failure=False,
        response_content_type="MUTABLE_RESOURCE",
        label="campaigns.create-app",
    )
