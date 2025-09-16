# taskforce_cli.py
import asyncio
import os
import argparse
from capstone.agent_v2.conversation_manager import ConversationManager
from capstone.agent_v2.hybrid_agent import HybridAgent

async def main():
    parser = argparse.ArgumentParser(description="TaskForce CLI")
    parser.add_argument("--mission", type=str, default=None, help="Initial mission text")
    parser.add_argument("--model", type=str, default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--temperature", type=float, default=float(os.getenv("OPENAI_TEMPERATURE", 0.7)))
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    agent = HybridAgent(
        api_key=api_key,
        model=args.model,
        enable_planning=True,
        plan_save_dir="./execution_plans",
        temperature=args.temperature,
    )

    cm = ConversationManager(session_id="local-cli", agent=agent)
    await cm.start(args.mission)

    print("TaskForce-CLI. Type 'exit' to quit.")
    while True:
        user = input("You: ").strip()
        if user.lower() in {"exit", "quit"}:
            break

        result = await cm.user_says(user)

        if result.get("needs_user_input") and result.get("question"):
            print(f"Agent needs info: {result['question']}")
            continue

        # Show tool-results (compact)
        rlist = result.get("results", [])
        if rlist:
            for r in rlist:
                ok = "✓" if r["success"] else "✗"
                print(f"[{ok}] {r['tool']} -> {str(r['result'])[:140]}")

        # Also print the last assistant message (if any)
        for m in reversed(cm.history):
            if m["role"] == "assistant":
                print(f"Agent: {m['content'][:800]}")
                break

if __name__ == "__main__":
    asyncio.run(main())
