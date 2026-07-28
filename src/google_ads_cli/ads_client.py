from __future__ import annotations

import pkgutil
import re
from dataclasses import dataclass

import google.ads.googleads as googleads_package
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

from google_ads_cli.config import credentials_file_for
from google_ads_cli.errors import CliError
from google_ads_cli.runtime import Runtime, normalize_customer_id


def supported_api_versions() -> list[str]:
    versions = [
        item.name
        for item in pkgutil.iter_modules(googleads_package.__path__)
        if re.fullmatch(r"v\d+", item.name)
    ]
    return sorted(versions, key=lambda value: int(value[1:]))


def resolve_api_version(requested: str | None) -> str:
    available = supported_api_versions()
    if not available:
        raise CliError("The installed google-ads package exposes no API versions.")
    version = requested or available[-1]
    if not version.startswith("v") and version.isdigit():
        version = f"v{version}"
    if version not in available:
        raise CliError(
            f"API version `{version}` is unavailable in the installed client. "
            f"Supported: {', '.join(available)}"
        )
    return version


def schema_client(version: str | None = None) -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="schema-only",
        version=resolve_api_version(version),
        use_proto_plus=True,
    )


@dataclass(slots=True)
class AdsSession:
    client: GoogleAdsClient
    customer_id: str
    api_version: str
    profile_name: str


def create_session(
    runtime: Runtime,
    *,
    customer_id: str | None = None,
    api_version: str | None = None,
) -> AdsSession:
    profile_name, profile = runtime.profile()
    selected_customer_id = (
        normalize_customer_id(customer_id) if customer_id else runtime.customer_id()
    )
    version = resolve_api_version(runtime.api_version(api_version))
    credentials_file = credentials_file_for(profile)
    if credentials_file:
        if not credentials_file.exists():
            raise CliError(f"Google Ads credentials file not found: {credentials_file}")
        client = GoogleAdsClient.load_from_storage(str(credentials_file), version=version)
    else:
        try:
            client = GoogleAdsClient.load_from_env(version=version)
        except ValueError as error:
            raise CliError(
                "No credentials file is configured and GOOGLE_ADS_* credentials are incomplete."
            ) from error
    if profile.login_customer_id:
        client.login_customer_id = normalize_customer_id(profile.login_customer_id)
    return AdsSession(
        client=client,
        customer_id=selected_customer_id,
        api_version=version,
        profile_name=profile_name,
    )
