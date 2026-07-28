from __future__ import annotations

import json

from typer.testing import CliRunner

from google_ads_cli.cli import app
from google_ads_cli.errors import CliError

runner = CliRunner()


def test_version_lists_v25_schema() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "v25" in result.stdout


def test_create_app_defaults_to_plan_without_credentials() -> None:
    result = runner.invoke(
        app,
        [
            "--customer-id",
            "1234567890",
            "--format",
            "json",
            "campaigns",
            "create-app",
            "--name",
            "Example App Plan",
            "--app-id",
            "123456789",
            "--daily-budget",
            "50",
            "--target-cpa",
            "2.5",
            "--headline",
            "AI Photo Magic",
            "--headline",
            "One Shot, Endless Wonder",
            "--description",
            "Turn one photo into endless creative styles.",
            "--description",
            "Create, remix, and share in seconds.",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "plan"
    assert payload["operations"][1]["data"]["status"] == "PAUSED"


def test_execute_and_validate_only_are_mutually_exclusive() -> None:
    result = runner.invoke(
        app,
        [
            "--customer-id",
            "1234567890",
            "campaigns",
            "set-status",
            "1",
            "PAUSED",
            "--execute",
            "--validate-only",
        ],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CliError)
