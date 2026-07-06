"""Named WeCom notification profiles."""

from __future__ import annotations

from dataclasses import dataclass

PROFILE_SCHOOL_CONSULT = "school_consult"
PROFILE_TECH_SUPPORT = "tech_support"

BUILTIN_PROFILE_IDS: tuple[str, ...] = (
    PROFILE_SCHOOL_CONSULT,
    PROFILE_TECH_SUPPORT,
)

PROFILE_ENV_SUFFIX: dict[str, str] = {
    PROFILE_SCHOOL_CONSULT: "SCHOOL_CONSULT",
    PROFILE_TECH_SUPPORT: "TECH_SUPPORT",
}


@dataclass(frozen=True)
class WeComNotifyProfile:
    """Destination profile: group webhook and/or app-message recipients."""

    profile_id: str
    webhook_url: str | None = None
    webhook_mention_userids: tuple[str, ...] = ()
    webhook_mention_mobile_list: tuple[str, ...] = ()
    notify_userids: tuple[str, ...] = ()

    @property
    def webhook_enabled(self) -> bool:
        """True when a validated webhook URL is configured."""
        return bool(self.webhook_url)

    @property
    def app_message_enabled(self) -> bool:
        """True when at least one notify_userid is configured."""
        return bool(self.notify_userids)

    @property
    def is_enabled(self) -> bool:
        """True when any delivery channel is configured."""
        return self.webhook_enabled or self.app_message_enabled
