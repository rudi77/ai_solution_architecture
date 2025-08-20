"""Persistent memory implementation for ADK agents using SQLite."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from app.persistence.sqlite import _connect
from app.agent.events import AgentEvent


@dataclass
class AgentInteraction:
    """Represents a complete agent interaction cycle."""
    id: str
    conversation_id: str
    user_message: str
    agent_response: str
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    reasoning: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


class PersistentMemory:
    """Bridge between ADK memory interface and SQLite persistence.
    
    This class provides conversation continuity for ADK agents by storing
    and retrieving interaction history from SQLite.
    """
    
    def __init__(self, db_path: str, max_context_length: int = 50):
        self.db_path = db_path
        self.max_context_length = max_context_length
        self._init_memory_tables()
    
    def _init_memory_tables(self) -> None:
        """Initialize memory tables in SQLite."""
        with _connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_interactions (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    agent_response TEXT NOT NULL,
                    tool_calls TEXT,  -- JSON array
                    tool_results TEXT,  -- JSON array
                    reasoning TEXT,
                    timestamp REAL NOT NULL,
                    metadata TEXT,  -- JSON object
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_agent_interactions_conv_ts 
                ON agent_interactions(conversation_id, timestamp);
                
                CREATE TABLE IF NOT EXISTS agent_context_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    last_updated REAL NOT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
            """)
            conn.commit()
    
    async def store_interaction(
        self, 
        conversation_id: str, 
        interaction: AgentInteraction
    ) -> None:
        """Store a complete agent interaction."""
        with _connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO agent_interactions 
                (id, conversation_id, user_message, agent_response, tool_calls, 
                 tool_results, reasoning, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.id,
                conversation_id,
                interaction.user_message,
                interaction.agent_response,
                json.dumps(interaction.tool_calls),
                json.dumps(interaction.tool_results),
                interaction.reasoning,
                interaction.timestamp,
                json.dumps(interaction.metadata) if interaction.metadata else None
            ))
            conn.commit()
    
    async def load_context(self, conversation_id: str) -> List[AgentInteraction]:
        """Load conversation history for agent context.
        
        Returns recent interactions up to max_context_length, with optional
        summarization for older interactions.
        """
        with _connect(self.db_path) as conn:
            # Get recent interactions
            cursor = conn.execute("""
                SELECT id, conversation_id, user_message, agent_response, 
                       tool_calls, tool_results, reasoning, timestamp, metadata
                FROM agent_interactions 
                WHERE conversation_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (conversation_id, self.max_context_length))
            
            rows = cursor.fetchall()
            
        interactions = []
        for row in rows:
            interactions.append(AgentInteraction(
                id=row[0],
                conversation_id=row[1],
                user_message=row[2],
                agent_response=row[3],
                tool_calls=json.loads(row[4]) if row[4] else [],
                tool_results=json.loads(row[5]) if row[5] else [],
                reasoning=row[6],
                timestamp=row[7],
                metadata=json.loads(row[8]) if row[8] else None
            ))
        
        # Return in chronological order (oldest first)
        return list(reversed(interactions))
    
    async def get_context_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary for context compression."""
        with _connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT summary FROM agent_context_summaries 
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            row = cursor.fetchone()
            return row[0] if row else None
    
    async def update_context_summary(
        self, 
        conversation_id: str, 
        summary: str
    ) -> None:
        """Update conversation summary for context compression."""
        with _connect(self.db_path) as conn:
            # Count total interactions
            cursor = conn.execute("""
                SELECT COUNT(*) FROM agent_interactions 
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            count = cursor.fetchone()[0]
            
            conn.execute("""
                INSERT OR REPLACE INTO agent_context_summaries 
                (conversation_id, summary, last_updated, interaction_count)
                VALUES (?, ?, ?, ?)
            """, (conversation_id, summary, time.time(), count))
            
            conn.commit()
    
    async def clear_context(self, conversation_id: str) -> None:
        """Clear conversation context and summaries."""
        with _connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM agent_interactions 
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            conn.execute("""
                DELETE FROM agent_context_summaries 
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            conn.commit()
    
    async def get_interaction_count(self, conversation_id: str) -> int:
        """Get total number of interactions in conversation."""
        with _connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM agent_interactions 
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            return cursor.fetchone()[0]
    
    def format_context_for_agent(
        self, 
        interactions: List[AgentInteraction],
        summary: Optional[str] = None
    ) -> str:
        """Format interaction history for ADK agent context.
        
        Creates a structured conversation history that the agent can understand.
        """
        context_parts = []
        
        if summary:
            context_parts.append(f"## Previous Conversation Summary\n{summary}\n")
        
        if interactions:
            context_parts.append("## Recent Conversation History")
            
            for interaction in interactions:
                context_parts.append(f"### User Request")
                context_parts.append(interaction.user_message)
                
                if interaction.reasoning:
                    context_parts.append(f"### Agent Reasoning")
                    context_parts.append(interaction.reasoning)
                
                if interaction.tool_calls:
                    context_parts.append(f"### Tool Calls")
                    for tool_call in interaction.tool_calls:
                        context_parts.append(f"- {tool_call.get('tool_name', 'unknown')}: {tool_call.get('parameters', {})}")
                
                if interaction.tool_results:
                    context_parts.append(f"### Tool Results")
                    for result in interaction.tool_results:
                        status = "✓" if result.get('success', True) else "✗"
                        context_parts.append(f"- {status} {result.get('tool_name', 'unknown')}: {result.get('result', 'no result')}")
                
                context_parts.append(f"### Agent Response")
                context_parts.append(interaction.agent_response)
                context_parts.append("---")
        
        return "\n".join(context_parts)


class ConversationMemory:
    """Simplified alias for PersistentMemory to match plan documentation."""
    
    def __init__(self, db_path: str, max_context_length: int = 50):
        self._memory = PersistentMemory(db_path, max_context_length)
    
    async def store_interaction(self, conversation_id: str, interaction: AgentInteraction):
        return await self._memory.store_interaction(conversation_id, interaction)
    
    async def load_context(self, conversation_id: str) -> List[AgentInteraction]:
        return await self._memory.load_context(conversation_id)
    
    async def clear_context(self, conversation_id: str):
        return await self._memory.clear_context(conversation_id)