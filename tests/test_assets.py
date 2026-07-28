from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from google_ads_cli.ads_client import schema_client
from google_ads_cli.assets import image_upload_plan, youtube_asset_plan
from google_ads_cli.errors import CliError
from google_ads_cli.mutations import compile_operations, plan_preview


def test_image_plan_detects_dimensions_and_redacts_bytes(tmp_path: Path) -> None:
    path = tmp_path / "creative.png"
    Image.new("RGB", (1200, 628), color=(10, 20, 30)).save(path)
    plan = image_upload_plan("1234567890", path, "Landscape Creative")
    image_asset = plan.operations[0].data["imageAsset"]
    assert image_asset["fullSize"] == {
        "heightPixels": "628",
        "widthPixels": "1200",
    }
    assert image_asset["mimeType"] == "IMAGE_PNG"
    assert (
        "redacted-large-value"
        in plan_preview(plan, "v25")["operations"][0]["data"]["imageAsset"]["data"]
    )
    compile_operations(schema_client("v25"), plan.operations, api_version="v25")


def test_invalid_image_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-an-image.png"
    path.write_text("no", encoding="utf-8")
    with pytest.raises(CliError, match="invalid image"):
        image_upload_plan("1234567890", path, "Invalid")


def test_youtube_plan_is_v25_valid() -> None:
    plan = youtube_asset_plan("1234567890", "abc123", "Demo")
    compile_operations(schema_client("v25"), plan.operations, api_version="v25")
    with pytest.raises(CliError, match="not a full URL"):
        youtube_asset_plan("1234567890", "https://youtube.com/watch?v=abc", "Demo")
