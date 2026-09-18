"""Compatibility shim — implementation lives in ``services.t2i.wan_image_studio``."""

from services.t2i.wan_image_studio import (
    download_image,
    jpeg_data_url,
    poll_storyboard,
    submit_icon,
    submit_storyboard,
)

__all__ = [
    "download_image",
    "jpeg_data_url",
    "poll_storyboard",
    "submit_icon",
    "submit_storyboard",
]
