from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "google-ads"


def test_skill_has_valid_frontmatter_and_references() -> None:
    content = (SKILL_DIR / "SKILL.md").read_text()
    delimiter, frontmatter, body = content.split("---", 2)
    assert delimiter == ""

    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "google-ads"
    assert "Google Ads" in metadata["description"]
    assert "gads" in metadata["description"]

    assert "[setup.md](references/setup.md)" in body
    assert "[operations.md](references/operations.md)" in body
    assert (SKILL_DIR / "references" / "setup.md").is_file()
    assert (SKILL_DIR / "references" / "operations.md").is_file()


def test_skill_interface_matches_skill_name() -> None:
    metadata = yaml.safe_load((SKILL_DIR / "agents" / "openai.yaml").read_text())
    interface = metadata["interface"]
    assert 25 <= len(interface["short_description"]) <= 64
    assert "$google-ads" in interface["default_prompt"]
