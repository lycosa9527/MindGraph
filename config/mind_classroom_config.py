"""Mind Classroom lecture planner configuration."""

from typing import TYPE_CHECKING, Any


class MindClassroomConfigMixin:
    """Planner model/token budget for 思维讲堂 (canvas tour + slide deck)."""

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

    @property
    def MIND_CLASSROOM_LESSON_PLANNER_MODEL(self) -> str:
        """LLM model for classroom script and slide planning."""
        override = self._get_cached_value("MIND_CLASSROOM_LESSON_PLANNER_MODEL", "")
        if isinstance(override, str) and override.strip():
            return override.strip()
        return self._get_cached_value("ZHIHUI_LESSON_PLANNER_MODEL", "qwen3.7-plus")

    @property
    def MIND_CLASSROOM_LESSON_PLANNER_MAX_TOKENS(self) -> int:
        """Max completion tokens per planner or script call."""
        raw = self._get_cached_value("MIND_CLASSROOM_LESSON_PLANNER_MAX_TOKENS", "")
        if raw not in ("", None):
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
        return int(self._get_cached_value("ZHIHUI_LESSON_PLANNER_MAX_TOKENS", "2500"))

    @property
    def MIND_CLASSROOM_MAX_STEPS(self) -> int:
        """Hard cap on lecture steps (each_node can explode)."""
        try:
            value = int(self._get_cached_value("MIND_CLASSROOM_MAX_STEPS", "40"))
        except (TypeError, ValueError):
            return 40
        return value if value > 0 else 40
