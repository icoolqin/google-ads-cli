from __future__ import annotations

from typing import Any

from google.ads.googleads.errors import GoogleAdsException


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
