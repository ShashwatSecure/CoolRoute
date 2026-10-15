"""Agent state definitions."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Conversation state. ``add_messages`` appends new messages instead of overwriting."""

    messages: Annotated[list[AnyMessage], add_messages]

