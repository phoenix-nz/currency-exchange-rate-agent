"""Additional coverage tests for agent.py and mcp_tools.py."""
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _make_agent():
    with patch("langchain_litellm.ChatLiteLLM"):
        from agent import SampleAgent
        return SampleAgent()


def _mock_graph(content: str) -> MagicMock:
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content=content)]})
    return graph


# ---------------------------------------------------------------------------
# stream() method tests
# ---------------------------------------------------------------------------

def test_stream_yields_processing_then_result(add_agent_to_path):
    """stream() yields a 'Processing...' chunk followed by the final result."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph("EUR/USD rate is 1.0821")
        chunks = []
        async for chunk in agent.stream("What is EUR to USD?", "ctx-stream"):
            chunks.append(chunk)

        assert len(chunks) == 2
        # First chunk is the progress indicator
        assert chunks[0]["is_task_complete"] is False
        assert chunks[0]["require_user_input"] is False
        assert "Processing" in chunks[0]["content"]
        # Second chunk is the final answer
        assert chunks[1]["is_task_complete"] is True
        assert "1.0821" in chunks[1]["content"]

    asyncio.run(run())


def test_stream_propagates_errors(add_agent_to_path):
    """stream() propagates exceptions from the graph."""
    async def run():
        agent = _make_agent()
        failing_graph = MagicMock()
        failing_graph.ainvoke = AsyncMock(side_effect=RuntimeError("S/4HANA unavailable"))
        agent._graph = failing_graph

        chunks = []
        with pytest.raises(RuntimeError, match="S/4HANA unavailable"):
            async for chunk in agent.stream("List rates", "ctx-err"):
                chunks.append(chunk)

        # First progress chunk should have been yielded before error
        assert len(chunks) == 1
        assert chunks[0]["is_task_complete"] is False

    asyncio.run(run())


def test_invoke_propagates_errors(add_agent_to_path):
    """invoke() propagates exceptions."""
    async def run():
        agent = _make_agent()
        failing_graph = MagicMock()
        failing_graph.ainvoke = AsyncMock(side_effect=RuntimeError("API timeout"))
        agent._graph = failing_graph

        with pytest.raises(RuntimeError, match="API timeout"):
            await agent.invoke("Update rate", "ctx-err2")

    asyncio.run(run())


# ---------------------------------------------------------------------------
# _get_graph caching
# ---------------------------------------------------------------------------

def test_get_graph_builds_once_and_caches(add_agent_to_path):
    """_get_graph builds the graph once; subsequent calls return the cached graph."""
    async def run():
        agent = _make_agent()
        mock_tools = [MagicMock(name="GET_CurrencyExchangeRate")]

        with patch("mcp_tools.get_mcp_tools", new=AsyncMock(return_value=mock_tools)):
            g1 = await agent._get_graph()
            g2 = await agent._get_graph()

        assert g1 is g2  # same cached instance

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Decorator presence check
# ---------------------------------------------------------------------------

def test_agent_has_exactly_three_decorators(add_agent_to_path):
    """agent.py must have exactly 3 decorated functions (agent_model, agent_config, prompt_section)."""
    import subprocess, sys
    result = subprocess.run(
        ["grep", "-c", r"^@agent_model\|^@agent_config\|^@prompt_section",
         str(Path(__file__).parent.parent / "app" / "agent.py")],
        capture_output=True, text=True,
    )
    count = int(result.stdout.strip())
    assert count == 3, f"Expected 3 decorated functions, found {count}"


# ---------------------------------------------------------------------------
# Milestone instrumentation smoke test
# ---------------------------------------------------------------------------

def test_milestone_logging_achieved(add_agent_to_path, caplog):
    """M6.achieved is logged when a query is processed successfully."""
    import logging
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph("EUR/USD rate is 1.0821")
        with caplog.at_level(logging.INFO, logger="agent"):
            await agent.invoke("What is EUR to USD?", "ctx-m6")

    asyncio.run(run())
    assert any("M6.achieved" in r.message for r in caplog.records)
    assert any("M10.achieved" in r.message for r in caplog.records)


def test_milestone_logging_m9_achieved(add_agent_to_path, caplog):
    """M9.achieved is logged when the response indicates a successful write."""
    import logging
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "Successfully updated the EUR to USD exchange rate to 1.0900."
        )
        with caplog.at_level(logging.INFO, logger="agent"):
            await agent.invoke("Update EUR to USD rate", "ctx-m9")

    asyncio.run(run())
    assert any("M9.achieved" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# mcp_tools.py — IBD_TESTING path
# ---------------------------------------------------------------------------

def test_mcp_tools_load_from_mock_file(add_agent_to_path):
    """In IBD_TESTING mode, get_mcp_tools reads from mcp-mock.json."""
    async def run():
        from mcp_tools import get_mcp_tools
        tools = await get_mcp_tools()
        # mcp-mock.json has 6 tools in the currency-exchange-rate server
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert any("CurrencyExchangeRate" in name for name in tool_names)

    asyncio.run(run())


def test_mcp_tools_missing_file_returns_empty(add_agent_to_path, tmp_path, monkeypatch):
    """_build_mock_tools returns empty list when mcp-mock.json is absent."""
    import mcp_tools as mt
    original = mt._MOCK_FILE
    monkeypatch.setattr(mt, "_MOCK_FILE", tmp_path / "nonexistent.json")
    result = mt._build_mock_tools()
    monkeypatch.setattr(mt, "_MOCK_FILE", original)
    assert result == []


def test_mcp_tools_invalid_json_returns_empty(add_agent_to_path, tmp_path, monkeypatch):
    """_build_mock_tools returns empty list for malformed JSON."""
    import mcp_tools as mt
    bad_file = tmp_path / "mcp-mock.json"
    bad_file.write_text("{invalid json}")
    original = mt._MOCK_FILE
    monkeypatch.setattr(mt, "_MOCK_FILE", bad_file)
    result = mt._build_mock_tools()
    monkeypatch.setattr(mt, "_MOCK_FILE", original)
    assert result == []
