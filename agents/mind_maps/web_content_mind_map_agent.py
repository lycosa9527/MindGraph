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
from utils.prompt_locale import build_web_page_content_user_block


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
        http_request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a mind map from extracted page content."""
        try:
            spec, recovery_warnings = await self._spec_from_web_page_content(
                page_content=page_content,
                language=language,
                content_format=content_format,
                page_title=page_title,
                page_url=page_url,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                http_request_id=http_request_id,
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

    async def _spec_from_web_page_content(
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
        http_request_id: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        """Call LLM to build mind map spec from extracted web page text."""
        system_prompt = get_prompt("mind_map", language, "web_content_generation")
        if not system_prompt:
            return None, None

        user_block = build_web_page_content_user_block(
            page_content=page_content,
            language=language,
            content_format=content_format,
            page_title=page_title,
            page_url=page_url,
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
            http_request_id=http_request_id,
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
