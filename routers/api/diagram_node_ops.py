"""Diagram node patch and PNG preview for OpenClaw / API clients."""

import copy
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, generate_signed_url, get_rate_limit_identifier
from routers.api.png_export import TEMP_IMAGES_DIR
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


class DiagramNodesPatchBody(BaseModel):
    """Patch diagram spec: full `spec` replace and/or structured updates."""

    spec: Optional[Dict[str, Any]] = None
    action: Optional[str] = Field(None, description="update | add | delete")
    updates: Optional[List[Dict[str, Any]]] = None


def _patch_node_text(obj: Any, node_id: str, new_text: str) -> bool:
    if isinstance(obj, dict):
        if obj.get("id") == node_id:
            if "text" in obj:
                obj["text"] = new_text
            if "label" in obj:
                obj["label"] = new_text
            return True
        for v in obj.values():
            if _patch_node_text(v, node_id, new_text):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _patch_node_text(item, node_id, new_text):
                return True
    return False


def _delete_node_by_id(obj: Any, node_id: str) -> bool:
    if isinstance(obj, dict) and "children" in obj and isinstance(obj["children"], list):
        new_children = []
        for ch in obj["children"]:
            if isinstance(ch, dict) and ch.get("id") == node_id:
                continue
            new_children.append(ch)
        if len(new_children) != len(obj["children"]):
            obj["children"] = new_children
            return True
        for ch in obj["children"]:
            if _delete_node_by_id(ch, node_id):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _delete_node_by_id(item, node_id):
                return True
    return False


def _apply_spec_patch(spec: Dict[str, Any], body: DiagramNodesPatchBody) -> Dict[str, Any]:
    if body.spec is not None:
        return body.spec
    if not body.action or not body.updates:
        raise HTTPException(status_code=400, detail="Provide spec or action+updates")
    out = copy.deepcopy(spec)
    action = body.action.lower()
    for u in body.updates:
        if action == "update":
            node_id = u.get("node_id")
            new_text = u.get("new_text")
            if not node_id or new_text is None:
                raise HTTPException(status_code=400, detail="update requires node_id and new_text")
            if not _patch_node_text(out, str(node_id), str(new_text)):
                raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
        elif action == "add":
            text = u.get("text", "")
            children = out.setdefault("children", [])
            prefix = "node"
            if isinstance(out.get("type"), str):
                prefix = out["type"][:8]
            new_id = f"{prefix}_{len(children)}"
            children.append({"id": new_id, "text": text})
        elif action == "delete":
            node_id = u.get("node_id")
            if not node_id:
                raise HTTPException(status_code=400, detail="delete requires node_id")
            if not _delete_node_by_id(out, str(node_id)):
                raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
        else:
            raise HTTPException(status_code=400, detail="action must be update, add, or delete")
    return out


def _build_public_image_url(request: Request, signed_path: str) -> str:
    external_base_url = os.getenv("EXTERNAL_BASE_URL", "").rstrip("/")
    if external_base_url:
        return f"{external_base_url}/api/temp_images/{signed_path}"
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}/api/temp_images/{signed_path}"
    protocol = request.url.scheme
    external_host = os.getenv("EXTERNAL_HOST", "localhost")
    port = os.getenv("PORT", "9527")
    return f"{protocol}://{external_host}:{port}/api/temp_images/{signed_path}"


@router.patch("/diagrams/{diagram_id}/nodes")
async def patch_diagram_nodes(
    diagram_id: str,
    body: DiagramNodesPatchBody,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    cache = get_diagram_cache()
    record = await cache.get_diagram(current_user.id, diagram_id)
    if not record:
        raise HTTPException(status_code=404, detail="Diagram not found")

    spec = record.get("spec") or {}
    if not isinstance(spec, dict):
        spec = {}

    updated_spec = _apply_spec_patch(dict(spec), body)

    ok, _, err = await cache.save_diagram(
        user_id=current_user.id,
        diagram_id=diagram_id,
        title=record["title"],
        diagram_type=record["diagram_type"],
        spec=updated_spec,
        language=record.get("language", "zh"),
        thumbnail=record.get("thumbnail"),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Failed to save diagram")

    children = updated_spec.get("children") if isinstance(updated_spec, dict) else None
    node_count = len(children) if isinstance(children, list) else 0
    return {"ok": True, "diagram_type": record["diagram_type"], "node_count": node_count}


@router.get("/diagrams/{diagram_id}/png")
async def get_diagram_png_url(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "diagram_png",
        identifier,
        max_requests=20,
        window_seconds=60,
    )

    cache = get_diagram_cache()
    record = await cache.get_diagram(current_user.id, diagram_id)
    if not record:
        raise HTTPException(status_code=404, detail="Diagram not found")

    spec = record.get("spec") or {}
    diagram_type = record.get("diagram_type") or "bubble_map"
    if not isinstance(spec, dict):
        raise HTTPException(status_code=400, detail="Invalid diagram spec")

    try:
        png_bytes = await capture_diagram_screenshot(spec, diagram_type)
    except RuntimeError as exc:
        logger.warning("[DiagramPNG] capture failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to render diagram PNG") from exc

    TEMP_IMAGES_DIR.mkdir(exist_ok=True)
    filename = f"diagram_{uuid.uuid4().hex}.png"
    temp_path = TEMP_IMAGES_DIR / filename
    async with aiofiles.open(temp_path, "wb") as f:
        await f.write(png_bytes)

    signed_path = generate_signed_url(filename, expiration_seconds=86400)
    url = _build_public_image_url(request, signed_path)
    return {"url": url, "filename": filename}
