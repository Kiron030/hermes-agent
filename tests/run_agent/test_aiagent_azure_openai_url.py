"""Regression: AIAgent exposes _is_azure_openai_url for routing guards."""

import sys
import types
from unittest.mock import MagicMock, patch

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent


def test_is_azure_openai_url_detection():
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = run_agent.AIAgent(
            model="gpt-4.1-mini",
            provider="custom",
            base_url="https://my-resource.openai.azure.com/openai/v1",
            api_key="sk-test",
            quiet_mode=True,
            max_iterations=1,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
    assert agent._is_azure_openai_url("https://foo.openai.azure.com/openai/v1") is True
    assert agent._is_azure_openai_url("https://api.openai.com/v1") is False
    assert agent._is_azure_openai_url("https://openrouter.ai/api/v1") is False
    assert agent._is_azure_openai_url() is True
