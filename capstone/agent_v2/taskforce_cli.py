# taskforce_cli.py
import asyncio
import os
from conversation_manager import ConversationManager
from hybrid_agent import HybridAgent

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    agent = HybridAgent(api_key=api_key, enable_planning=True, plan_save_dir="./execution_plans")

    cm = ConversationManager(session_id="local-cli", agent=agent)
    cm.start()  # no mission yet; user will type first

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
        for m in reversed(cm.history()):
            if m["role"] == "assistant":
                print(f"Agent: {m['content'][:800]}")
                break

if __name__ == "__main__":
    asyncio.run(main())
