"""Tests for the real-identifier guard.

This file is scanned by the very check it tests, so **no literal 8+ digit run,
grouped ID, or email address may appear in the source**. Sample values are
assembled from fragments at runtime instead. That constraint is the point: a
test about catching identifiers must not be the thing that publishes one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "check_identifiers", REPO / "scripts" / "check_identifiers.py"
)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

# Assembled so the literals never appear in this file. All are invented.
DENIED_ID = "9999" + "888877"
UNKNOWN_ID = "7777" + "6666" + "5555"
SEPARATED = "1_234_" + "500_000"
SEPARATED_FLAT = "1234" + "500000"
GROUPED = "1111-2222-" + "3333-4444"
EMAIL = "ops@" + "invented-company.example"
ALLOWED_ID = "1234567890"  # already in the repo allowlist


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point the checker at a scratch repo with its own allowlist/denylist."""
    monkeypatch.setattr(checker, "REPO", tmp_path)
    monkeypatch.setattr(checker, "ALLOWLIST", tmp_path / ".identifier-allowlist.txt")
    monkeypatch.setattr(checker, "PRIVATE_VALUES", tmp_path / ".private-values")
    (tmp_path / ".identifier-allowlist.txt").write_text(f"{ALLOWED_ID}\n", encoding="utf-8")
    (tmp_path / ".private-values").write_text(f"# comment\n{DENIED_ID}\n", encoding="utf-8")
    return tmp_path


def _write(repo: Path, name: str, body: str) -> str:
    (repo / name).write_text(body, encoding="utf-8")
    return name


def test_allowlisted_placeholder_passes(repo) -> None:
    name = _write(repo, "doc.md", f"gads --customer-id {ALLOWED_ID}\n")
    assert checker.scan([name]) == []


def test_unknown_long_number_is_flagged(repo) -> None:
    # Not in .private-values: this is the rule that catches identifiers nobody
    # knew to write down yet, which is the case that actually leaks.
    name = _write(repo, "doc.md", f"gads ads assets {UNKNOWN_ID}\n")
    problems = checker.scan([name])
    assert len(problems) == 1
    assert UNKNOWN_ID in problems[0]


def test_known_private_value_is_flagged_by_both_rules(repo) -> None:
    name = _write(repo, "doc.md", f"customer {DENIED_ID}\n")
    problems = checker.scan([name])
    assert any(".private-values" in p for p in problems)
    assert any("unapproved long number" in p for p in problems)


def test_numeric_separators_cannot_hide_an_identifier(repo) -> None:
    name = _write(repo, "test_x.py", f"limit = {SEPARATED}\n")
    assert any(SEPARATED_FLAT in p for p in checker.scan([name]))


def test_grouped_payments_id_is_flagged(repo) -> None:
    name = _write(repo, "doc.md", f"payments account {GROUPED}\n")
    assert any("grouped ID" in p for p in checker.scan([name]))


def test_unapproved_email_is_flagged(repo) -> None:
    name = _write(repo, "doc.md", f"contact {EMAIL}\n")
    assert any("unapproved email" in p for p in checker.scan([name]))


def test_allowlist_and_denylist_files_are_not_scanned(repo) -> None:
    assert checker.scan([".identifier-allowlist.txt", ".private-values"]) == []


def test_short_numbers_and_dates_do_not_trip_it(repo) -> None:
    name = _write(repo, "CHANGELOG.md", "## [0.2.0] - 2026-08-04\nport 8080, id 1234567\n")
    assert checker.scan([name]) == []


def test_binary_files_are_skipped(repo) -> None:
    (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + DENIED_ID.encode())
    assert checker.scan(["logo.png"]) == []


def test_repository_itself_is_clean() -> None:
    """The guard that matters: the committed tree carries no unapproved identifiers."""
    assert checker.scan(checker.tracked_files()) == []
