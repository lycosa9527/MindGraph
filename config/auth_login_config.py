"""COS knobs for public /auth login-hero MP4s."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from config.cos_env_prefix import cos_feature_prefix


class AuthLoginCosConfigMixin:
    """Private-bucket cinematic login clips (presigned GET, no login)."""

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            raise NotImplementedError

    @property
    def COS_AUTH_LOGIN_ENABLED(self) -> bool:
        """Serve /auth heroes from COS when credentials exist. Default on."""
        return self._get_cached_value("COS_AUTH_LOGIN_ENABLED", "true").lower() == "true"

    @property
    def COS_AUTH_LOGIN_PREFIX(self) -> str:
        """COS key prefix for login heroes. Default ``{env}/auth-login``."""
        return cos_feature_prefix(
            "auth-login",
            self._get_cached_value("COS_AUTH_LOGIN_PREFIX", ""),
        )

    @property
    def COS_AUTH_LOGIN_PRESIGN_GET_TTL(self) -> int:
        """Seconds for COS→browser presigned GET URLs."""
        return int(self._get_cached_value("COS_AUTH_LOGIN_PRESIGN_GET_TTL", "3600"))
