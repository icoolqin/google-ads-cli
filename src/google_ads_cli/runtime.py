from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google_ads_cli.config import AppConfig, Profile, environment_profile
from google_ads_cli.errors import CliError


def normalize_customer_id(value: str | int) -> str:
    normalized = str(value).replace("-", "").strip()
    if not normalized.isdigit() or len(normalized) != 10:
        raise CliError("Google Ads customer IDs must contain exactly 10 digits.")
    return normalized


@dataclass(slots=True)
class Runtime:
    config_path: Path | None
    profile_name: str | None
    customer_id_override: str | None
    api_version_override: str | None
    output_format: str
    no_color: bool
    verbose: bool

    def profile(self, *, required: bool = True) -> tuple[str, Profile]:
        path = self.config_path
        config = AppConfig.load(path, required=False)
        if config.profiles:
            return config.get_profile(self.profile_name)
        env_profile = environment_profile()
        if env_profile:
            return "environment", env_profile
        if required:
            target = path or "the default config path"
            raise CliError(
                f"No configured profile in {target}. Run `gads config init` or set "
                "GOOGLE_ADS_* credentials and GADS_CUSTOMER_ID."
            )
        return self.profile_name or "default", Profile()

    def customer_id(self, fallback: str | None = None) -> str:
        _, profile = self.profile(required=False)
        value = self.customer_id_override or fallback or profile.customer_id
        if not value:
            raise CliError(
                "No customer ID selected. Pass `--customer-id`, put `customer_id` in the "
                "profile, or set GADS_CUSTOMER_ID."
            )
        return normalize_customer_id(value)

    def api_version(self, fallback: str | None = None) -> str | None:
        _, profile = self.profile(required=False)
        return self.api_version_override or fallback or profile.api_version
