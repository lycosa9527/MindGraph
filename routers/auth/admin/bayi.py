import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header

from models.auth import User
from models.messages import Messages
from utils.auth import AUTH_MODE

from ..dependencies import get_language_dependency, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/bayi/ip-whitelist", tags=["Admin - Bayi IP Whitelist"])

@router.get("", dependencies=[Depends(require_admin)])
async def list_bayi_ip_whitelist(
    request: Request,
    current_user: User = Depends(require_admin),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, Any]:
    """List all whitelisted IPs for bayi mode (ADMIN ONLY)"""
    if AUTH_MODE != "bayi":
        error_msg = Messages.error("feature_not_available", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bayi mode not enabled")
    
    try:
        from services.redis_bayi_whitelist import get_bayi_whitelist
        whitelist = get_bayi_whitelist()
        ips = whitelist.list_ips()
        
        return {
            "ips": ips,
            "count": len(ips)
        }
    except Exception as e:
        logger.error(f"Failed to list IP whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list IP whitelist"
        )

@router.post("", dependencies=[Depends(require_admin)])
async def add_bayi_ip_whitelist(
    request_body: dict,
    http_request: Request,
    current_user: User = Depends(require_admin),
    lang: str = Depends(get_language_dependency)
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
        from services.redis_bayi_whitelist import get_bayi_whitelist
        whitelist = get_bayi_whitelist()
        success = whitelist.add_ip(ip, added_by=current_user.phone)
        
        if success:
            logger.info(f"Admin {current_user.phone} added IP {ip} to bayi whitelist")
            return {
                "message": f"IP {ip} added to whitelist successfully",
                "ip": ip
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add IP to whitelist"
            )
    except ValueError as e:
        error_msg = Messages.error("invalid_ip_address", lang, ip)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        logger.error(f"Failed to add IP to whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add IP to whitelist"
        )

@router.delete("/{ip}", dependencies=[Depends(require_admin)])
async def remove_bayi_ip_whitelist(
    ip: str,
    request: Request,
    current_user: User = Depends(require_admin),
    lang: str = Depends(get_language_dependency)
) -> Dict[str, str]:
    """Remove IP from bayi IP whitelist (ADMIN ONLY)"""
    if AUTH_MODE != "bayi":
        error_msg = Messages.error("feature_not_available", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bayi mode not enabled")
    
    try:
        from services.redis_bayi_whitelist import get_bayi_whitelist
        whitelist = get_bayi_whitelist()
        success = whitelist.remove_ip(ip)
        
        if success:
            logger.info(f"Admin {current_user.phone} removed IP {ip} from bayi whitelist")
            return {
                "message": f"IP {ip} removed from whitelist successfully",
                "ip": ip
            }
        else:
            error_msg = f"IP {ip} not found in whitelist"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except ValueError as e:
        error_msg = f"Invalid IP address format: {ip}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove IP from whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove IP from whitelist"
        )



