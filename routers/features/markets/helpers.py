"""Market router helpers."""

from fastapi import HTTPException, status

from config.settings import config


def require_markets_enabled() -> None:
    """Raise 404 if markets feature is disabled (avoid advertising existence)."""
    if not config.FEATURE_MARKETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
