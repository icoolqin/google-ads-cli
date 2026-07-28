from __future__ import annotations

import stat
from pathlib import Path

import pytest

from google_ads_cli.config import AppConfig, Profile, environment_profile
from google_ads_cli.errors import CliError
from google_ads_cli.runtime import normalize_customer_id


def test_config_round_trip_and_private_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    config = AppConfig(
        profiles={
            "default": Profile(
                credentials_file="/tmp/google-ads.yaml",
                customer_id="1234567890",
                login_customer_id="1111111111",
                api_version="v25",
            )
        }
    )
    assert config.save(path) == path
    loaded = AppConfig.load(path)
    assert loaded.profiles["default"].api_version == "v25"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("unknown: true\n", encoding="utf-8")
    with pytest.raises(CliError, match="Unknown config"):
        AppConfig.load(path)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("123-456-7890", "1234567890"), (1234567890, "1234567890")],
)
def test_customer_id_normalization(value: str | int, expected: str) -> None:
    assert normalize_customer_id(value) == expected


def test_invalid_customer_id_is_rejected() -> None:
    with pytest.raises(CliError, match="10 digits"):
        normalize_customer_id("123")


def test_service_account_environment_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "token")
    monkeypatch.setenv("GOOGLE_ADS_JSON_KEY_FILE_PATH", "/private/key.json")
    monkeypatch.setenv("GADS_CUSTOMER_ID", "1234567890")
    assert environment_profile() == Profile(customer_id="1234567890")
