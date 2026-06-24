"""
Agent result normalization after diagram agent generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict


def agent_validation_failure(message: str) -> Dict[str, Any]:
    """Standard agent response when post-LLM validation fails."""
    return {
        "success": False,
        "error": message,
        "error_type": "validation",
        "show_guidance": True,
    }


def normalize_agent_generation_result(result: Any) -> Dict[str, Any]:
    """
    Normalize agent return value into a consistent artifact dict.

    Returns dict with at least one of: spec, error, warning, recovery_warnings.
    """
    if not isinstance(result, dict):
        return {"spec": result}

    if "spec" in result:
        artifact: Dict[str, Any] = {"spec": result["spec"]}
        if result.get("warning"):
            artifact["warning"] = result["warning"]
        if result.get("recovery_warnings"):
            artifact["recovery_warnings"] = result["recovery_warnings"]
        if result.get("success") is False:
            artifact["success"] = False
            artifact["error"] = result.get("error", "Generation failed")
            if result.get("error_type"):
                artifact["error_type"] = result["error_type"]
            if result.get("show_guidance") is not None:
                artifact["show_guidance"] = result["show_guidance"]
        return artifact

    if result.get("error"):
        return dict(result)

    return {"spec": result}


def artifact_to_spec_or_error(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Collapse artifact to legacy spec-or-error dict for downstream checks."""
    if artifact.get("success") is False or artifact.get("error"):
        error_msg = artifact.get("error", "Generation failed")
        payload: Dict[str, Any] = {
            "success": False,
            "error": error_msg,
        }
        if artifact.get("error_type"):
            payload["error_type"] = artifact["error_type"]
        if artifact.get("show_guidance") is not None:
            payload["show_guidance"] = artifact["show_guidance"]
        return payload
    spec = artifact.get("spec")
    if spec is None:
        return {"error": "Failed to generate specification"}
    return spec if isinstance(spec, dict) else {"spec": spec}


def artifact_metadata(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Extract optional warning metadata from a normalized artifact."""
    meta: Dict[str, Any] = {}
    if artifact.get("warning"):
        meta["warning"] = artifact["warning"]
    if artifact.get("recovery_warnings"):
        meta["recovery_warnings"] = artifact["recovery_warnings"]
    return meta
