from __future__ import annotations

import json
import stat
from pathlib import Path
from types import SimpleNamespace

import yaml
from google.api_core.exceptions import ServiceUnavailable
from google.auth.exceptions import RefreshError
from typer.testing import CliRunner

import google_ads_cli.cli as cli
import google_ads_cli.oauth as oauth
from google_ads_cli.ads_client import AdsSession
from google_ads_cli.errors import (
    CliError,
    google_api_error_details,
    oauth_refresh_error_details,
)

runner = CliRunner()


def _client_secret_file(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "example.apps.googleusercontent.com",
                    "client_secret": "not-a-real-secret",  # pragma: allowlist secret
                }
            }
        )
    )
    return path


def test_oauth_login_forces_account_picker_and_secures_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    calls: dict[str, object] = {}

    class FakeFlow:
        def run_local_server(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(refresh_token="fake-refresh-token")

    monkeypatch.setattr(
        oauth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda *args, **kwargs: FakeFlow(),
    )
    destination = tmp_path / "google-ads.yaml"

    oauth.login(
        _client_secret_file(tmp_path / "client.json"),
        destination,
        "fake-developer-token",
        login_customer_id="111-111-1111",
        open_browser=True,
    )

    assert calls["prompt"] == "select_account consent"
    assert calls["access_type"] == "offline"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    payload = yaml.safe_load(destination.read_text())
    assert payload["login_customer_id"] == "1111111111"
    assert payload["refresh_token"] == "fake-refresh-token"


def test_auth_test_rejects_oauth_user_without_direct_manager_access(monkeypatch) -> None:
    customer_service = SimpleNamespace(
        list_accessible_customers=lambda: SimpleNamespace(resource_names=["customers/3333333333"])
    )
    client = SimpleNamespace(
        login_customer_id="1111111111",
        get_service=lambda *args, **kwargs: customer_service,
    )
    session = AdsSession(
        client=client,
        customer_id="2222222222",
        api_version="v25",
        profile_name="default",
    )
    monkeypatch.setattr(cli, "create_session", lambda runtime: session)

    result = runner.invoke(cli.app, ["auth", "test"])

    assert result.exit_code != 0
    assert isinstance(result.exception, CliError)
    assert "cannot directly access" in str(result.exception)
    assert result.exception.details["configured_login_customer_id"] == "1111111111"


def test_auth_test_reports_verified_manager_relationship(monkeypatch) -> None:
    customer_service = SimpleNamespace(
        list_accessible_customers=lambda: SimpleNamespace(resource_names=["customers/1111111111"])
    )
    client = SimpleNamespace(
        login_customer_id="1111111111",
        get_service=lambda *args, **kwargs: customer_service,
    )
    session = AdsSession(
        client=client,
        customer_id="2222222222",
        api_version="v25",
        profile_name="default",
    )
    monkeypatch.setattr(cli, "create_session", lambda runtime: session)
    monkeypatch.setattr(cli, "run_gaql", lambda session, query: [{"customer": {"id": "2"}}])

    result = runner.invoke(cli.app, ["--format", "json", "auth", "test"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["login_customer_accessible"] is True
    assert payload["login_customer_id"] == "1111111111"


def test_transport_and_refresh_errors_include_actionable_help() -> None:
    transport = google_api_error_details(ServiceUnavailable("DNS lookup failed"))
    refresh = oauth_refresh_error_details(RefreshError("invalid_grant"))

    assert transport["type"] == "ServiceUnavailable"
    assert "GRPC_DNS_RESOLVER=native" in transport["help"]
    assert refresh["type"] == "RefreshError"
    assert "gads auth login" in refresh["help"]
