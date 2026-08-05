"""App Ad asset inspection and safe in-place asset edits.

Two things this module exists for:

1. **`ad_group_ad_asset_view` is not the source of truth.** It keeps historical
   associations, so it can report more assets than the ad actually carries.
   Read `ad_group_ad.ad.app_ad.*` instead — that is what these queries do.

2. **App Ad asset fields are whole-field replacements.** Updating
   `app_ad.images` with an `update_mask` replaces the entire list, so any asset
   omitted from the payload is silently dropped. `plan_app_ad_assets` builds the
   full replacement from the ad's current state plus an explicit delta, which
   removes that footgun.

The App Ad itself cannot be created a second time in one ad group, nor removed.
Editing its assets in place is therefore the only non-destructive iteration path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from google_ads_cli.errors import CliError
from google_ads_cli.mutations import MutationOperation, MutationPlan

# Per-ad-group caps for App campaigns (Google Ads limits).
LIMITS = {"headlines": 5, "descriptions": 5, "images": 20, "youtube_videos": 20}

APP_AD_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  ad_group.id,
  ad_group.name,
  ad_group_ad.ad.id,
  ad_group_ad.ad.name,
  ad_group_ad.status,
  ad_group_ad.ad_strength,
  ad_group_ad.policy_summary.approval_status,
  ad_group_ad.policy_summary.review_status,
  ad_group_ad.ad.app_ad.headlines,
  ad_group_ad.ad.app_ad.descriptions,
  ad_group_ad.ad.app_ad.images,
  ad_group_ad.ad.app_ad.youtube_videos
FROM ad_group_ad
WHERE ad_group_ad.ad.id = {ad_id}
"""

ASSET_DETAIL_QUERY = """
SELECT
  asset.id,
  asset.name,
  asset.type,
  asset.image_asset.full_size.width_pixels,
  asset.image_asset.full_size.height_pixels,
  asset.youtube_video_asset.youtube_video_id,
  asset.youtube_video_asset.youtube_video_title
FROM asset
WHERE asset.id IN ({asset_ids})
"""

# Explicit aspect-ratio tokens are checked before English orientation words:
# creative names routinely use "portrait" or "landscape" to mean the *subject*
# (a portrait shoot, a landscape scene), which would otherwise win over the real
# ratio in a name like "V09_Portrait_16x9". Landscape ratios are checked before
# square so that "1.91x1" is not read as "1x1".
_RATIO_TOKENS = (
    ("LANDSCAPE", (r"1\.91[x:_-]1", r"16[x:_-]9")),
    ("PORTRAIT", (r"9[x:_-]16", r"4[x:_-]5", r"2[x:_-]3")),
    ("SQUARE", (r"(?<![\d.])1[x:_-]1(?!\d)",)),
)
_WORD_TOKENS = (
    ("PORTRAIT", (r"vertical", r"portrait")),
    ("SQUARE", (r"square",)),
    ("LANDSCAPE", (r"landscape", r"horizontal")),
)


@dataclass(slots=True)
class AppAdAssets:
    """The asset lists an App Ad currently carries."""

    ad_id: str
    headlines: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    youtube_videos: list[str] = field(default_factory=list)


def asset_id_from(value: str) -> str:
    """Accept either a bare numeric asset ID or a full asset resource name."""
    text = str(value).strip()
    if text.isdigit():
        return text
    match = re.fullmatch(r"customers/\d+/assets/(\d+)", text)
    if match:
        return match.group(1)
    raise CliError(f"`{value}` is not an asset ID or an asset resource name.")


def parse_app_ad(row: dict[str, Any]) -> AppAdAssets:
    ad = ((row.get("ad_group_ad") or {}).get("ad")) or {}
    app_ad = ad.get("app_ad") or {}
    if not app_ad:
        raise CliError(
            f"Ad {ad.get('id', '?')} is not an App Ad (no app_ad payload). "
            "These commands only apply to App campaign ads."
        )
    return AppAdAssets(
        ad_id=str(ad.get("id") or ""),
        headlines=[item.get("text", "") for item in app_ad.get("headlines", [])],
        descriptions=[item.get("text", "") for item in app_ad.get("descriptions", [])],
        images=[
            asset_id_from(item["asset"]) for item in app_ad.get("images", []) if "asset" in item
        ],
        youtube_videos=[
            asset_id_from(item["asset"])
            for item in app_ad.get("youtube_videos", [])
            if "asset" in item
        ],
    )


def image_orientation(width: Any, height: Any) -> str:
    try:
        ratio = int(width) / int(height)
    except (TypeError, ValueError, ZeroDivisionError):
        return "UNKNOWN"
    if ratio >= 1.2:
        return "LANDSCAPE"
    if ratio >= 0.9:
        return "SQUARE"
    return "PORTRAIT"


def infer_video_orientation(name: str | None) -> str:
    """Guess a YouTube asset's orientation from its name.

    The Google Ads API does not expose a video's aspect ratio, so this is a
    naming-convention heuristic. Results are always labelled as inferred.

    An explicit ratio anywhere in the name wins; bare words like "portrait" are
    only a fallback, because they are just as often describing the subject.
    """
    text = (name or "").lower()
    for tokens in (_RATIO_TOKENS, _WORD_TOKENS):
        for orientation, patterns in tokens:
            for pattern in patterns:
                if re.search(pattern, text):
                    return orientation
    return "UNKNOWN"


def describe_assets(assets: AppAdAssets, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join the ad's asset IDs against asset metadata, adding orientation."""
    by_id = {str((row.get("asset") or {}).get("id")): row.get("asset") or {} for row in details}
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(assets.headlines, start=1):
        rows.append({"slot": f"headline {index}", "kind": "HEADLINE", "value": text})
    for index, text in enumerate(assets.descriptions, start=1):
        rows.append({"slot": f"description {index}", "kind": "DESCRIPTION", "value": text})
    for asset_id in assets.images:
        detail = by_id.get(asset_id, {})
        size = (detail.get("image_asset") or {}).get("full_size") or {}
        width, height = size.get("width_pixels"), size.get("height_pixels")
        rows.append(
            {
                "slot": "image",
                "kind": "IMAGE",
                "asset_id": asset_id,
                "name": detail.get("name"),
                "dimensions": f"{width}x{height}" if width and height else None,
                "orientation": image_orientation(width, height),
                "orientation_source": "pixels",
            }
        )
    for asset_id in assets.youtube_videos:
        detail = by_id.get(asset_id, {})
        video = detail.get("youtube_video_asset") or {}
        rows.append(
            {
                "slot": "video",
                "kind": "YOUTUBE_VIDEO",
                "asset_id": asset_id,
                "name": detail.get("name"),
                "youtube_video_id": video.get("youtube_video_id"),
                "youtube_title": video.get("youtube_video_title"),
                "orientation": infer_video_orientation(detail.get("name")),
                "orientation_source": "inferred-from-name",
            }
        )
    return rows


def coverage(described: list[dict[str, Any]], ad_strength: str | None) -> dict[str, Any]:
    """Slot fill plus per-orientation coverage, with the gaps spelled out."""

    def _count(kind: str) -> int:
        return sum(1 for row in described if row["kind"] == kind)

    def _orientations(kind: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in described:
            if row["kind"] == kind:
                counts[row["orientation"]] = counts.get(row["orientation"], 0) + 1
        return counts

    image_orientations = _orientations("IMAGE")
    video_orientations = _orientations("YOUTUBE_VIDEO")
    gaps: list[str] = []
    for label, counts in (("image", image_orientations), ("video", video_orientations)):
        for orientation in ("LANDSCAPE", "SQUARE", "PORTRAIT"):
            if not counts.get(orientation):
                gaps.append(f"no {orientation.lower()} {label}")
    for kind, key in (
        ("HEADLINE", "headlines"),
        ("DESCRIPTION", "descriptions"),
        ("IMAGE", "images"),
        ("YOUTUBE_VIDEO", "youtube_videos"),
    ):
        used = _count(kind)
        if used < LIMITS[key]:
            gaps.append(f"{key} {used}/{LIMITS[key]}")

    return {
        "ad_strength": ad_strength or "(not yet computed by Google)",
        "headlines": f"{_count('HEADLINE')}/{LIMITS['headlines']}",
        "descriptions": f"{_count('DESCRIPTION')}/{LIMITS['descriptions']}",
        "images": f"{_count('IMAGE')}/{LIMITS['images']}",
        "image_orientations": image_orientations,
        "videos": f"{_count('YOUTUBE_VIDEO')}/{LIMITS['youtube_videos']}",
        "video_orientations": video_orientations,
        "gaps": gaps or ["none"],
        "note": (
            "Video orientation is inferred from asset names; the API does not expose "
            "video aspect ratio. Google's own per-orientation Ad Strength breakdown is "
            "only available in the web UI (asset_group.asset_coverage is Performance Max only)."
        ),
    }


def _apply_delta(
    current: list[str],
    *,
    add: tuple[str, ...],
    remove: tuple[str, ...],
    replace: tuple[str, ...] | None,
    label: str,
) -> list[str]:
    if replace is not None:
        if add or remove:
            raise CliError(f"Use either --set-{label} or --add/--remove-{label}, not both.")
        result = [asset_id_from(value) for value in replace]
    else:
        removals = {asset_id_from(value) for value in remove}
        unknown = removals - set(current)
        if unknown:
            raise CliError(
                f"Cannot remove {label} asset(s) not on the ad: {', '.join(sorted(unknown))}"
            )
        result = [value for value in current if value not in removals]
        for value in add:
            asset_id = asset_id_from(value)
            if asset_id not in result:
                result.append(asset_id)
    duplicates = {value for value in result if result.count(value) > 1}
    if duplicates:
        raise CliError(f"Duplicate {label} asset(s): {', '.join(sorted(duplicates))}")
    return result


def plan_app_ad_assets(
    customer_id: str,
    current: AppAdAssets,
    *,
    add_images: tuple[str, ...] = (),
    remove_images: tuple[str, ...] = (),
    set_images: tuple[str, ...] | None = None,
    add_videos: tuple[str, ...] = (),
    remove_videos: tuple[str, ...] = (),
    set_videos: tuple[str, ...] | None = None,
    set_headlines: tuple[str, ...] | None = None,
    set_descriptions: tuple[str, ...] | None = None,
) -> tuple[MutationPlan, dict[str, Any]]:
    """Build a whole-field replacement from the ad's current state plus a delta."""
    images = _apply_delta(
        current.images, add=add_images, remove=remove_images, replace=set_images, label="image"
    )
    videos = _apply_delta(
        current.youtube_videos,
        add=add_videos,
        remove=remove_videos,
        replace=set_videos,
        label="video",
    )
    headlines = list(set_headlines) if set_headlines is not None else current.headlines
    descriptions = list(set_descriptions) if set_descriptions is not None else current.descriptions

    for values, key in (
        (headlines, "headlines"),
        (descriptions, "descriptions"),
        (images, "images"),
        (videos, "youtube_videos"),
    ):
        if len(values) > LIMITS[key]:
            raise CliError(f"App ads allow at most {LIMITS[key]} {key} ({len(values)} requested).")
    if not images and not videos:
        raise CliError("Refusing to leave the ad with no image and no video assets.")
    if not headlines or not descriptions:
        raise CliError("App ads require at least one headline and one description.")

    app_ad: dict[str, Any] = {}
    update_mask: list[str] = []
    diff: dict[str, Any] = {}

    if images != current.images:
        app_ad["images"] = [{"asset": f"customers/{customer_id}/assets/{i}"} for i in images]
        update_mask.append("app_ad.images")
        diff["images"] = {
            "before": len(current.images),
            "after": len(images),
            "added": sorted(set(images) - set(current.images)),
            "removed": sorted(set(current.images) - set(images)),
        }
    if videos != current.youtube_videos:
        app_ad["youtubeVideos"] = [{"asset": f"customers/{customer_id}/assets/{i}"} for i in videos]
        update_mask.append("app_ad.youtube_videos")
        diff["youtube_videos"] = {
            "before": len(current.youtube_videos),
            "after": len(videos),
            "added": sorted(set(videos) - set(current.youtube_videos)),
            "removed": sorted(set(current.youtube_videos) - set(videos)),
        }
    if headlines != current.headlines:
        app_ad["headlines"] = [{"text": text} for text in headlines]
        update_mask.append("app_ad.headlines")
        diff["headlines"] = {"before": current.headlines, "after": headlines}
    if descriptions != current.descriptions:
        app_ad["descriptions"] = [{"text": text} for text in descriptions]
        update_mask.append("app_ad.descriptions")
        diff["descriptions"] = {"before": current.descriptions, "after": descriptions}

    if not update_mask:
        raise CliError("Nothing to change: the requested asset set matches the ad already.")

    plan = MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="ad",
                action="update",
                data={
                    "resourceName": f"customers/{customer_id}/ads/{current.ad_id}",
                    "appAd": app_ad,
                },
                update_mask=update_mask,
            )
        ],
        label="ads.set-assets",
    )
    return plan, diff
