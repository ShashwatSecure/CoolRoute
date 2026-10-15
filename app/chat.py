"""Chat page: the CoolRoute dispatch assistant (Module 2.7).

Each browser session gets its own LangGraph ``thread_id`` so the agent remembers the
conversation. The compiled graph is cached once per process with ``st.cache_resource``.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage

from agent.graph import build_graph, stream_turn

EXAMPLE_QUESTIONS = (
    "Which refrigerated vehicles are in Texas?",
    "Show Truck 284 temperature last 6 hours",
    "Where is truck 284 and is its cargo within range?",
)


@st.cache_resource
def get_graph():
    return build_graph()


def _init_session() -> None:
    if "chat_thread_id" not in st.session_state:
        st.session_state.chat_thread_id = str(uuid.uuid4())
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def _format_call(call: dict[str, Any]) -> str:
    args = ", ".join(f"{key}={value}" for key, value in call["args"].items())
    return f"{call['name']}({args})"


def _render_tool_calls(calls: list[dict[str, Any]]) -> None:
    if not calls:
        return
    with st.expander(f"Tool calls ({len(calls)})"):
        for call in calls:
            st.code(_format_call(call))


def _answer(question: str) -> None:
    """Stream one turn: show tool steps live, then the final answer."""
    graph = get_graph()
    calls: list[dict[str, Any]] = []
    answer = ""

    with st.chat_message("assistant"):
        status = st.status("Working on it...", expanded=True)
        try:
            for update in stream_turn(graph, question, st.session_state.chat_thread_id):
                for payload in (update or {}).values():
                    for message in (payload or {}).get("messages", []):
                        if isinstance(message, AIMessage) and message.tool_calls:
                            for call in message.tool_calls:
                                entry = {"name": call["name"], "args": call["args"]}
                                calls.append(entry)
                                status.write(f"Calling `{_format_call(entry)}`")
                        elif isinstance(message, AIMessage) and message.content:
                            answer = str(message.content)
                        elif isinstance(message, ToolMessage):
                            status.write("Tool returned a result")
            status.update(label="Done", state="complete", expanded=False)
        except Exception as exc:  # show the failure in the chat instead of crashing the page
            status.update(label="Failed", state="error")
            answer = f"Sorry, the assistant hit an error: {type(exc).__name__}: {exc}"

        st.markdown(answer or "No answer was returned.")
        _render_tool_calls(calls)

    st.session_state.chat_history.append({"role": "user", "content": question, "tool_calls": []})
    st.session_state.chat_history.append({"role": "assistant", "content": answer, "tool_calls": calls})


def show_chat() -> None:
    st.title("Dispatch Assistant")
    st.caption("Ask about trucks, shipments, and cargo temperatures. Answers come from live database queries.")
    _init_session()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_tool_calls(message["tool_calls"])

    if not st.session_state.chat_history:
        st.caption("Try: " + " | ".join(EXAMPLE_QUESTIONS))

    question = st.chat_input("Ask the dispatch assistant")
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        _answer(question)
