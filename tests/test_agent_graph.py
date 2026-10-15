"""Module 2.3 tests: the hand-built graph routes agent -> tools -> agent without a live LLM.

A scripted fake model returns fixed messages, so these tests run in CI with no Ollama.
"""

from collections.abc import Iterator
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph, run_turn, strip_think


class ScriptedChatModel(GenericFakeChatModel):
    """Fake chat model that accepts ``bind_tools`` and replays scripted replies."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":  # noqa: ARG002
        return self


@tool
def get_vehicle_status(vehicle_id: int) -> str:
    """Return a fixed status for a vehicle (test stub)."""
    return f'{{"vehicle": {{"vehicle_id": {vehicle_id}}}}}'


def _script(replies: list[AIMessage]) -> Iterator[AIMessage]:
    yield from replies


def test_tool_call_then_final_answer_routes_correctly():
    model = ScriptedChatModel(
        messages=_script(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "get_vehicle_status", "args": {"vehicle_id": 284}, "id": "c1"}],
                ),
                AIMessage(content="Truck 284 is active."),
            ]
        )
    )
    graph = build_graph(model=model, tools=[get_vehicle_status], checkpointer=MemorySaver())

    result = run_turn(graph, "Where is truck 284?", thread_id="t1")

    assert result.tool_calls == [{"name": "get_vehicle_status", "args": {"vehicle_id": 284}}]
    assert result.answer == "Truck 284 is active."


def test_direct_answer_makes_no_tool_calls():
    model = ScriptedChatModel(messages=_script([AIMessage(content="Hello.")]))
    graph = build_graph(model=model, tools=[get_vehicle_status], checkpointer=MemorySaver())

    result = run_turn(graph, "Hi", thread_id="t2")

    assert result.tool_calls == []
    assert result.answer == "Hello."


def test_think_blocks_are_removed_from_answers():
    model = ScriptedChatModel(
        messages=_script([AIMessage(content="<think>reasoning here</think>\nTruck 284 is active.")])
    )
    graph = build_graph(model=model, tools=[get_vehicle_status], checkpointer=MemorySaver())

    result = run_turn(graph, "Status?", thread_id="t3")

    assert result.answer == "Truck 284 is active."


def test_strip_think_leaves_plain_text_unchanged():
    message = AIMessage(content="No reasoning tags here.")
    assert strip_think(message).content == "No reasoning tags here."
