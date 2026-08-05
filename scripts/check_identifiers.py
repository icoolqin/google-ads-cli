#!/usr/bin/env python3
"""Block real account identifiers from reaching a public repository.

`detect-secrets` finds credentials — API keys, tokens, private keys. It has no
concept of a *business* identifier, so a real Google Ads customer ID, ad ID,
account balance, or live ad headline sails straight through: to a credential
scanner they are just digits and prose.

This check closes that gap with two complementary rules:

1. **Denylist** — anything listed in `.private-values` (gitignored, never
   committed) fails immediately. Precise, no false positives, but only catches
   values someone remembered to write down.

2. **Allowlist** — every long digit run and every email address must appear in
   `.identifier-allowlist.txt`. This is the rule that catches identifiers nobody
   knew to add to the denylist yet, which is the case that actually leaks.

Rule 2 is deliberately noisy: adding a genuinely synthetic value costs one
reviewable line in the allowlist, and that line is exactly where a reviewer gets
to ask "is this real?".

Usage:
    python scripts/check_identifiers.py [FILE ...]

With no arguments every tracked file is scanned. pre-commit passes staged files.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / ".identifier-allowlist.txt"
PRIVATE_VALUES = REPO / ".private-values"

# Files that legitimately contain identifier-shaped noise, or define the rules.
SKIP_FILES = {
    ".identifier-allowlist.txt",
    ".private-values",
    ".private-values.example",
    ".secrets.baseline",
    "uv.lock",
    "scripts/check_identifiers.py",
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".whl", ".mp4"}

# 8+ consecutive digits: Google Ads customer/campaign/ad group/ad/asset IDs and
# micros amounts all land here.
DIGIT_RUN = re.compile(r"\d{8,}")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Google payments account / profile IDs, and anything card-shaped.
GROUPED_ID = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b")
# Python numeric separators must not hide an identifier: 2_830_190_000.
NUMERIC_SEPARATOR = re.compile(r"(?<=\d)_(?=\d)")


def load_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def scan(paths: list[str]) -> list[str]:
    allowed = load_lines(ALLOWLIST)
    private = load_lines(PRIVATE_VALUES)
    problems: list[str] = []

    for rel in paths:
        if rel in SKIP_FILES or Path(rel).suffix.lower() in SKIP_SUFFIXES:
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_no, line in enumerate(raw.splitlines(), start=1):
            for value in sorted(private):
                if value and value in line:
                    problems.append(
                        f"{rel}:{line_no}: real value from .private-values -> {value!r}\n"
                        f"    Replace it with a synthetic placeholder."
                    )
            normalized = NUMERIC_SEPARATOR.sub("", line)
            for match in DIGIT_RUN.finditer(normalized):
                value = match.group()
                if value not in allowed:
                    problems.append(
                        f"{rel}:{line_no}: unapproved long number -> {value}\n"
                        f"    If it is synthetic, add it to .identifier-allowlist.txt. "
                        f"If it came from a real account, replace it."
                    )
            for match in GROUPED_ID.finditer(line):
                if match.group() not in allowed:
                    problems.append(
                        f"{rel}:{line_no}: grouped ID (payments-account shaped) "
                        f"-> {match.group()}\n"
                        f"    Replace it unless it is synthetic and allowlisted."
                    )
            for match in EMAIL.finditer(line):
                if match.group() not in allowed:
                    problems.append(
                        f"{rel}:{line_no}: unapproved email -> {match.group()}\n"
                        f"    Add it to .identifier-allowlist.txt if it is meant to be public."
                    )
    return problems


def main() -> int:
    paths = sys.argv[1:] or tracked_files()
    problems = scan(paths)
    if not problems:
        return 0
    print("Real-identifier check failed:\n", file=sys.stderr)
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(
        f"\n{len(problems)} problem(s). This repository is public: a value committed here "
        "stays in git history even after a later fix.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
