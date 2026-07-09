"""
Mind Map Agent - LLM-based mind map spec generation.

Layout is handled entirely by the frontend (loadMindMapSpec / correctYPositions).
This agent only generates the JSON spec (topic + children tree) via LLM and
tags it with ``_agent = 'mind_map_agent'``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Dict, List, Optional, Tuple, Any
import logging

from agents.core.base_agent import BaseAgent
from agents.core.agent_result import agent_validation_failure
from agents.core.agent_utils import extract_json_from_response
from agents.core.llm_spec_stream import dispatch_llm_chat
from config.settings import Config
from prompts import get_prompt
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.prompt_locale import is_chinese_prompt_shell_language


logger = logging.getLogger(__name__)


def build_mind_map_branch_expand_user_message(
    *,
    expand_branch: str,
    mind_map_topic: str,
    reference_branches: List[str],
    existing_branch_children: List[str],
    parent_branch: str,
    language: str,
) -> str:
    """Build the LLM user message for mind map branch sub-graph expansion."""
    is_main_branch = not (parent_branch or "").strip()
    if is_chinese_prompt_shell_language(language):
        lines = [
            f"中心主题：{mind_map_topic or '（未设置）'}",
            f"要扩展的分支：{expand_branch}",
        ]
        if parent_branch:
            lines.append(f"上级分支：{parent_branch}")
        if reference_branches:
            lines.append(f"图中其他分支（参考）：{'、'.join(reference_branches)}")
        if existing_branch_children:
            lines.append(f"该分支已有子节点（勿重复）：{'、'.join(existing_branch_children)}")
        if is_main_branch:
            lines.append("请为该主分支生成 4–6 个直接子节点（仅一层，不要嵌套更深层级）。")
        else:
            lines.append("请为该子节点生成 4–6 个直接下级节点（仅一层，不要嵌套更深层级）。")
        return "\n".join(lines)

    lines = [
        f"Central topic: {mind_map_topic or '(not set)'}",
        f"Branch to expand: {expand_branch}",
    ]
    if parent_branch:
        lines.append(f"Parent branch: {parent_branch}")
    if reference_branches:
        lines.append(f"Other branches in the map (reference): {', '.join(reference_branches)}")
    if existing_branch_children:
        joined = ", ".join(existing_branch_children)
        lines.append(f"Existing children under this branch (do not duplicate): {joined}")
    if is_main_branch:
        lines.append("Generate 4–6 direct child nodes for this main branch only (one level; no deeper nesting).")
    else:
        lines.append("Generate 4–6 direct child nodes for this sub-node only (one level; no deeper nesting).")
    return "\n".join(lines)


class MindMapAgent(BaseAgent):
    """
    Mind Map Agent - generates mind map specs via LLM.

    Layout is handled entirely on the frontend; this agent only
    produces the JSON spec (topic + children tree) via LLM.
    """

    def __init__(self, model="qwen"):
        super().__init__(model=model)
        self.config = Config()
        self.diagram_type = "mindmap"

    def _get_node_text(self, node: Dict, default: str = "") -> str:
        """
        Safely extract text from a node. Canonical field is 'text' (matches frontend
        and tree/brace map prompts). Fallback to 'label' for backward compatibility.

        Args:
            node: Node dictionary with 'text' or 'label' key
            default: Default value if neither key exists

        Returns:
            Text content from node
        """
        if not isinstance(node, dict):
            return default

        return node.get("text") or node.get("label") or default

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a mind map from a prompt."""
        try:
            expand_branch = str(kwargs.get("expand_branch") or "").strip()
            if expand_branch:
                return await self._generate_branch_expand(
                    expand_branch=expand_branch,
                    language=language,
                    mind_map_topic=str(kwargs.get("mind_map_topic") or "").strip(),
                    reference_branches=kwargs.get("reference_branches"),
                    existing_branch_children=kwargs.get("existing_branch_children"),
                    parent_branch=str(kwargs.get("parent_branch") or "").strip(),
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    phase_emit=kwargs.get("phase_emit"),
                )

            structure_mode = kwargs.get("structure_mode", "free")
            fixed_nodes = kwargs.get("fixed_nodes") or {}
            spec, recovery_warnings = await self._generate_mind_map_spec(
                user_prompt,
                language,
                structure_mode=structure_mode,
                fixed_nodes=fixed_nodes,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                phase_emit=kwargs.get("phase_emit"),
            )
            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate mind map specification",
                }

            is_valid, validation_msg = self.validate_output(
                spec,
                fixed_branch_labels=fixed_nodes.get("children") if structure_mode == "fixed" else None,
            )
            if not is_valid:
                logger.warning("MindMapAgent: Validation failed: %s", validation_msg)
                if recovery_warnings:
                    error_msg = (
                        f"Partial recovery attempted but validation failed: "
                        f"{validation_msg}. Original LLM response had issues."
                    )
                else:
                    error_msg = f"Generated invalid specification: {validation_msg}"
                return agent_validation_failure(error_msg)

            enhanced_spec = await self.enhance_spec(spec)

            logger.info("MindMapAgent: Successfully generated mind map")
            result = {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }

            if recovery_warnings:
                result["warning"] = (
                    "LLM response had issues. Some branches may be missing. You can use auto-complete to add more."
                )
                result["recovery_warnings"] = recovery_warnings

            return result

        except LLM_PIPELINE_ERRORS as e:
            logger.error("MindMapAgent: Error generating mind map: %s", e)
            return {"success": False, "error": f"Generation failed: {str(e)}"}

    def _build_user_prompt_message(
        self,
        prompt: str,
        language: str,
        fixed_nodes: Dict[str, Any],
    ) -> str:
        """Build LLM user message."""
        children = fixed_nodes.get("children")
        if isinstance(children, list) and children:
            labels = ", ".join(str(c) for c in children if str(c).strip())
            if is_chinese_prompt_shell_language(language):
                return f"请为以下描述创建思维导图：{prompt}\n\n用户指定的主分支（必须原样使用）：{labels}"
            return (
                f"Please create a mind map for the following description: {prompt}\n\n"
                f"User-specified main branches (use EXACT labels): {labels}"
            )
        if is_chinese_prompt_shell_language(language):
            return f"请为以下描述创建一个思维导图：{prompt}"
        return f"Please create a mind map for the following description: {prompt}"

    def _coerce_reference_branch_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    def _build_branch_expand_user_message(
        self,
        *,
        expand_branch: str,
        mind_map_topic: str,
        reference_branches: List[str],
        existing_branch_children: List[str],
        parent_branch: str,
        language: str,
    ) -> str:
        return build_mind_map_branch_expand_user_message(
            expand_branch=expand_branch,
            mind_map_topic=mind_map_topic,
            reference_branches=reference_branches,
            existing_branch_children=existing_branch_children,
            parent_branch=parent_branch,
            language=language,
        )

    async def _generate_branch_expand(
        self,
        *,
        expand_branch: str,
        language: str,
        mind_map_topic: str,
        reference_branches: Any,
        existing_branch_children: Any,
        parent_branch: str,
        user_id: Optional[int],
        organization_id: Optional[int],
        request_type: str,
        endpoint_path: Optional[str],
        phase_emit,
    ) -> Dict[str, Any]:
        """Generate sub-branches for one existing mind map branch."""
        try:
            system_prompt = get_prompt("mind_map", language, "branch_expand")
            if not system_prompt:
                logger.error("MindMapAgent: No branch_expand prompt for language %s", language)
                return {"success": False, "error": "Branch expand prompt not configured"}

            refs = self._coerce_reference_branch_list(reference_branches)
            refs = [label for label in refs if label != expand_branch]
            existing = self._coerce_reference_branch_list(existing_branch_children)
            user_prompt = self._build_branch_expand_user_message(
                expand_branch=expand_branch,
                mind_map_topic=mind_map_topic,
                reference_branches=refs,
                existing_branch_children=existing,
                parent_branch=parent_branch,
                language=language,
            )

            logger.info(
                "MindMapAgent: Branch expand dispatch model=%s language=%s expand=%r topic=%r",
                self.model,
                language,
                expand_branch,
                mind_map_topic,
            )
            logger.info("MindMapAgent: Branch expand user prompt:\n%s", user_prompt)

            response = await dispatch_llm_chat(
                phase_emit=phase_emit,
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=1.0,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type="mind_map",
            )

            if not response:
                logger.error("MindMapAgent: No response from LLM for branch expand")
                return {"success": False, "error": "Failed to generate branch sub-graph"}

            if isinstance(response, dict):
                spec = response
            else:
                response_str = str(response)
                spec = extract_json_from_response(response_str, allow_partial=True)
                if not spec:
                    logger.error("MindMapAgent: Failed to extract JSON from branch expand response")
                    return {"success": False, "error": "Failed to parse branch sub-graph response"}

                if spec.get("_partial_recovery"):
                    warnings = spec.get("_recovery_warnings", [])
                    logger.warning(
                        "MindMapAgent: Partial branch expand JSON recovery. Warnings: %s",
                        ", ".join(warnings),
                    )
                    spec.pop("_partial_recovery", None)
                    spec.pop("_recovery_warnings", None)
                    spec.pop("_recovered_count", None)

            if isinstance(spec, dict):
                spec["topic"] = expand_branch

            is_valid, validation_msg = self.validate_branch_expand_output(spec, expand_branch)
            if not is_valid:
                logger.warning("MindMapAgent: Branch expand validation failed: %s", validation_msg)
                return agent_validation_failure(f"Generated invalid branch sub-graph: {validation_msg}")

            enhanced_spec = await self.enhance_spec(spec)
            child_labels = [
                self._get_node_text(child).strip()
                for child in (enhanced_spec.get("children") or [])
                if isinstance(child, dict) and self._get_node_text(child).strip()
            ]
            logger.info(
                "MindMapAgent: Branch expand LLM response topic=%r children(%d)=%s",
                enhanced_spec.get("topic"),
                len(child_labels),
                child_labels,
            )
            logger.info("MindMapAgent: Successfully generated branch sub-graph for %r", expand_branch)
            return {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }
        except LLM_PIPELINE_ERRORS as exc:
            logger.error("MindMapAgent: Branch expand error: %s", exc)
            return {"success": False, "error": f"Generation failed: {str(exc)}"}

    async def _generate_mind_map_spec(
        self,
        prompt: str,
        language: str,
        structure_mode: str = "free",
        fixed_nodes: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
        phase_emit=None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        """Generate the mind map specification using LLM."""
        fixed_nodes = fixed_nodes or {}
        try:
            has_fixed_children = structure_mode == "fixed" and fixed_nodes.get("children")
            prompt_type = "fixed_children" if has_fixed_children else "generation"
            system_prompt = get_prompt("mind_map", language, prompt_type)

            if not system_prompt:
                logger.error("MindMapAgent: No prompt found for language %s type %s", language, prompt_type)
                return None, None

            user_prompt = self._build_user_prompt_message(prompt, language, fixed_nodes)

            response = await dispatch_llm_chat(
                phase_emit=phase_emit,
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=1.0,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type="mind_map",
            )

            if not response:
                logger.error("MindMapAgent: No response from LLM")
                return None, None

            recovery_warnings = None
            if isinstance(response, dict):
                spec = response
            else:
                response_str = str(response)
                spec = extract_json_from_response(response_str, allow_partial=True)

                if not spec:
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error("MindMapAgent: Failed to extract JSON from LLM response")
                    logger.error(
                        "MindMapAgent: Response length: %s, Preview: %s",
                        len(response_str),
                        response_preview,
                    )
                    return None, None

                if spec.get("_partial_recovery"):
                    warnings = spec.get("_recovery_warnings", [])
                    recovered_count = spec.get("_recovered_count", 0)
                    logger.warning(
                        "MindMapAgent: Partial JSON recovery succeeded. Recovered %s branches. Warnings: %s",
                        recovered_count,
                        ", ".join(warnings),
                    )
                    recovery_warnings = warnings
                    spec.pop("_partial_recovery", None)
                    spec.pop("_recovery_warnings", None)
                    spec.pop("_recovered_count", None)

            return spec, recovery_warnings

        except LLM_PIPELINE_ERRORS as e:
            logger.error("MindMapAgent: Error in spec generation: %s", e)
            raise

    def validate_output(
        self,
        output: Dict[str, Any],
        fixed_branch_labels: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Validate a mind map specification."""
        try:
            if not output or not isinstance(output, dict):
                return False, "Invalid specification"

            if "topic" not in output or not output["topic"]:
                return False, "Missing topic"

            if "children" not in output or not isinstance(output["children"], list):
                return False, "Missing children"

            if not output["children"]:
                return False, "At least one child branch is required"

            if fixed_branch_labels:
                expected = [str(label).strip() for label in fixed_branch_labels if str(label).strip()]
                actual = [self._get_node_text(child).strip() for child in output["children"] if isinstance(child, dict)]
                if len(actual) != len(expected):
                    return False, f"Expected {len(expected)} main branches, got {len(actual)}"
                for idx, label in enumerate(expected):
                    if idx >= len(actual) or actual[idx] != label:
                        return False, f"Branch {idx + 1} must be '{label}'"

            return True, "Valid mind map specification"
        except LLM_PIPELINE_ERRORS as e:
            return False, f"Validation error: {str(e)}"

    def validate_branch_expand_output(
        self,
        output: Dict[str, Any],
        expand_branch: str,
    ) -> Tuple[bool, str]:
        """Validate branch-expand JSON (sub-branches only)."""
        try:
            if not output or not isinstance(output, dict):
                return False, "Invalid specification"

            topic = str(output.get("topic") or self._get_node_text(output, "")).strip()
            if not topic:
                return False, "Missing topic"
            if topic != expand_branch.strip():
                return False, f"Topic must be the expanded branch '{expand_branch}'"

            children = output.get("children")
            if not isinstance(children, list) or not children:
                return False, "Missing children"

            valid_children = [
                child for child in children if isinstance(child, dict) and self._get_node_text(child).strip()
            ]
            if len(valid_children) < 2:
                return False, "At least two sub-branches are required"
            if len(valid_children) > 8:
                return False, "Too many sub-branches (max 8)"

            return True, "Valid branch expand specification"
        except LLM_PIPELINE_ERRORS as exc:
            return False, f"Validation error: {str(exc)}"

    async def enhance_spec(self, spec: Dict) -> Dict:
        """Tag the spec so downstream code knows which agent produced it.

        Layout is computed entirely on the frontend; this method no longer
        generates positions or connections.
        """
        if not spec or "topic" not in spec or "children" not in spec:
            return {"success": False, "error": "Invalid specification"}
        spec["_agent"] = "mind_map_agent"
        return spec
