from __future__ import annotations

import re
from typing import Any

from google_ads_cli.ads_client import AdsSession
from google_ads_cli.output import message_to_dict


def selected_fields(query: str) -> list[str]:
    match = re.search(r"\bSELECT\b(.*?)\bFROM\b", query, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    return [field.strip() for field in match.group(1).split(",") if field.strip()]


def run_gaql(
    session: AdsSession,
    query: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    service = session.client.get_service("GoogleAdsService", version=session.api_version)
    responses = service.search_stream(customer_id=session.customer_id, query=query)
    rows: list[dict[str, Any]] = []
    for response in responses:
        for row in response.results:
            rows.append(message_to_dict(row))
            if limit is not None and len(rows) >= limit:
                return rows
    return rows


def validate_gaql(session: AdsSession, query: str) -> None:
    service = session.client.get_service("GoogleAdsService", version=session.api_version)
    request = session.client.get_type("SearchGoogleAdsRequest", version=session.api_version)
    request.customer_id = session.customer_id
    request.query = query
    request.validate_only = True
    service.search(request=request)


def search_fields(session: AdsSession, query: str) -> list[dict[str, Any]]:
    service = session.client.get_service("GoogleAdsFieldService", version=session.api_version)
    response = service.search_google_ads_fields(query=query)
    return [message_to_dict(field) for field in response]
