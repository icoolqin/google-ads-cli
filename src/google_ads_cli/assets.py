from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from google_ads_cli.errors import CliError
from google_ads_cli.mutations import MutationOperation, MutationPlan

MIME_ENUMS = {
    "JPEG": "IMAGE_JPEG",
    "PNG": "IMAGE_PNG",
    "GIF": "IMAGE_GIF",
}


def image_upload_plan(customer_id: str, path: Path, name: str) -> MutationPlan:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise CliError(f"Could not read image {path}: {error}") from error
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise CliError(f"Unsupported or invalid image: {path}") from error
    if image_format not in MIME_ENUMS:
        raise CliError("Google Ads image assets must be JPEG, PNG, or GIF.")
    if not name.strip():
        raise CliError("Asset name cannot be empty.")
    return MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="asset",
                action="create",
                data={
                    "name": name,
                    "type": "IMAGE",
                    "imageAsset": {
                        "data": base64.b64encode(content).decode(),
                        "fileSize": str(len(content)),
                        "mimeType": MIME_ENUMS[image_format],
                        "fullSize": {
                            "heightPixels": str(height),
                            "widthPixels": str(width),
                        },
                    },
                },
            )
        ],
        response_content_type="MUTABLE_RESOURCE",
        label="assets.upload-image",
    )


def youtube_asset_plan(customer_id: str, video_id: str, name: str) -> MutationPlan:
    if not video_id.strip() or "/" in video_id:
        raise CliError("Pass a YouTube video ID, not a full URL.")
    return MutationPlan(
        customer_id=customer_id,
        operations=[
            MutationOperation(
                resource="asset",
                action="create",
                data={
                    "name": name,
                    "type": "YOUTUBE_VIDEO",
                    "youtubeVideoAsset": {"youtubeVideoId": video_id},
                },
            )
        ],
        response_content_type="MUTABLE_RESOURCE",
        label="assets.create-youtube",
    )
