from __future__ import annotations

from typing import Any

from google.ads.googleads.errors import GoogleAdsException
from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError, ServiceUnavailable
from google.auth.exceptions import RefreshError


class CliError(RuntimeError):
    """An expected, user-actionable CLI error."""

    def __init__(self, message: str, *, exit_code: int = 2, details: Any = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.details = details


def google_ads_error_details(error: GoogleAdsException) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for google_error in error.failure.errors:
        code_message = google_error.error_code._pb
        code_field = code_message.WhichOneof("error_code")
        code_value = getattr(google_error.error_code, code_field) if code_field else None
        location = [
            {
                "field": element.field_name,
                "index": element.index if element.index else None,
            }
            for element in google_error.location.field_path_elements
        ]
        items.append(
            {
                "code": code_field,
                "code_value": str(code_value) if code_value is not None else None,
                "message": google_error.message,
                "trigger": google_error.trigger.string_value or None,
                "location": location,
            }
        )
    return {
        "request_id": error.request_id,
        "message": str(error),
        "errors": items,
    }


def google_api_error_details(error: GoogleAPICallError) -> dict[str, Any]:
    """Render transport/API-core failures without exposing a Python traceback."""
    code = error.code
    if callable(code):
        code = code()
    details = {
        "type": type(error).__name__,
        "code": str(code) if code is not None else None,
        "message": str(error),
    }
    if isinstance(error, (ServiceUnavailable, DeadlineExceeded)):
        details["help"] = (
            "Google Ads could not be reached. Check DNS, VPN/proxy, firewall, and IPv6 "
            "routing, then retry. On custom networks you can also try "
            "`GRPC_DNS_RESOLVER=native gads auth test`."
        )
    return details


def oauth_refresh_error_details(error: RefreshError) -> dict[str, Any]:
    return {
        "type": type(error).__name__,
        "message": str(error),
        "help": (
            "Run `gads auth login` again and choose a Google user that can directly access "
            "the configured manager account. If the OAuth app is in Testing, add that user "
            "to Google Auth Platform > Audience > Test users first."
        ),
    }
