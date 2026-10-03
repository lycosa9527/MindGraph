"""Stream generate_graph must forward the second diagram language."""

import inspect
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.generate_pipeline import run_generate_pipeline
from agents.core.workflow import agent_graph_workflow_with_styles
from models import GenerateRequest
from models.common import DiagramType, LLMModel
from routers.api.diagram_generation import _build_workflow_kwargs


@pytest.mark.asyncio
async def test_run_generate_pipeline_forwards_secondary_language() -> None:
    """Dual-language autocomplete reaches the workflow instead of TypeError."""
    workflow = AsyncMock(return_value={"spec": {}})
    with patch("agents.core.generate_pipeline.agent_graph_workflow_with_styles", new=workflow):
        await run_generate_pipeline(
            "中国外交政策",
            language="en",
            forced_diagram_type="mind_map",
            request_type="autocomplete",
            secondary_language="zh",
        )
    assert workflow.await_args is not None
    assert workflow.await_args.kwargs["secondary_language"] == "zh"
    assert workflow.await_args.kwargs["language"] == "en"
    assert workflow.await_args.kwargs["request_type"] == "autocomplete"


def test_workflow_kwargs_are_accepted_by_stream_and_json_paths() -> None:
    """Every generate_graph kwarg must exist on both callables.

    The stream path unpacks this dict into run_generate_pipeline. A new field
    that only the workflow accepts becomes a TypeError for every model.
    """
    req = GenerateRequest.model_validate(
        {
            "prompt": "中国外交政策",
            "diagram_type": DiagramType.MIND_MAP,
            "language": "en",
            "secondary_language": "zh",
            "llm": LLMModel.QWEN,
            "request_type": "autocomplete",
            "locked_topic": "中国外交政策",
        }
    )
    prepared = {
        "prompt": "中国外交政策",
        "language": "en",
        "llm_model": "qwen",
        "user_id": 3,
        "organization_id": 5,
        "request_type": "autocomplete",
        "endpoint_path": "/api/generate_graph/stream",
        "generation_instructions": None,
        "is_learning_sheet": None,
    }
    kwargs = _build_workflow_kwargs(req, prepared)
    pipeline_params = set(inspect.signature(run_generate_pipeline).parameters)
    workflow_params = set(inspect.signature(agent_graph_workflow_with_styles).parameters)
    assert set(kwargs) <= pipeline_params
    assert set(kwargs) <= workflow_params
    assert kwargs["secondary_language"] == "zh"
