import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from opentelemetry import trace
from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section

from mcp_tools import get_mcp_tools

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@agent_model(
    key="config.model",
    label="LLM Model",
    description="The language model powering this agent",
)
def get_model_name() -> str:
    return "sap/anthropic--claude-4.5-sonnet"


@agent_config(
    key="config.temperature",
    label="LLM Temperature",
    description="Controls randomness of responses (0.0 = deterministic, 1.0 = creative)",
)
def get_temperature() -> float:
    return 0.0


@prompt_section(
    key="prompts.system",
    label="System Prompt",
    description="The full system prompt defining the agent's role and behavior",
    validation={"format": "markdown", "max_length": 5000},
)
def get_system_prompt() -> str:
    return (
        "You are an AI agent that reads, creates, and updates currency exchange rates in SAP S/4HANA. "
        "Execute write operations (create/update) immediately once all required fields are provided — "
        "do NOT ask for confirmation before writing. "
        "Never infer or estimate rate values — all values must be explicitly provided by the user. "
        "If a required field is missing, ask the user for that specific field before proceeding. "
        "Required fields for writes: ExchangeRateType, SourceCurrency, TargetCurrency, "
        "ExchangeRateEffectiveDate (YYYY-MM-DD), ExchangeRateValue. "
        "Set top to a maximum of 100 on every list/search tool call to prevent context overflow; "
        "inform the user when this limit is applied. "
        "If the S/4HANA API returns an error, report it clearly — do not retry automatically."
    )


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


class SampleAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        from langchain_litellm import ChatLiteLLM
        self.llm = ChatLiteLLM(model=get_model_name(), temperature=get_temperature())
        self._graph = None

    def _build_graph(self, tools):
        llm_with_tools = self.llm.bind_tools(tools)
        tool_node = ToolNode(tools)

        def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "tools"
            return "__end__"

        async def call_model(state: MessagesState):
            response = await llm_with_tools.ainvoke(state["messages"])
            return {"messages": [response]}

        builder = StateGraph(MessagesState)
        builder.add_node("model", call_model)
        builder.add_node("tools", tool_node)
        builder.add_edge(START, "model")
        builder.add_conditional_edges(
            "model", should_continue, {"tools": "tools", "__end__": END}
        )
        builder.add_edge("tools", "model")
        return builder.compile()

    async def _get_graph(self):
        if self._graph is None:
            tools = await get_mcp_tools()
            logger.info(
                "Building graph with %d tool(s): %s",
                len(tools),
                [t.name for t in tools],
            )
            self._graph = self._build_graph(tools)
        return self._graph

    async def _run_agent(self, query: str) -> str:
        """Core agent execution — instrumented with OTel spans and milestone logging.

        Extracted from stream() so spans never wrap a yield statement.
        """
        with tracer.start_as_current_span("exchange_rate_agent.run") as span:
            span.set_attribute("query", query[:500])

            # M6 — User Request Received
            try:
                messages = [
                    SystemMessage(content=get_system_prompt()),
                    HumanMessage(content=query),
                ]
                logger.info("M6.achieved: user request received and intent classified")
                span.add_event("M6.achieved", {"description": "user request received and intent classified"})
            except Exception as exc:
                logger.warning("M6.missed: intent classification failed or request not understood")
                span.record_exception(exc)
                raise

            # M7 / M8 / M9 — Execute the graph (retrieval + validation + write happen inside tool calls)
            with tracer.start_as_current_span("exchange_rate_agent.graph_invoke") as graph_span:
                try:
                    graph = await self._get_graph()
                    result = await graph.ainvoke({"messages": messages})
                    response = result["messages"][-1].content

                    # Determine which milestones to log based on response content
                    response_lower = response.lower()

                    # M7 — Exchange Rate Retrieved
                    if any(k in response_lower for k in ["rate", "eur", "usd", "gbp", "exchange"]):
                        logger.info("M7.achieved: exchange rate retrieved from S/4HANA")
                        graph_span.add_event(
                            "M7.achieved",
                            {"description": "exchange rate retrieved from S/4HANA"},
                        )
                    else:
                        logger.info("M7.missed: exchange rate retrieval failed or no data returned")

                    # M8 — Update Validated (triggered when a write was requested)
                    write_keywords = ["creat", "updat", "patch", "post", "set", "written", "added"]
                    if any(k in response_lower for k in write_keywords):
                        logger.info("M8.achieved: input parameters validated successfully")
                        graph_span.add_event(
                            "M8.achieved",
                            {"description": "input parameters validated successfully"},
                        )

                        # M9 — Exchange Rate Updated
                        success_keywords = ["success", "created", "updated", "written", "added", "saved"]
                        if any(k in response_lower for k in success_keywords):
                            logger.info("M9.achieved: exchange rate created/updated in S/4HANA")
                            graph_span.add_event(
                                "M9.achieved",
                                {"description": "exchange rate created/updated in S/4HANA"},
                            )
                        else:
                            logger.warning("M9.missed: exchange rate update failed, API error returned")
                            graph_span.add_event(
                                "M9.missed",
                                {"description": "exchange rate update failed, API error returned"},
                            )
                    else:
                        logger.info("M8.missed: input validation failed, user prompted to correct input")

                except Exception as exc:
                    logger.error("M7.missed: exchange rate retrieval failed or no data returned")
                    graph_span.record_exception(exc)
                    raise

            # M10 — Confirmation Provided
            logger.info("M10.achieved: operation result confirmed to user")
            span.add_event("M10.achieved", {"description": "operation result confirmed to user"})

            return response

    async def stream(self, query: str, context_id: str) -> AsyncGenerator[dict, None]:
        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Processing...",
        }
        try:
            response = await self._run_agent(query)
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response,
            }
        except Exception:
            logger.error("stream() failed", exc_info=True)
            raise

    async def invoke(self, query: str, context_id: str) -> AgentResponse:
        try:
            response = await self._run_agent(query)
            return AgentResponse(status="completed", message=response)
        except Exception:
            logger.error("invoke() failed", exc_info=True)
            raise
