"""Debug script to test RAG agent end-to-end."""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env
agent_v2_dir = Path('capstone/agent_v2')
dotenv_path = agent_v2_dir / '.env'
load_dotenv(dotenv_path=dotenv_path)

from capstone.agent_v2.agent import Agent

async def test_rag_agent():
    print("Creating RAG agent...")
    agent = Agent.create_rag_agent(
        session_id='test_debug_001',
        user_context={'user_id': 'ms-user', 'org_id': 'MS-corp', 'scope': 'shared'}
    )

    print(f"Agent created: {agent.name}")
    print(f"Tools: {[tool.name for tool in agent.tools]}")

    query = "welche EINSTELLUNGEN gibt es IM MITARBEITER-HR"
    print(f"\nExecuting query: {query}\n")

    event_count = 0
    async for event in agent.execute(query, 'test_debug_001'):
        event_count += 1
        event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)

        if event_type == "thought":
            thought = event.data.get('thought', {})
            print(f"\n[THOUGHT {event.data.get('step')}] {thought.get('rationale', '')[:80]}...")
            action = thought.get('action', {})
            if action.get('tool'):
                print(f"  Tool: {action['tool']}")
                print(f"  Input: {action.get('tool_input', {})}")

        elif event_type == "tool_result":
            success = event.data.get('success')
            results = event.data.get('results', [])
            print(f"[TOOL_RESULT] Success: {success}, Results: {len(results)}")
            if not success:
                print(f"  Error: {event.data.get('error')}")
            if results:
                print(f"  First result ID: {results[0].get('content_id', '')[:50]}")

        elif event_type == "complete":
            message = event.data.get('message') or event.data.get('summary')
            if message:
                print(f"\n[COMPLETE] {message[:200]}")
            else:
                print(f"\n[COMPLETE] (no message)")

    print(f"\nTotal events: {event_count}")

if __name__ == "__main__":
    asyncio.run(test_rag_agent())
