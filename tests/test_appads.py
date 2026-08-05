from __future__ import annotations

import pytest

from google_ads_cli.ads_client import schema_client
from google_ads_cli.appads import (
    AppAdAssets,
    asset_id_from,
    coverage,
    describe_assets,
    image_orientation,
    infer_video_orientation,
    parse_app_ad,
    plan_app_ad_assets,
)
from google_ads_cli.errors import CliError
from google_ads_cli.mutations import compile_operations

CUSTOMER = "1234567890"


def _row(images: list[str], videos: list[str]) -> dict:
    return {
        "ad_group_ad": {
            "ad_strength": "EXCELLENT",
            "ad": {
                "id": "111222333444",
                "app_ad": {
                    "headlines": [{"text": "Example Headline"}],
                    "descriptions": [{"text": "Example description."}],
                    "images": [{"asset": f"customers/{CUSTOMER}/assets/{i}"} for i in images],
                    "youtube_videos": [
                        {"asset": f"customers/{CUSTOMER}/assets/{i}"} for i in videos
                    ],
                },
            },
        }
    }


def _current(images: list[str], videos: list[str]) -> AppAdAssets:
    return parse_app_ad(_row(images, videos))


def test_asset_id_accepts_both_forms() -> None:
    assert asset_id_from("123") == "123"
    assert asset_id_from(f"customers/{CUSTOMER}/assets/456") == "456"
    with pytest.raises(CliError, match="not an asset ID"):
        asset_id_from("assets/456")


def test_parse_app_ad_rejects_non_app_ads() -> None:
    with pytest.raises(CliError, match="not an App Ad"):
        parse_app_ad({"ad_group_ad": {"ad": {"id": "1", "app_ad": {}}}})


def test_image_orientation_matches_google_buckets() -> None:
    assert image_orientation(1200, 628) == "LANDSCAPE"
    assert image_orientation(1200, 1200) == "SQUARE"
    assert image_orientation(1200, 1500) == "PORTRAIT"
    assert image_orientation(None, 0) == "UNKNOWN"


def test_video_orientation_is_inferred_from_name() -> None:
    assert infer_video_orientation("promo_v01_9x16_11s") == "PORTRAIT"
    assert infer_video_orientation("promo_v04_1x1_11s") == "SQUARE"
    assert infer_video_orientation("promo_v07_16x9_11s") == "LANDSCAPE"
    assert infer_video_orientation("mystery-clip") == "UNKNOWN"


def test_explicit_ratio_beats_a_subject_word_in_the_name() -> None:
    # Creative names often use "portrait"/"landscape" for the subject, not the
    # aspect ratio. An explicit ratio token has to win.
    assert infer_video_orientation("promo_v06_portrait_1x1_11s") == "SQUARE"
    assert infer_video_orientation("promo_v09_portrait_16x9_11s") == "LANDSCAPE"
    assert infer_video_orientation("promo_v03_portrait_9x16_11s") == "PORTRAIT"
    # 1.91:1 is a landscape ratio and must not be read as 1:1.
    assert infer_video_orientation("banner_1.91x1") == "LANDSCAPE"
    # With no ratio anywhere, the word is all we have.
    assert infer_video_orientation("hero_landscape_cut") == "LANDSCAPE"


def test_coverage_reports_orientation_gaps() -> None:
    described = describe_assets(
        _current(["1"], ["2"]),
        [
            {
                "asset": {
                    "id": "1",
                    "name": "img",
                    "image_asset": {"full_size": {"width_pixels": 1200, "height_pixels": 628}},
                }
            },
            {
                "asset": {
                    "id": "2",
                    "name": "clip_9x16",
                    "youtube_video_asset": {"youtube_video_id": "abc"},
                }
            },
        ],
    )
    report = coverage(described, "EXCELLENT")
    assert report["image_orientations"] == {"LANDSCAPE": 1}
    assert report["video_orientations"] == {"PORTRAIT": 1}
    assert "no square image" in report["gaps"]
    assert "no landscape video" in report["gaps"]
    assert report["ad_strength"] == "EXCELLENT"


def test_missing_ad_strength_is_labelled_not_blank() -> None:
    assert coverage([], None)["ad_strength"].startswith("(not yet")


def test_delta_preserves_untouched_assets() -> None:
    current = _current(["1", "2", "3"], ["9"])
    plan, diff = plan_app_ad_assets(CUSTOMER, current, add_images=("4",), remove_images=("2",))
    images = plan.operations[0].data["appAd"]["images"]
    assert [item["asset"].rsplit("/", 1)[-1] for item in images] == ["1", "3", "4"]
    assert diff["images"] == {"before": 3, "after": 3, "added": ["4"], "removed": ["2"]}
    # Videos untouched, so they must stay out of the update mask entirely.
    assert plan.operations[0].update_mask == ["app_ad.images"]
    assert "youtubeVideos" not in plan.operations[0].data["appAd"]


def test_plan_is_valid_against_v25_schema() -> None:
    current = _current(["1"], ["9"])
    plan, _ = plan_app_ad_assets(CUSTOMER, current, add_videos=("10",))
    compile_operations(schema_client("v25"), plan.operations, api_version="v25")


def test_removing_an_absent_asset_is_rejected() -> None:
    current = _current(["1"], ["9"])
    with pytest.raises(CliError, match="not on the ad"):
        plan_app_ad_assets(CUSTOMER, current, remove_images=("42",))


def test_caps_are_enforced() -> None:
    current = _current([str(i) for i in range(20)], ["9"])
    with pytest.raises(CliError, match="at most 20 images"):
        plan_app_ad_assets(CUSTOMER, current, add_images=("999",))


def test_refuses_to_strip_all_visual_assets() -> None:
    current = _current(["1"], ["9"])
    with pytest.raises(CliError, match="no image and no video"):
        plan_app_ad_assets(CUSTOMER, current, set_images=(), set_videos=())


def test_set_and_add_are_mutually_exclusive() -> None:
    current = _current(["1"], ["9"])
    with pytest.raises(CliError, match="not both"):
        plan_app_ad_assets(CUSTOMER, current, add_images=("2",), set_images=("3",))


def test_noop_change_is_rejected() -> None:
    current = _current(["1"], ["9"])
    with pytest.raises(CliError, match="Nothing to change"):
        plan_app_ad_assets(CUSTOMER, current, add_images=("1",))


def test_duplicate_assets_are_rejected() -> None:
    current = _current(["1"], ["9"])
    with pytest.raises(CliError, match="Duplicate"):
        plan_app_ad_assets(CUSTOMER, current, set_images=("2", "2"))
