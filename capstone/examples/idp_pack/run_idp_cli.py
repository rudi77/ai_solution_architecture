from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional


from capstone.examples.idp_pack.idp_tools import get_idp_tools
from capstone.prototype.agent import ReActAgent
from capstone.prototype.llm_provider import OpenAIProvider



def load_text(path: Path) -> str:
	"""Load text file content."""
	return path.read_text(encoding="utf-8")


async def main() -> None:
	root = Path(__file__).resolve().parents[2]
	prompt_path = root / "examples" / "idp_pack" / "system_prompt_git.txt"
	system_prompt = load_text(prompt_path)

    # Initialize LLM provider with fallback to mock if no API key
	openai_key = os.getenv("OPENAI_API_KEY")

	provider = OpenAIProvider(api_key=openai_key)  # placeholder; relies on env var in provider
	agent = ReActAgent(
		system_prompt=system_prompt,
		llm=provider,
		tools=get_idp_tools(),
	)

	print("=" * 80)
	print("IDP Pack CLI - minimal Git workflow example")
	print("Type 'exit' to quit.")
	print("=" * 80)

	session_id: Optional[str] = None
	while True:
		msg = input("You: ").strip()
		if msg.lower() in {"", "exit", "quit", "q"}:
			break
		async for update in agent.process_request(msg, session_id=session_id):
			print(update, end="", flush=True)
		session_id = agent.session_id
		if agent.context.get("awaiting_user_input"):
			continue
		print("")


if __name__ == "__main__":
	asyncio.run(main())
