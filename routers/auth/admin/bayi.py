from typing import Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from models.domain.auth import User
from models.domain.messages import Messages, Language
from services.redis.redis_bayi_whitelist import get_bayi_whitelist
from utils.auth import AUTH_MODE
from ..dependencies import get_language_dependency, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/bayi/ip-whitelist", tags=["Admin - Bayi IP Whitelist"])

@router.get("", dependencies=[Depends(require_admin)])
async def list_bayi_ip_whitelist(
    request: Request,
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """List all whitelisted IPs for bayi mode (ADMIN ONLY)"""
    if AUTH_MODE != "bayi":
        Messages.error("feature_not_available", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bayi mode not enabled")

    try:
        whitelist = get_bayi_whitelist()
        ips = whitelist.list_ips()

        return {
            "ips": ips,
            "count": len(ips)
        }
    except Exception as e:
        logger.error("Failed to list IP whitelist: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list IP whitelist"
        )

@router.post("", dependencies=[Depends(require_admin)])
async def add_bayi_ip_whitelist(
    request_body: dict,
    http_request: Request,
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency)
) -> Dict[str, str]:
    """Add IP to bayi IP whitelist (ADMIN ONLY)"""
    if AUTH_MODE != "bayi":
        error_msg = Messages.error("feature_not_available", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bayi mode not enabled")

    if "ip" not in request_body:
        error_msg = Messages.error("missing_required_fields", lang, "ip")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    ip = request_body["ip"].strip()

    try:
        whitelist = get_bayi_whitelist()
        success = whitelist.add_ip(ip, added_by=current_user.phone)

        if success:
            logger.info("Admin %s added IP %s to bayi whitelist", current_user.phone, ip)
            return {
                "message": f"IP {ip} added to whitelist successfully",
                "ip": ip
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add IP to whitelist"
            )
    except ValueError:
        error_msg = Messages.error("invalid_ip_address", lang, ip)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        logger.error("Failed to add IP to whitelist: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add IP to whitelist"
        )

@router.delete("/{ip}", dependencies=[Depends(require_admin)])
async def remove_bayi_ip_whitelist(
    ip: str,
    request: Request,
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency)
) -> Dict[str, str]:
    """Remove IP from bayi IP whitelist (ADMIN ONLY)"""
    if AUTH_MODE != "bayi":
        error_msg = Messages.error("feature_not_available", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bayi mode not enabled")

    try:
        whitelist = get_bayi_whitelist()
        success = whitelist.remove_ip(ip)

        if success:
            logger.info("Admin %s removed IP %s from bayi whitelist", current_user.phone, ip)
            return {
                "message": f"IP {ip} removed from whitelist successfully",
                "ip": ip
            }
        else:
            error_msg = f"IP {ip} not found in whitelist"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except ValueError:
        error_msg = f"Invalid IP address format: {ip}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove IP from whitelist: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove IP from whitelist"
        )



