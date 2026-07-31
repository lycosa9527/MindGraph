"""
YAML prompt registry for Maite learning.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from services.utils.error_types import FILE_IO_ERRORS, JSON_PARSE_ERRORS

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Loaded Maite prompt definition from YAML."""

    id: str
    version: str
    task_type: str
    model_hint: str
    input_variables: tuple[str, ...]
    output_schema: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """Prompt template rendered with caller variables."""

    template: PromptTemplate
    system_prompt: str
    user_prompt: str
    variables: Dict[str, str] = field(default_factory=dict)


class PromptRegistry:
    """Load and render Maite prompt YAML files."""

    def __init__(self, prompts_dir: Optional[Path] = None) -> None:
        self._prompts_dir = prompts_dir or Path(__file__).resolve().parent
        self._by_id: Dict[str, PromptTemplate] = {}
        self._by_task: Dict[str, PromptTemplate] = {}
        self._load_all()

    def _load_all(self) -> None:
        for path in sorted(self._prompts_dir.glob("*.yaml")):
            try:
                template = self._load_file(path)
            except (*FILE_IO_ERRORS, *JSON_PARSE_ERRORS, KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping maite prompt %s: %s", path.name, exc)
                continue
            self._by_id[template.id] = template
            self._by_task[template.task_type] = template

    @staticmethod
    def _load_file(path: Path) -> PromptTemplate:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid prompt YAML structure in {path.name}")
        input_vars = raw.get("input_variables") or []
        if not isinstance(input_vars, list):
            raise ValueError(f"input_variables must be a list in {path.name}")
        return PromptTemplate(
            id=str(raw["id"]),
            version=str(raw.get("version", "v1")),
            task_type=str(raw.get("task_type", raw["id"])),
            model_hint=str(raw.get("model_hint", "qwen3.7-plus")),
            input_variables=tuple(str(v) for v in input_vars),
            output_schema=str(raw.get("output_schema", "")),
            system_prompt=str(raw.get("system_prompt", "")).strip(),
            user_prompt=str(raw.get("user_prompt", "")).strip(),
        )

    def get(self, prompt_id: str) -> PromptTemplate:
        """Return a prompt template by id."""
        template = self._by_id.get(prompt_id)
        if template is None:
            raise KeyError(f"Unknown maite prompt id: {prompt_id}")
        return template

    def get_by_task_type(self, task_type: str) -> PromptTemplate:
        """Return a prompt template by task type."""
        template = self._by_task.get(task_type)
        if template is None:
            raise KeyError(f"Unknown maite task_type: {task_type}")
        return template

    def list_ids(self) -> list[str]:
        """List loaded prompt ids sorted alphabetically."""
        return sorted(self._by_id.keys())

    def render(self, prompt_id: str, variables: Mapping[str, Any]) -> RenderedPrompt:
        """Render system/user prompts with variable substitution."""
        template = self.get(prompt_id)
        str_vars = {key: "" if value is None else str(value) for key, value in variables.items()}
        missing = [name for name in template.input_variables if name not in str_vars]
        if missing:
            logger.debug("Maite prompt %s missing variables: %s", prompt_id, missing)
        return RenderedPrompt(
            template=template,
            system_prompt=_substitute(template.system_prompt, str_vars),
            user_prompt=_substitute(template.user_prompt, str_vars),
            variables=dict(str_vars),
        )


def _substitute(text: str, variables: Mapping[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _VAR_PATTERN.sub(replacer, text)


class _PromptRegistryHolder:
    """Holder for singleton Maite prompt registry."""

    _instance: Optional[PromptRegistry] = None

    @classmethod
    def get_instance(cls) -> PromptRegistry:
        """Return or create the singleton registry instance."""
        if cls._instance is None:
            cls._instance = PromptRegistry()
        return cls._instance


def get_prompt_registry() -> PromptRegistry:
    """Return the process-wide Maite prompt registry singleton."""
    return _PromptRegistryHolder.get_instance()
