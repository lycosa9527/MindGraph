"""
Web content mind map agent — generates mind map specs from extracted page text.

Used by the Chrome extension flow (and API clients). Uses centralized
``web_content_generation`` prompts and defaults to Qwen with classification
model id (qwen-plus-latest) via ``dashscope_model`` override.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, List, Optional, Tuple

from agents.core.agent_utils import extract_json_from_response
from agents.mind_maps.mind_map_agent import MindMapAgent
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service


class WebContentMindMapAgent(MindMapAgent):
    """Mind map generation from web page text (plain or markdown)."""

    async def generate_from_page_content(
        self,
        page_content: str,
        language: str = "en",
        content_format: str = "text/plain",
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a mind map from extracted page content."""
        try:
            spec, recovery_warnings = await self._generate_mind_map_spec_from_web(
                page_content=page_content,
                language=language,
                content_format=content_format,
                page_title=page_title,
                page_url=page_url,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
            )
            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate mind map specification from web content",
                }

            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                if recovery_warnings:
                    err = (
                        f"Partial recovery attempted but validation failed: {validation_msg}. "
                        "Original LLM response had issues."
                    )
                else:
                    err = f"Generated invalid specification: {validation_msg}"
                return {"success": False, "error": err}

            enhanced_spec = await self.enhance_spec(spec)
            result: Dict[str, Any] = {
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

        except Exception as exc:
            return {"success": False, "error": f"Generation failed: {str(exc)}"}

    async def _generate_mind_map_spec_from_web(
        self,
        page_content: str,
        language: str,
        content_format: str,
        page_title: Optional[str],
        page_url: Optional[str],
        user_id: Optional[int],
        organization_id: Optional[int],
        request_type: str,
        endpoint_path: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        """Generate mind map spec from web page content."""
        system_prompt = get_prompt("mind_map", language, "web_content_generation")
        if not system_prompt:
            return None, None

        title_line = (page_title or "").strip() or ("(no title)" if language == "en" else "（无标题）")
        url_line = (page_url or "").strip() or ("(no url)" if language == "en" else "（无 URL）")
        fmt = "markdown" if content_format == "text/markdown" else "plain text"

        if language == "zh":
            user_block = (
                f"页面 URL：{url_line}\n"
                f"页面标题：{title_line}\n"
                f"内容格式：{fmt}\n\n"
                f"--- 正文开始 ---\n{page_content}\n--- 正文结束 ---"
            )
        else:
            user_block = (
                f"Page URL: {url_line}\n"
                f"Page title: {title_line}\n"
                f"Content format: {fmt}\n\n"
                f"--- Content start ---\n{page_content}\n--- Content end ---"
            )

        response = await llm_service.chat(
            prompt=user_block,
            model="qwen",
            system_message=system_prompt,
            max_tokens=4000,
            temperature=0.9,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
            diagram_type="mind_map",
            use_knowledge_base=False,
            dashscope_model=config.QWEN_MODEL_CLASSIFICATION,
        )

        return self._parse_spec_response(response)

    def _parse_spec_response(
        self,
        response: Any,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        """Parse LLM response into spec."""
        if not response:
            return None, None

        recovery_warnings = None
        if isinstance(response, dict):
            spec = response
        else:
            response_str = str(response)
            spec = extract_json_from_response(response_str, allow_partial=True)
            if not spec:
                return None, None
            if spec.get("_partial_recovery"):
                warnings = spec.get("_recovery_warnings", [])
                recovery_warnings = warnings
                spec.pop("_partial_recovery", None)
                spec.pop("_recovery_warnings", None)
                spec.pop("_recovered_count", None)
        return spec, recovery_warnings
