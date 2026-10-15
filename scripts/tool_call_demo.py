"""Module 2.2: show the model choosing a tool and the manual tool loop. Run: python -m scripts.tool_call_demo"""

from langchain_core.messages import HumanMessage, ToolMessage

from agent.graph import strip_think
from agent.llm import get_llm
from agent.prompts import SYSTEM_PROMPT
from agent.tools.sql_tool import get_vehicle_status


def main() -> None:
    llm = get_llm().bind_tools([get_vehicle_status])
    messages = [
        ("system", SYSTEM_PROMPT),
        HumanMessage("Where is truck 284?"),
    ]

    first = llm.invoke(messages)
    print("tool calls:", first.tool_calls)
    if not first.tool_calls:
        print("model answered without a tool:", first.content)
        return

    messages.append(first)
    for call in first.tool_calls:
        result = get_vehicle_status.invoke(call["args"])
        print(f"tool result for {call['name']}: {result[:200]}...")
        messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

    final = strip_think(llm.invoke(messages))
    print("answer:", final.content)


if __name__ == "__main__":
    main()
