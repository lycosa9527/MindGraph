"""VOD feature mapping is not org-grant gated."""

from utils.auth.roles import FEATURE_KEY_TO_CONFIG_ATTR, FEATURE_KEYS_WITH_ORG_ACCESS


def test_feature_vod_mapped_and_not_org_grant_gated() -> None:
    """FEATURE_VOD is mapped and not org-grant gated."""
    assert FEATURE_KEY_TO_CONFIG_ATTR["feature_vod"] == "FEATURE_VOD"
    assert "feature_vod" not in FEATURE_KEYS_WITH_ORG_ACCESS
