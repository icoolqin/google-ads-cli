from __future__ import annotations

import getpass
import json
import os
import re
from pathlib import Path
from typing import Any

import typer
from google.ads.googleads.errors import GoogleAdsException
from rich.console import Console

from google_ads_cli import __version__
from google_ads_cli.ads_client import (
    create_session,
    resolve_api_version,
    supported_api_versions,
)
from google_ads_cli.app_campaign import GOAL_SETTINGS, AppCampaignSpec, build_app_campaign_plan
from google_ads_cli.assets import image_upload_plan, youtube_asset_plan
from google_ads_cli.audit import default_audit_path, read_audit
from google_ads_cli.config import (
    AppConfig,
    Profile,
    default_config_path,
    default_credentials_path,
)
from google_ads_cli.errors import CliError, google_ads_error_details
from google_ads_cli.mutations import (
    MutationOperation,
    MutationPlan,
    execute_plan,
    load_mutation_plan,
    plan_preview,
    validate_plan_schema,
)
from google_ads_cli.oauth import login as oauth_login
from google_ads_cli.output import OUTPUT_FORMATS, Output, message_to_dict
from google_ads_cli.presets import REPORT_PRESETS, render_report_query
from google_ads_cli.query import (
    run_gaql,
    search_fields,
    selected_fields,
    validate_gaql,
)
from google_ads_cli.runtime import Runtime, normalize_customer_id

app = typer.Typer(
    name="gads",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Safely inspect and operate Google Ads accounts.",
)
auth_app = typer.Typer(no_args_is_help=True, help="Authorize Google Ads API access.")
config_app = typer.Typer(no_args_is_help=True, help="Manage non-secret CLI profiles.")
accounts_app = typer.Typer(no_args_is_help=True, help="Inspect accessible account hierarchies.")
query_app = typer.Typer(no_args_is_help=True, help="Run or validate arbitrary GAQL.")
fields_app = typer.Typer(no_args_is_help=True, help="Discover GAQL fields and compatibility.")
reports_app = typer.Typer(no_args_is_help=True, help="Run curated performance reports.")
campaigns_app = typer.Typer(no_args_is_help=True, help="Inspect and manage campaigns.")
budgets_app = typer.Typer(no_args_is_help=True, help="Inspect and manage campaign budgets.")
adgroups_app = typer.Typer(no_args_is_help=True, help="Inspect ad groups.")
ads_app = typer.Typer(no_args_is_help=True, help="Inspect ads.")
assets_app = typer.Typer(no_args_is_help=True, help="Inspect and create immutable assets.")
conversions_app = typer.Typer(no_args_is_help=True, help="Inspect conversion actions.")
geo_app = typer.Typer(no_args_is_help=True, help="Find location and language constants.")
mutate_app = typer.Typer(no_args_is_help=True, help="Plan, validate, or execute generic mutates.")
audit_app = typer.Typer(no_args_is_help=True, help="Inspect the local mutation audit trail.")

app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(accounts_app, name="accounts")
app.add_typer(query_app, name="query")
app.add_typer(fields_app, name="fields")
app.add_typer(reports_app, name="reports")
app.add_typer(campaigns_app, name="campaigns")
app.add_typer(budgets_app, name="budgets")
app.add_typer(adgroups_app, name="adgroups")
app.add_typer(ads_app, name="ads")
app.add_typer(assets_app, name="assets")
app.add_typer(conversions_app, name="conversions")
app.add_typer(geo_app, name="geo")
app.add_typer(mutate_app, name="mutate")
app.add_typer(audit_app, name="audit")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gads {__version__}; API schemas: {', '.join(supported_api_versions())}")
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    config_file: Path | None = typer.Option(
        None,
        "--config",
        envvar="GADS_CONFIG_FILE",
        help="CLI profile file (not the Google credentials file).",
    ),
    profile: str | None = typer.Option(None, "--profile", envvar="GADS_PROFILE"),
    customer_id: str | None = typer.Option(
        None, "--customer-id", envvar="GADS_CUSTOMER_ID", help="10-digit client account ID."
    ),
    api_version: str | None = typer.Option(
        None, "--api-version", envvar="GADS_API_VERSION", help="For example v25."
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", envvar="GADS_OUTPUT_FORMAT", help="table, json, jsonl, or csv."
    ),
    no_color: bool = typer.Option(False, "--no-color"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show CLI and supported API versions.",
    ),
) -> None:
    del version
    if output_format not in OUTPUT_FORMATS:
        raise CliError(f"--format must be one of: {', '.join(OUTPUT_FORMATS)}")
    ctx.obj = Runtime(
        config_path=config_file,
        profile_name=profile,
        customer_id_override=customer_id,
        api_version_override=api_version,
        output_format=output_format,
        no_color=no_color,
        verbose=verbose,
    )


def _runtime(ctx: typer.Context) -> Runtime:
    if not isinstance(ctx.obj, Runtime):
        raise CliError("Internal error: CLI runtime is unavailable.")
    return ctx.obj


def _output(ctx: typer.Context) -> Output:
    runtime = _runtime(ctx)
    return Output(runtime.output_format, no_color=runtime.no_color)


def _read_query(query: str | None, file: Path | None) -> str:
    if bool(query) == bool(file):
        raise CliError("Provide exactly one of QUERY or --file.")
    if file:
        try:
            query = file.read_text(encoding="utf-8")
        except OSError as error:
            raise CliError(f"Could not read query file {file}: {error}") from error
    assert query is not None
    query = query.strip()
    if not query:
        raise CliError("GAQL query cannot be empty.")
    return query


def _run_mutation(
    ctx: typer.Context,
    plan: MutationPlan,
    *,
    execute: bool,
    validate_only: bool,
) -> None:
    if execute and validate_only:
        raise CliError("Choose either --execute or --validate-only, not both.")
    runtime = _runtime(ctx)
    requested_version = runtime.api_version(plan.api_version)
    version = validate_plan_schema(plan, requested_version)
    writer = _output(ctx)
    if not execute and not validate_only:
        writer.render(plan_preview(plan, version), title=f"PLAN: {plan.label}")
        return
    session = create_session(
        runtime,
        customer_id=plan.customer_id,
        api_version=version,
    )
    if session.customer_id != plan.customer_id:
        raise CliError("Selected profile customer ID does not match the mutation plan.")
    writer.render(
        execute_plan(session, plan, validate_only=validate_only),
        title="Validation result" if validate_only else "Mutation result",
    )


@config_app.command("path")
def config_path(ctx: typer.Context) -> None:
    runtime = _runtime(ctx)
    _output(ctx).render(
        {
            "config_file": str(runtime.config_path or default_config_path()),
            "default_credentials_file": str(default_credentials_path()),
            "audit_file": str(default_audit_path()),
        }
    )


@config_app.command("init")
def config_init(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--name", help="Profile name."),
    credentials_file: Path | None = typer.Option(
        None, "--credentials", help="Path to the official google-ads.yaml."
    ),
    customer_id: str | None = typer.Option(None, "--customer-id"),
    login_customer_id: str | None = typer.Option(None, "--login-customer-id"),
    api_version: str | None = typer.Option(None, "--api-version"),
    make_default: bool = typer.Option(True, "--default/--no-default"),
) -> None:
    runtime = _runtime(ctx)
    path = runtime.config_path or default_config_path()
    config = AppConfig.load(path, required=False)
    existing = config.profiles.get(profile, Profile())
    selected_credentials = credentials_file or (
        Path(existing.credentials_file).expanduser()
        if existing.credentials_file
        else default_credentials_path()
    )
    config.profiles[profile] = Profile(
        credentials_file=str(selected_credentials),
        customer_id=normalize_customer_id(customer_id) if customer_id else existing.customer_id,
        login_customer_id=(
            normalize_customer_id(login_customer_id)
            if login_customer_id
            else existing.login_customer_id
        ),
        api_version=resolve_api_version(api_version or existing.api_version),
    )
    if make_default:
        config.default_profile = profile
    saved = config.save(path)
    _output(ctx).render(
        {
            "config_file": str(saved),
            "profile": profile,
            "default_profile": config.default_profile,
            "credentials_file": str(selected_credentials),
            "customer_id": config.profiles[profile].customer_id,
            "login_customer_id": config.profiles[profile].login_customer_id,
            "api_version": config.profiles[profile].api_version,
        }
    )


@config_app.command("show")
def config_show(ctx: typer.Context) -> None:
    runtime = _runtime(ctx)
    path = runtime.config_path or default_config_path()
    config = AppConfig.load(path)
    data = {
        "config_file": str(path),
        "default_profile": config.default_profile,
        "profiles": {
            name: {
                "credentials_file": profile.credentials_file,
                "customer_id": profile.customer_id,
                "login_customer_id": profile.login_customer_id,
                "api_version": profile.api_version,
            }
            for name, profile in config.profiles.items()
        },
    }
    _output(ctx).render(data)


@auth_app.command("login")
def auth_login(
    ctx: typer.Context,
    client_secrets: Path = typer.Option(
        ..., "--client-secrets", exists=True, file_okay=True, dir_okay=False
    ),
    destination: Path | None = typer.Option(None, "--destination"),
    developer_token: str | None = typer.Option(
        None, "--developer-token", envvar="GOOGLE_ADS_DEVELOPER_TOKEN", hidden=True
    ),
    login_customer_id: str | None = typer.Option(None, "--login-customer-id"),
    customer_id: str | None = typer.Option(None, "--customer-id"),
    profile: str = typer.Option("default", "--profile-name"),
    no_browser: bool = typer.Option(False, "--no-browser"),
) -> None:
    token = developer_token or getpass.getpass("Google Ads developer token: ")
    credentials_path = destination or default_credentials_path()
    saved = oauth_login(
        client_secrets,
        credentials_path,
        token,
        login_customer_id=login_customer_id,
        open_browser=not no_browser,
    )
    runtime = _runtime(ctx)
    config_path_value = runtime.config_path or default_config_path()
    config = AppConfig.load(config_path_value, required=False)
    config.profiles[profile] = Profile(
        credentials_file=str(saved),
        customer_id=normalize_customer_id(customer_id) if customer_id else None,
        login_customer_id=(normalize_customer_id(login_customer_id) if login_customer_id else None),
        api_version=resolve_api_version(runtime.api_version()),
    )
    config.default_profile = profile
    config.save(config_path_value)
    _output(ctx).render(
        {
            "credentials_file": str(saved),
            "config_file": str(config_path_value),
            "profile": profile,
            "customer_id": config.profiles[profile].customer_id,
            "login_customer_id": config.profiles[profile].login_customer_id,
            "api_version": config.profiles[profile].api_version,
        }
    )


@auth_app.command("test")
def auth_test(ctx: typer.Context) -> None:
    runtime = _runtime(ctx)
    session = create_session(runtime)
    customer_service = session.client.get_service("CustomerService", version=session.api_version)
    accessible = customer_service.list_accessible_customers().resource_names
    query = (
        "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
        "customer.time_zone, customer.test_account, customer.manager FROM customer"
    )
    rows = run_gaql(session, query)
    _output(ctx).render(
        {
            "ok": True,
            "profile": session.profile_name,
            "api_version": session.api_version,
            "selected_customer_id": session.customer_id,
            "directly_accessible_customers": list(accessible),
            "selected_customer": rows,
        }
    )


@accounts_app.command("accessible")
def accounts_accessible(ctx: typer.Context) -> None:
    session = create_session(_runtime(ctx))
    service = session.client.get_service("CustomerService", version=session.api_version)
    rows = [
        {"resource_name": resource, "customer_id": resource.rsplit("/", 1)[-1]}
        for resource in service.list_accessible_customers().resource_names
    ]
    _output(ctx).render(rows, title="Directly accessible customers")


@accounts_app.command("show")
def accounts_show(ctx: typer.Context) -> None:
    session = create_session(_runtime(ctx))
    query = """
    SELECT
      customer.id,
      customer.descriptive_name,
      customer.currency_code,
      customer.time_zone,
      customer.test_account,
      customer.manager,
      customer.auto_tagging_enabled,
      customer.tracking_url_template
    FROM customer
    """
    _output(ctx).render(
        run_gaql(session, query),
        title=f"Customer {session.customer_id}",
        columns=selected_fields(query),
    )


@accounts_app.command("hierarchy")
def accounts_hierarchy(
    ctx: typer.Context,
    manager_id: str | None = typer.Option(None, "--manager-id"),
) -> None:
    runtime = _runtime(ctx)
    session = create_session(runtime, customer_id=manager_id or runtime.customer_id_override)
    seed = normalize_customer_id(manager_id) if manager_id else session.customer_id
    query = """
    SELECT
      customer_client.client_customer,
      customer_client.id,
      customer_client.level,
      customer_client.manager,
      customer_client.descriptive_name,
      customer_client.currency_code,
      customer_client.time_zone,
      customer_client.status,
      customer_client.test_account
    FROM customer_client
    WHERE customer_client.level <= 1
    """
    queue = [seed]
    visited: set[str] = set()
    rows: list[dict[str, Any]] = []
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        child_session = create_session(runtime, customer_id=current)
        for row in run_gaql(child_session, query):
            child = row.get("customer_client", {})
            child_id = str(child.get("id", ""))
            rows.append({"parent_customer_id": current, **child})
            if child.get("manager") and child.get("level") == "1" and child_id not in visited:
                queue.append(child_id)
    _output(ctx).render(rows, title=f"Account hierarchy from {seed}")


@query_app.command("run")
def query_run(
    ctx: typer.Context,
    query: str | None = typer.Argument(None),
    file: Path | None = typer.Option(None, "--file", "-i", exists=True),
    limit: int | None = typer.Option(None, "--limit", min=1),
) -> None:
    text = _read_query(query, file)
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, text, limit=limit),
        title=f"GAQL · customer {session.customer_id}",
        columns=selected_fields(text),
    )


@query_app.command("validate")
def query_validate(
    ctx: typer.Context,
    query: str | None = typer.Argument(None),
    file: Path | None = typer.Option(None, "--file", "-i", exists=True),
) -> None:
    text = _read_query(query, file)
    session = create_session(_runtime(ctx))
    validate_gaql(session, text)
    _output(ctx).render(
        {
            "valid": True,
            "customer_id": session.customer_id,
            "api_version": session.api_version,
        }
    )


@fields_app.command("describe")
def fields_describe(ctx: typer.Context, name: str = typer.Argument(...)) -> None:
    if not re.fullmatch(r"[a-z0-9_.]+", name):
        raise CliError("Field names may contain only lowercase letters, digits, `_`, and `.`.")
    session = create_session(_runtime(ctx))
    query = (
        "SELECT name, category, data_type, type_url, selectable, filterable, sortable, "
        f"selectable_with, attribute_resources, metrics, segments WHERE name = '{name}'"
    )
    _output(ctx).render(search_fields(session, query), title=f"Field: {name}")


@fields_app.command("search")
def fields_search(
    ctx: typer.Context,
    pattern: str = typer.Argument(..., help="For example campaign.%"),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.%]+", pattern):
        raise CliError("Field pattern contains unsupported characters.")
    if "%" not in pattern:
        pattern = f"{pattern}%"
    session = create_session(_runtime(ctx))
    query = (
        "SELECT name, category, data_type, selectable, filterable, sortable "
        f"WHERE name LIKE '{pattern}' LIMIT {limit}"
    )
    _output(ctx).render(search_fields(session, query), title=f"Fields: {pattern}")


@reports_app.command("list")
def reports_list(ctx: typer.Context) -> None:
    rows = [
        {"name": preset.name, "description": preset.description}
        for preset in REPORT_PRESETS.values()
    ]
    _output(ctx).render(rows, title="Report presets")


@reports_app.command("run")
def reports_run(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    date_range: str = typer.Option("LAST_30_DAYS", "--date-range"),
    limit: int | None = typer.Option(None, "--limit", min=1),
    show_query: bool = typer.Option(False, "--show-query"),
) -> None:
    query = render_report_query(name, date_range)
    if show_query:
        _output(ctx).render({"preset": name, "query": query})
        return
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query, limit=limit),
        title=f"{name} · {date_range}",
        columns=selected_fields(query),
    )


@campaigns_app.command("list")
def campaigns_list(
    ctx: typer.Context,
    include_removed: bool = typer.Option(False, "--include-removed"),
    channel: str | None = typer.Option(None, "--channel"),
) -> None:
    conditions = []
    if not include_removed:
        conditions.append("campaign.status != 'REMOVED'")
    if channel:
        if not re.fullmatch(r"[A-Z_]+", channel.upper()):
            raise CliError("Invalid channel enum.")
        conditions.append(f"campaign.advertising_channel_type = '{channel.upper()}'")
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
    SELECT
      campaign.id,
      campaign.resource_name,
      campaign.name,
      campaign.status,
      campaign.primary_status,
      campaign.advertising_channel_type,
      campaign.advertising_channel_sub_type,
      campaign.campaign_budget,
      campaign.start_date_time,
      campaign.end_date_time
    FROM campaign{where}
    ORDER BY campaign.id
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query),
        title="Campaigns",
        columns=selected_fields(query),
    )


@campaigns_app.command("get")
def campaigns_get(ctx: typer.Context, campaign_id: str = typer.Argument(...)) -> None:
    if not campaign_id.isdigit():
        raise CliError("Campaign ID must be numeric.")
    query = f"""
    SELECT
      campaign.id,
      campaign.resource_name,
      campaign.name,
      campaign.status,
      campaign.primary_status,
      campaign.primary_status_reasons,
      campaign.advertising_channel_type,
      campaign.advertising_channel_sub_type,
      campaign.campaign_budget,
      campaign.bidding_strategy_type,
      campaign.app_campaign_setting.app_id,
      campaign.app_campaign_setting.app_store,
      campaign.app_campaign_setting.bidding_strategy_goal_type,
      campaign.start_date_time,
      campaign.end_date_time
    FROM campaign
    WHERE campaign.id = {campaign_id}
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(run_gaql(session, query), title=f"Campaign {campaign_id}")


@campaigns_app.command("set-status")
def campaigns_set_status(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="ENABLED or PAUSED."),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    if not campaign_id.isdigit():
        raise CliError("Campaign ID must be numeric.")
    normalized_status = status.upper()
    if normalized_status not in {"ENABLED", "PAUSED"}:
        raise CliError("Status must be ENABLED or PAUSED.")
    customer_id = _runtime(ctx).customer_id()
    plan = MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="campaign",
                action="update",
                data={
                    "resourceName": f"customers/{customer_id}/campaigns/{campaign_id}",
                    "status": normalized_status,
                },
                update_mask=["status"],
            )
        ],
        label=f"campaigns.set-status.{normalized_status.lower()}",
    )
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@campaigns_app.command("remove")
def campaigns_remove(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    if not campaign_id.isdigit():
        raise CliError("Campaign ID must be numeric.")
    customer_id = _runtime(ctx).customer_id()
    plan = MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="campaign",
                action="remove",
                resource_name=f"customers/{customer_id}/campaigns/{campaign_id}",
            )
        ],
        label="campaigns.remove",
    )
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@campaigns_app.command("create-app")
def campaigns_create_app(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    app_id: str = typer.Option(..., "--app-id", help="Store ID; e.g. iOS numeric app ID."),
    app_store: str = typer.Option("APPLE_APP_STORE", "--app-store"),
    daily_budget: str = typer.Option(..., "--daily-budget", help="Account-currency amount."),
    goal: str = typer.Option("installs", "--goal", help=", ".join(GOAL_SETTINGS)),
    target_cpa: str | None = typer.Option(None, "--target-cpa"),
    target_roas: float | None = typer.Option(None, "--target-roas"),
    ad_group_name: str = typer.Option("Default", "--ad-group-name"),
    ad_name: str = typer.Option("Default App Ad", "--ad-name"),
    headline: list[str] = typer.Option(..., "--headline", help="Repeat 2-5 times."),
    description: list[str] = typer.Option(..., "--description", help="Repeat 2-5 times."),
    location: list[str] = typer.Option([], "--location", help="Geo constant ID/resource; repeat."),
    language: list[str] = typer.Option(
        [], "--language", help="Language constant ID/resource; repeat."
    ),
    conversion_action: list[str] = typer.Option([], "--conversion-action"),
    image_asset: list[str] = typer.Option([], "--image-asset"),
    video_asset: list[str] = typer.Option([], "--video-asset"),
    start_date_time: str | None = typer.Option(None, "--start-date-time"),
    end_date_time: str | None = typer.Option(None, "--end-date-time"),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    runtime = _runtime(ctx)
    plan = build_app_campaign_plan(
        AppCampaignSpec(
            customer_id=runtime.customer_id(),
            name=name,
            app_id=app_id,
            app_store=app_store,
            daily_budget=daily_budget,
            goal=goal,
            target_cpa=target_cpa,
            target_roas=target_roas,
            ad_group_name=ad_group_name,
            ad_name=ad_name,
            headlines=headline,
            descriptions=description,
            locations=location,
            languages=language,
            conversion_actions=conversion_action,
            image_assets=image_asset,
            video_assets=video_asset,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
        )
    )
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@budgets_app.command("list")
def budgets_list(
    ctx: typer.Context,
    include_removed: bool = typer.Option(False, "--include-removed"),
) -> None:
    where = "" if include_removed else " WHERE campaign_budget.status != 'REMOVED'"
    query = f"""
    SELECT
      campaign_budget.id,
      campaign_budget.resource_name,
      campaign_budget.name,
      campaign_budget.status,
      campaign_budget.amount_micros,
      campaign_budget.delivery_method,
      campaign_budget.explicitly_shared,
      campaign_budget.reference_count
    FROM campaign_budget{where}
    ORDER BY campaign_budget.id
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query), title="Campaign budgets", columns=selected_fields(query)
    )


@budgets_app.command("set-amount")
def budgets_set_amount(
    ctx: typer.Context,
    budget_id: str = typer.Argument(...),
    amount: str = typer.Argument(..., help="Daily amount in account currency."),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    from google_ads_cli.app_campaign import money_to_micros

    if not budget_id.isdigit():
        raise CliError("Budget ID must be numeric.")
    customer_id = _runtime(ctx).customer_id()
    plan = MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="campaign_budget",
                action="update",
                data={
                    "resourceName": f"customers/{customer_id}/campaignBudgets/{budget_id}",
                    "amountMicros": str(money_to_micros(amount, "budget amount")),
                },
                update_mask=["amount_micros"],
            )
        ],
        label="budgets.set-amount",
    )
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@adgroups_app.command("list")
def adgroups_list(
    ctx: typer.Context,
    campaign_id: str | None = typer.Option(None, "--campaign-id"),
    include_removed: bool = typer.Option(False, "--include-removed"),
) -> None:
    conditions = []
    if not include_removed:
        conditions.append("ad_group.status != 'REMOVED'")
    if campaign_id:
        if not campaign_id.isdigit():
            raise CliError("Campaign ID must be numeric.")
        conditions.append(f"campaign.id = {campaign_id}")
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
    SELECT
      campaign.id,
      campaign.name,
      ad_group.id,
      ad_group.resource_name,
      ad_group.name,
      ad_group.status,
      ad_group.primary_status,
      ad_group.type
    FROM ad_group{where}
    ORDER BY campaign.id, ad_group.id
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(run_gaql(session, query), title="Ad groups", columns=selected_fields(query))


@ads_app.command("list")
def ads_list(
    ctx: typer.Context,
    campaign_id: str | None = typer.Option(None, "--campaign-id"),
    ad_group_id: str | None = typer.Option(None, "--ad-group-id"),
    include_removed: bool = typer.Option(False, "--include-removed"),
) -> None:
    conditions = []
    if not include_removed:
        conditions.append("ad_group_ad.status != 'REMOVED'")
    for value, field, label in (
        (campaign_id, "campaign.id", "Campaign"),
        (ad_group_id, "ad_group.id", "Ad group"),
    ):
        if value:
            if not value.isdigit():
                raise CliError(f"{label} ID must be numeric.")
            conditions.append(f"{field} = {value}")
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
    SELECT
      campaign.id,
      campaign.name,
      ad_group.id,
      ad_group.name,
      ad_group_ad.ad.id,
      ad_group_ad.ad.resource_name,
      ad_group_ad.ad.name,
      ad_group_ad.ad.type,
      ad_group_ad.status,
      ad_group_ad.primary_status,
      ad_group_ad.policy_summary.approval_status
    FROM ad_group_ad{where}
    ORDER BY campaign.id, ad_group.id, ad_group_ad.ad.id
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(run_gaql(session, query), title="Ads", columns=selected_fields(query))


@assets_app.command("list")
def assets_list(
    ctx: typer.Context,
    asset_type: str | None = typer.Option(None, "--type"),
    limit: int | None = typer.Option(None, "--limit", min=1),
) -> None:
    where = ""
    if asset_type:
        if not re.fullmatch(r"[A-Z_]+", asset_type.upper()):
            raise CliError("Invalid asset type enum.")
        where = f" WHERE asset.type = '{asset_type.upper()}'"
    query = f"""
    SELECT
      asset.id,
      asset.resource_name,
      asset.name,
      asset.type,
      asset.source,
      asset.image_asset.file_size,
      asset.image_asset.mime_type,
      asset.image_asset.full_size.width_pixels,
      asset.image_asset.full_size.height_pixels,
      asset.youtube_video_asset.youtube_video_id,
      asset.youtube_video_asset.youtube_video_title
    FROM asset{where}
    ORDER BY asset.id
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query, limit=limit),
        title="Assets",
        columns=selected_fields(query),
    )


@assets_app.command("upload-image")
def assets_upload_image(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    name: str = typer.Option(..., "--name"),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    plan = image_upload_plan(_runtime(ctx).customer_id(), path, name)
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@assets_app.command("create-youtube")
def assets_create_youtube(
    ctx: typer.Context,
    video_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    plan = youtube_asset_plan(_runtime(ctx).customer_id(), video_id, name)
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@conversions_app.command("list")
def conversions_list(
    ctx: typer.Context,
    include_removed: bool = typer.Option(False, "--include-removed"),
) -> None:
    where = "" if include_removed else " WHERE conversion_action.status != 'REMOVED'"
    query = f"""
    SELECT
      conversion_action.id,
      conversion_action.resource_name,
      conversion_action.name,
      conversion_action.status,
      conversion_action.type,
      conversion_action.category,
      conversion_action.origin,
      conversion_action.primary_for_goal,
      conversion_action.include_in_conversions_metric
    FROM conversion_action{where}
    ORDER BY conversion_action.name
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query), title="Conversion actions", columns=selected_fields(query)
    )


@geo_app.command("suggest")
def geo_suggest(
    ctx: typer.Context,
    name: list[str] = typer.Argument(..., help="One or more location names."),
    country_code: str | None = typer.Option(None, "--country-code"),
    locale: str = typer.Option("en", "--locale"),
) -> None:
    session = create_session(_runtime(ctx))
    service = session.client.get_service("GeoTargetConstantService", version=session.api_version)
    request = session.client.get_type(
        "SuggestGeoTargetConstantsRequest", version=session.api_version
    )
    request.locale = locale
    if country_code:
        if not re.fullmatch(r"[A-Za-z]{2}", country_code):
            raise CliError("Country code must contain two letters.")
        request.country_code = country_code.upper()
    request.location_names.names.extend(name)
    response = service.suggest_geo_target_constants(request=request)
    _output(ctx).render(
        [message_to_dict(item) for item in response.geo_target_constant_suggestions],
        title="Geo target suggestions",
    )


@geo_app.command("languages")
def geo_languages(
    ctx: typer.Context,
    targetable_only: bool = typer.Option(True, "--targetable-only/--all"),
) -> None:
    where = " WHERE language_constant.targetable = TRUE" if targetable_only else ""
    query = f"""
    SELECT
      language_constant.id,
      language_constant.resource_name,
      language_constant.name,
      language_constant.code,
      language_constant.targetable
    FROM language_constant{where}
    ORDER BY language_constant.name
    """
    session = create_session(_runtime(ctx))
    _output(ctx).render(
        run_gaql(session, query), title="Language constants", columns=selected_fields(query)
    )


@mutate_app.command("apply")
def mutate_apply(
    ctx: typer.Context,
    file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    execute: bool = typer.Option(False, "--execute"),
    validate_only: bool = typer.Option(False, "--validate-only"),
) -> None:
    runtime = _runtime(ctx)
    explicit_customer = runtime.customer_id_override
    plan = load_mutation_plan(file, explicit_customer)
    _run_mutation(ctx, plan, execute=execute, validate_only=validate_only)


@mutate_app.command("schema")
def mutate_schema(ctx: typer.Context) -> None:
    version = resolve_api_version(_runtime(ctx).api_version())
    _output(ctx).render(
        {
            "api_version": version,
            "manifest": {
                "label": "descriptive-name",
                "customer_id": "1234567890",
                "api_version": version,
                "partial_failure": False,
                "response_content_type": "RESOURCE_NAME_ONLY",
                "operations": [
                    {
                        "resource": "campaign",
                        "action": "update",
                        "data": {
                            "resourceName": "customers/1234567890/campaigns/111",
                            "status": "PAUSED",
                        },
                        "update_mask": ["status"],
                    }
                ],
            },
            "safety": "Omit --execute for a local plan; use --validate-only for API validation.",
        }
    )


@audit_app.command("list")
def audit_list(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", min=1, max=10000),
) -> None:
    _output(ctx).render(read_audit(limit), title=f"Audit log · {default_audit_path()}")


def main() -> None:
    try:
        app()
    except GoogleAdsException as error:
        details = google_ads_error_details(error)
        Console(stderr=True, no_color="NO_COLOR" in os.environ).print(
            json.dumps(details, ensure_ascii=False, indent=2)
        )
        raise SystemExit(1) from error
    except CliError as error:
        Console(stderr=True, no_color="NO_COLOR" in os.environ).print(f"Error: {error}")
        if error.details is not None:
            Console(stderr=True).print(json.dumps(error.details, ensure_ascii=False, indent=2))
        raise SystemExit(error.exit_code) from error
    except KeyboardInterrupt as error:
        Console(stderr=True).print("Cancelled.")
        raise SystemExit(130) from error


if __name__ == "__main__":
    main()
