"""Ark chat-completions thinking switch.

DeepSeek-V4.1 on Volcengine thinks unless ``thinking.type`` is set.
``enable_thinking`` is the older flag and is ignored on that endpoint.
"""

from typing import Any, Dict


def volcengine_thinking_extra(model_alias: str, enable_thinking: bool) -> Dict[str, Any]:
    """Return the extra body for this Volcengine alias.

    ``ark-deepseek`` (console endpoint DS_v4.1flash) uses ``thinking.type``.
    Canvas Doubao 2.1 (``ark-doubao21``) uses the same switch so thinking stays off.
    Kimi still uses ``enable_thinking``, and only when thinking is requested.
    The doubao_1.5pro_32k alias omits the field when thinking is off.
    """
    if model_alias in ("ark-deepseek", "ark-doubao21"):
        mode = "enabled" if enable_thinking else "disabled"
        return {"thinking": {"type": mode}}
    if enable_thinking:
        return {"enable_thinking": True}
    return {}
