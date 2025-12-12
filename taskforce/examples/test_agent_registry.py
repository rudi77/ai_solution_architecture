"""
Example: Using the Agent Registry API
======================================

Demonstrates CRUD operations on custom agents via REST API.

Usage:
    1. Start the server: python start_server.py
    2. Run this script: python examples/test_agent_registry.py
"""

import requests

BASE_URL = "http://localhost:8070/api/v1"


def main():
    print("🧪 Testing Agent Registry API\n")

    # 1. Create a custom agent
    print("1️⃣ Creating custom agent...")
    create_payload = {
        "agent_id": "invoice-extractor",
        "name": "Invoice Extractor",
        "description": "Extracts structured fields from invoice text.",
        "system_prompt": "You are a LeanAgent specialized in invoice extraction. Extract key fields like invoice number, date, total, vendor name.",
        "tool_allowlist": ["file_read", "python"],
        "mcp_servers": [],
        "mcp_tool_allowlist": [],
    }
    response = requests.post(f"{BASE_URL}/agents", json=create_payload)
    if response.status_code == 201:
        print(f"✅ Created agent: {response.json()['agent_id']}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return

    # 2. Get the agent
    print("\n2️⃣ Retrieving agent...")
    response = requests.get(f"{BASE_URL}/agents/invoice-extractor")
    if response.status_code == 200:
        agent = response.json()
        print(f"✅ Retrieved: {agent['name']}")
        print(f"   Description: {agent['description']}")
        print(f"   Tools: {agent['tool_allowlist']}")
    else:
        print(f"❌ Failed: {response.status_code}")

    # 3. List all agents
    print("\n3️⃣ Listing all agents...")
    response = requests.get(f"{BASE_URL}/agents")
    if response.status_code == 200:
        agents = response.json()["agents"]
        custom_count = sum(1 for a in agents if a["source"] == "custom")
        profile_count = sum(1 for a in agents if a["source"] == "profile")
        print(f"✅ Found {len(agents)} agents:")
        print(f"   - {custom_count} custom agents")
        print(f"   - {profile_count} profile agents")
    else:
        print(f"❌ Failed: {response.status_code}")

    # 4. Update the agent
    print("\n4️⃣ Updating agent...")
    update_payload = {
        "name": "Invoice Extractor Pro",
        "description": "Enhanced invoice extraction with ML validation.",
        "system_prompt": "You are an advanced LeanAgent specialized in invoice extraction with ML-based validation.",
        "tool_allowlist": ["file_read", "python", "llm"],
        "mcp_servers": [],
        "mcp_tool_allowlist": [],
    }
    response = requests.put(
        f"{BASE_URL}/agents/invoice-extractor", json=update_payload
    )
    if response.status_code == 200:
        updated = response.json()
        print(f"✅ Updated: {updated['name']}")
        print(f"   New tools: {updated['tool_allowlist']}")
    else:
        print(f"❌ Failed: {response.status_code}")

    # 5. Delete the agent
    print("\n5️⃣ Deleting agent...")
    response = requests.delete(f"{BASE_URL}/agents/invoice-extractor")
    if response.status_code == 204:
        print("✅ Agent deleted successfully")
    else:
        print(f"❌ Failed: {response.status_code}")

    # 6. Verify deletion
    print("\n6️⃣ Verifying deletion...")
    response = requests.get(f"{BASE_URL}/agents/invoice-extractor")
    if response.status_code == 404:
        print("✅ Agent not found (expected)")
    else:
        print(f"❌ Agent still exists: {response.status_code}")

    print("\n✨ All tests completed!")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server.")
        print("   Please start the server first: python start_server.py")

