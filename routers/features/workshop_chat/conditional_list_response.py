"""
Shared conditional GET (ETag / 304) JSON response for workshop list routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from services.features.workshop_chat.workshop_list_etag import etag_is_not_modified


def workshop_list_json_response(
    request: Request,
    etag: str,
    build_body: Callable[[], Any],
) -> Response | JSONResponse:
    """Return 304 if If-None-Match matches, else JSON body with ETag headers."""
    headers = {
        "ETag": etag,
        "Cache-Control": "private, no-store",
    }
    if etag_is_not_modified(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return JSONResponse(content=build_body(), headers=headers)
