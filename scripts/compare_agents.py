"""Module 2.6: compare the prebuilt ReAct agent with the hand-built graph on one question.

Usage (from the repo root):
    python -m scripts.compare_agents "Which refrigerated vehicles are in Texas?"
"""

from __future__ import annotations

import sys

from langgraph.prebuilt import create_react_agent

from agent.graph import build_graph, run_turn
from agent.llm import get_llm
from agent.prompts import SYSTEM_PROMPT
from agent.tools.sql_tool import SQL_TOOLS

DEFAULT_QUESTION = "Which refrigerated vehicles are in Texas?"


def _tool_names(messages) -> list[str]:
    names: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            names.append(call["name"])
    return names


def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    llm = get_llm()

    react = create_react_agent(llm, SQL_TOOLS, prompt=SYSTEM_PROMPT)
    react_state = react.invoke({"messages": [("user", question)]}, {"recursion_limit": 12})
    react_answer = react_state["messages"][-1].content
    print("## Prebuilt create_react_agent")
    print("Tools called:", _tool_names(react_state["messages"]))
    print("Answer:", react_answer, "\n")

    graph = build_graph(model=llm)
    result = run_turn(graph, question, thread_id="compare-custom")
    print("## Custom graph (agent <-> tools)")
    print("Tools called:", [c["name"] for c in result.tool_calls])
    print("Answer:", result.answer, "\n")

    print("## Custom graph structure (Mermaid)")
    print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
