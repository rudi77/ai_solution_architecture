from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional


from capstone.examples.idp_pack.idp_tools import get_idp_tools
from capstone.prototype.agent import ReActAgent
from capstone.prototype.llm_provider import OpenAIProvider
from capstone.prototype.tools_builtin import AGENT_TOOLS



def load_text(path: Path) -> str:
	"""Load text file content."""
	return path.read_text(encoding="utf-8")


async def main() -> None:
	root = Path(__file__).resolve().parents[2]
	# Orchestrator mission
	orch_path = root / "examples" / "idp_pack" / "prompts" / "orchestrator.txt"
	orch_system_prompt = load_text(orch_path)

	mission_path = root / "examples" / "idp_pack" / "prompts" / "mission_git.txt"
	mission = load_text(mission_path)

    # Initialize LLM provider with fallback to mock if no API key
	openai_key = os.getenv("OPENAI_API_KEY")

	provider = OpenAIProvider(api_key=openai_key)

	# Sub-agent with Git tools (no mission → empty <Mission> in sub-agent)
	git_tools = get_idp_tools()
	git_agent = ReActAgent(
		system_prompt=None,
		llm=provider,
		tools=git_tools,
		mission=None,
	)

	# Orchestrator only knows the sub-agent tool (delegation)
	orchestrator = ReActAgent(
		system_prompt=orch_system_prompt,
		llm=provider,
		tools=[
			git_agent.to_tool(
				name="agent_git",
				description="Git sub-agent",
				allowed_tools=[t.name for t in git_tools],
				budget={"max_steps": 12},				
			),
		],
		mission=mission,
	)

	print("=" * 80)
	print("IDP Pack CLI - minimal Git workflow example")
	print("Type 'exit' to quit.")
	print("=" * 80)

	session_id: Optional[str] = None
	print("\nRoles:\n- Orchestrator (delegates)\n- Sub-Agent (does the work)\n")
	while True:
		msg = input("You: ").strip()
		if msg.lower() in {"", "exit", "quit", "q"}:
			break
		async for update in orchestrator.process_request(msg, session_id=session_id):
			print(update, end="", flush=True)
		session_id = orchestrator.session_id
		if orchestrator.context.get("awaiting_user_input"):
			continue
		print("")


if __name__ == "__main__":
	asyncio.run(main())
