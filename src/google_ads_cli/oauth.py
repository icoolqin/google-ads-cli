from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml
from google_auth_oauthlib.flow import InstalledAppFlow

from google_ads_cli.errors import CliError
from google_ads_cli.runtime import normalize_customer_id

GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


def _client_info(path: Path) -> tuple[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CliError(f"Could not read OAuth client secrets {path}: {error}") from error
    client = raw.get("installed") or raw.get("web")
    if (
        not isinstance(client, dict)
        or not client.get("client_id")
        or not client.get("client_secret")
    ):
        raise CliError("OAuth JSON must contain an `installed` or `web` client configuration.")
    return str(client["client_id"]), str(client["client_secret"])


def login(
    client_secrets: Path,
    destination: Path,
    developer_token: str,
    *,
    login_customer_id: str | None,
    open_browser: bool,
) -> Path:
    if not developer_token.strip():
        raise CliError("Developer token cannot be empty.")
    client_id, client_secret = _client_info(client_secrets)
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), scopes=[GOOGLE_ADS_SCOPE])
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=open_browser,
        access_type="offline",
        # Google may otherwise silently reuse whichever account is already active
        # in the browser. Always show the account picker because the OAuth user,
        # developer-token owner, manager account, and target customer can differ.
        prompt="select_account consent",
        authorization_prompt_message="Open this URL to authorize Google Ads access:\n{url}",
        success_message="Google Ads authorization succeeded. You can close this tab.",
    )
    if not credentials.refresh_token:
        raise CliError(
            "Google did not return a refresh token. Revoke the app grant and retry with consent."
        )
    payload = {
        "developer_token": developer_token.strip(),
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": credentials.refresh_token,
        "use_proto_plus": True,
    }
    if login_customer_id:
        payload["login_customer_id"] = normalize_customer_id(login_customer_id)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".google-ads-",
            suffix=".yaml",
            delete=False,
        ) as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
            temp_path = Path(handle.name)
        temp_path.chmod(0o600)
        temp_path.replace(destination)
    except OSError as error:
        raise CliError(f"Could not write credentials to {destination}: {error}") from error
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    return destination
