"""Hand-built LangGraph ReAct loop: START -> agent -> (tools -> agent)* -> END.

Module 2.3 builds the loop by hand so the internals are visible. The prebuilt
``create_react_agent`` is compared against it in ``scripts/compare_agents.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import get_llm
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState
from agent.tools.sql_tool import SQL_TOOLS

# Each agent turn plus each tool step counts toward this. It stops a model that loops forever.
RECURSION_LIMIT = 12

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(message: AIMessage) -> AIMessage:
    """Remove qwen3 reasoning tags if the server emits them despite /no_think."""
    if isinstance(message.content, str) and "<think>" in message.content:
        cleaned = _THINK_BLOCK.sub("", message.content).strip()
        return message.model_copy(update={"content": cleaned})
    return message


def build_graph(
    model: BaseChatModel | None = None,
    tools: Sequence[BaseTool] = SQL_TOOLS,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the agent graph. Pass ``model`` or ``tools`` to override the defaults in tests."""
    llm = (model or get_llm()).bind_tools(list(tools))

    def agent_node(state: AgentState) -> dict[str, list[AIMessage]]:
        # The system prompt is prepended on every call and never stored in state.
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [strip_think(llm.invoke(messages))]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(list(tools)))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer or MemorySaver())


@dataclass
class TurnResult:
    answer: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


def run_turn(graph, question: str, thread_id: str) -> TurnResult:
    """Send one user question and return the final answer plus this turn's tool calls."""
    result = graph.invoke({"messages": [("user", question)]}, _config(thread_id))
    messages = result["messages"]
    tool_calls: list[dict[str, Any]] = []
    for message in messages[_last_human_index(messages) + 1 :]:
        if isinstance(message, AIMessage):
            tool_calls.extend({"name": c["name"], "args": c["args"]} for c in message.tool_calls)
    return TurnResult(answer=str(messages[-1].content), tool_calls=tool_calls)


def stream_turn(graph, question: str, thread_id: str) -> Iterator[dict[str, Any]]:
    """Yield LangGraph ``updates`` events (node name -> state update) as the turn runs."""
    yield from graph.stream(
        {"messages": [("user", question)]},
        _config(thread_id),
        stream_mode="updates",
    )


def _last_human_index(messages: list[Any]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        if getattr(messages[index], "type", "") == "human":
            return index
    return -1

