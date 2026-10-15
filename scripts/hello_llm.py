"""Module 2.1: confirm the local model answers. Run: python -m scripts.hello_llm"""

from agent.llm import get_llm


def main() -> None:
    llm = get_llm()
    print(f"model: {llm.model}  base_url: {llm.base_url}")
    response = llm.invoke("In one sentence, what is a reefer truck?")
    print(response.content)
    meta = response.response_metadata
    print(f"tokens generated: {meta.get('eval_count')}  total duration (ns): {meta.get('total_duration')}")


if __name__ == "__main__":
    main()
