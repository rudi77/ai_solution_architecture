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
	prompt_path = root / "examples" / "idp_pack" / "system_prompt_git.txt"
	git_mission = load_text(prompt_path)
	# Generic system prompt shared across agents (IDP principles)
	generic_path = root / "examples" / "idp_pack" / "system_prompt_idp.txt"
	generic = load_text(generic_path)
	# Orchestrator mission
	orch_path = root / "examples" / "idp_pack" / "prompts" / "orchestrator.txt"
	orch_mission = load_text(orch_path)

    # Initialize LLM provider with fallback to mock if no API key
	openai_key = os.getenv("OPENAI_API_KEY")

	provider = OpenAIProvider(api_key=openai_key)

	# Sub-agent with Git tools
	git_tools = get_idp_tools()
	git_agent = ReActAgent(
		system_prompt=None,
		llm=provider,
		tools=git_tools,
		mission=git_mission,
		generic_system_prompt=generic,
	)

	# Orchestrator only knows the sub-agent tool (delegation)
	orchestrator = ReActAgent(
		system_prompt=None,
		llm=provider,
		tools=[
			git_agent.to_tool(
				name="agent_git",
				description="Git sub-agent",
				allowed_tools=[t.name for t in git_tools],
				budget={"max_steps": 12},
				mission_override=git_mission,
			),
		],
		mission=orch_mission,
		generic_system_prompt=generic,
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
