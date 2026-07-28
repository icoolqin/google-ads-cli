from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platformdirs import user_state_path

from google_ads_cli.config import APP_NAME


def default_audit_path() -> Path:
    override = os.getenv("GADS_AUDIT_FILE")
    if override:
        return Path(override).expanduser()
    return user_state_path(APP_NAME) / "audit.jsonl"


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def append_audit(record: dict[str, Any], path: Path | None = None) -> None:
    audit_path = path or default_audit_path()
    audit_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    enriched = {
        "timestamp": datetime.now(UTC).isoformat(),
        **record,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        if audit_path.stat().st_size == 0:
            audit_path.chmod(0o600)
        handle.write(json.dumps(enriched, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def read_audit(limit: int = 50, path: Path | None = None) -> list[dict[str, Any]]:
    audit_path = path or default_audit_path()
    if not audit_path.exists():
        return []
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"malformed_record": line})
    return records
