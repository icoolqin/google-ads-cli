from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_path

from google_ads_cli.errors import CliError

APP_NAME = "google-ads-cli"


def default_config_path() -> Path:
    override = os.getenv("GADS_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    return user_config_path(APP_NAME) / "config.yaml"


def default_credentials_path() -> Path:
    override = os.getenv("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
    if override:
        return Path(override).expanduser()
    return user_config_path(APP_NAME) / "google-ads.yaml"


@dataclass(slots=True)
class Profile:
    credentials_file: str | None = None
    customer_id: str | None = None
    login_customer_id: str | None = None
    api_version: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Profile:
        allowed = {item.name for item in cls.__dataclass_fields__.values()}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise CliError(f"Unknown profile setting(s): {', '.join(unknown)}")
        return cls(**raw)


@dataclass(slots=True)
class AppConfig:
    default_profile: str = "default"
    profiles: dict[str, Profile] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None, *, required: bool = True) -> AppConfig:
        config_path = path or default_config_path()
        if not config_path.exists():
            if required:
                raise CliError(
                    f"Config not found: {config_path}\n"
                    "Run `gads auth login ...` and `gads config init ...`, or set the "
                    "GOOGLE_ADS_* and GADS_CUSTOMER_ID environment variables."
                )
            return cls()
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            raise CliError(f"Could not read config {config_path}: {error}") from error
        if not isinstance(raw, dict):
            raise CliError(f"Config root must be a mapping: {config_path}")
        unknown = sorted(set(raw) - {"default_profile", "profiles"})
        if unknown:
            raise CliError(f"Unknown config setting(s): {', '.join(unknown)}")
        profiles_raw = raw.get("profiles") or {}
        if not isinstance(profiles_raw, dict):
            raise CliError("`profiles` must be a mapping")
        profiles = {}
        for name, profile_raw in profiles_raw.items():
            if not isinstance(name, str) or not isinstance(profile_raw, dict):
                raise CliError("Each profile must be a named mapping")
            profiles[name] = Profile.from_mapping(profile_raw)
        return cls(default_profile=str(raw.get("default_profile", "default")), profiles=profiles)

    def get_profile(self, name: str | None = None) -> tuple[str, Profile]:
        selected = name or self.default_profile
        try:
            return selected, self.profiles[selected]
        except KeyError as error:
            available = ", ".join(sorted(self.profiles)) or "(none)"
            raise CliError(f"Profile `{selected}` not found. Available: {available}") from error

    def save(self, path: Path | None = None) -> Path:
        config_path = path or default_config_path()
        config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        raw = {
            "default_profile": self.default_profile,
            "profiles": {name: asdict(profile) for name, profile in self.profiles.items()},
        }
        payload = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=config_path.parent,
                prefix=".config-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                temp_path = Path(handle.name)
            temp_path.chmod(0o600)
            temp_path.replace(config_path)
        except OSError as error:
            raise CliError(f"Could not write config {config_path}: {error}") from error
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
        return config_path


def environment_profile() -> Profile | None:
    oauth_ready = all(
        os.getenv(key)
        for key in (
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
        )
    )
    service_account_ready = bool(os.getenv("GOOGLE_ADS_JSON_KEY_FILE_PATH"))
    adc_ready = os.getenv("GOOGLE_ADS_USE_APPLICATION_DEFAULT_CREDENTIALS", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if not os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") or not (
        oauth_ready or service_account_ready or adc_ready
    ):
        return None
    return Profile(
        customer_id=os.getenv("GADS_CUSTOMER_ID"),
        login_customer_id=os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        api_version=os.getenv("GADS_API_VERSION"),
    )


def credentials_file_for(profile: Profile) -> Path | None:
    raw_path = profile.credentials_file or os.getenv("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
    return Path(raw_path).expanduser() if raw_path else None
