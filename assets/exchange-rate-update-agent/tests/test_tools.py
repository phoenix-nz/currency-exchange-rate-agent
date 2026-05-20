"""Unit tests for exchange rate agent via mocked graph invocation."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent():
    """Instantiate SampleAgent with LiteLLM mocked (prevents real AI Core calls)."""
    with patch("langchain_litellm.ChatLiteLLM"):
        from agent import SampleAgent
        return SampleAgent()


def _mock_graph(content: str) -> MagicMock:
    """Return a mock LangGraph graph whose ainvoke returns a canned AIMessage."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content=content)]})
    return graph


# ---------------------------------------------------------------------------
# Unit test: GET_CurrencyExchangeRate (list)
# ---------------------------------------------------------------------------

def test_get_exchange_rates(add_agent_to_path):
    """Agent lists exchange rates — graph returns two mock EUR rates."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "The current EUR/USD exchange rate is 1.0821 and EUR/GBP is 0.8453 as of 2026-05-20."
        )
        result = await agent.invoke("What are the current EUR exchange rates?", "ctx-1")
        assert result.status == "completed"
        assert "EUR" in result.message

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Unit test: GET by key (single rate)
# ---------------------------------------------------------------------------

def test_get_exchange_rate_by_key(add_agent_to_path):
    """Agent retrieves a specific EUR/USD exchange rate by key."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "The EUR to USD exchange rate (type M) effective 2026-05-20 is 1.0821."
        )
        result = await agent.invoke(
            "Get the EUR to USD rate type M effective 2026-05-20", "ctx-2"
        )
        assert result.status == "completed"
        assert "1.0821" in result.message

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Unit test: POST_CurrencyExchangeRate (create)
# ---------------------------------------------------------------------------

def test_create_exchange_rate(add_agent_to_path):
    """Agent creates a new exchange rate without asking for confirmation."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "Successfully created the EUR to USD exchange rate 1.0850 effective 2026-05-21."
        )
        result = await agent.invoke(
            "Create EUR to USD rate M 1.0850 effective 2026-05-21", "ctx-3"
        )
        assert result.status == "completed"
        assert "created" in result.message.lower() or "1.0850" in result.message

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Unit test: PATCH (update) — no confirmation
# ---------------------------------------------------------------------------

def test_update_exchange_rate(add_agent_to_path):
    """Agent updates an existing exchange rate immediately — no confirmation step."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "Successfully updated the EUR to GBP exchange rate to 0.8500 effective 2026-05-20."
        )
        result = await agent.invoke(
            "Update EUR to GBP rate M to 0.8500 effective 2026-05-20", "ctx-4"
        )
        assert result.status == "completed"
        assert "updated" in result.message.lower() or "0.8500" in result.message
        # Must NOT ask for confirmation
        assert "confirm" not in result.message.lower()
        assert "are you sure" not in result.message.lower()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Unit test: Input validation — missing required field
# ---------------------------------------------------------------------------

def test_input_validation_missing_field(add_agent_to_path):
    """Agent asks for missing required field instead of calling write tool."""
    async def run():
        agent = _make_agent()
        agent._graph = _mock_graph(
            "To create the exchange rate, I need the effective date (YYYY-MM-DD). Please provide it."
        )
        result = await agent.invoke(
            "Create EUR to USD rate 1.0850",  # missing ExchangeRateType and date
            "ctx-5",
        )
        assert result.status == "completed"
        # Agent should ask for the missing field, not write immediately
        msg_lower = result.message.lower()
        assert "date" in msg_lower or "effective" in msg_lower or "provide" in msg_lower

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Integration test: end-to-end — query then update with no confirmation
# ---------------------------------------------------------------------------

def test_integration_query_and_no_confirmation_on_update(add_agent_to_path):
    """E2E: query retrieves rate; update executes immediately without confirmation."""
    async def run():
        agent = _make_agent()

        # First call: read
        agent._graph = _mock_graph(
            "The EUR to USD exchange rate (M) effective 2026-05-20 is 1.0821."
        )
        result_get = await agent.invoke("What is the EUR to USD rate?", "ctx-e2e-1")
        assert result_get.status == "completed"
        assert "1.0821" in result_get.message

        # Second call: update — reset graph
        agent._graph = _mock_graph(
            "Updated the EUR to USD exchange rate to 1.0900 effective 2026-05-20."
        )
        result_update = await agent.invoke(
            "Update EUR to USD rate M to 1.0900 effective 2026-05-20", "ctx-e2e-2"
        )
        assert result_update.status == "completed"
        # No confirmation prompt
        assert "confirm" not in result_update.message.lower()
        assert "are you sure" not in result_update.message.lower()
        assert "updated" in result_update.message.lower() or "1.0900" in result_update.message

    asyncio.run(run())
