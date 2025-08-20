"""Proper ADK lifecycle management replacing the old adk_adapter."""
from __future__ import annotations

import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from app.agent.events import AgentEvent, AgentEventType, create_agent_event
from app.settings import settings


class ADKManager:
    """Proper ADK lifecycle manager with robust error handling and integration.
    
    This class replaces the old adk_adapter.py with a more sophisticated
    approach to managing Google ADK agents throughout their lifecycle.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._agent_cache: Dict[str, Any] = {}
        self._adk_available = self._check_adk_availability()
    
    def _check_adk_availability(self) -> bool:
        """Check if Google ADK is available and properly configured."""
        try:
            import google.adk
            from google.adk.agents import Agent
            
            # Test basic agent creation
            test_agent = Agent(
                name="test_agent",
                model="gemini-2.0-flash",
                instruction="Test agent",
                description="Test",
                tools=[]
            )
            
            # Check if agent has required methods
            for method in ["run", "execute", "invoke"]:
                if hasattr(test_agent, method):
                    return True
            
            return False
            
        except Exception as e:
            print(f"ADK availability check failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Return True if ADK is available and functional."""
        return self._adk_available
    
    def create_agent(
        self,
        name: str,
        instruction: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Any]] = None
    ) -> Optional[Any]:
        """Create a new ADK agent with proper configuration.
        
        Args:
            name: Agent name
            instruction: System instruction for the agent
            description: Optional agent description
            model: Model to use (defaults to settings)
            tools: List of tools to provide to the agent
            
        Returns:
            ADK Agent instance or None if ADK is unavailable
        """
        if not self._adk_available:
            return None
        
        try:
            from google.adk.agents import Agent
            
            agent = Agent(
                name=name,
                model=model or getattr(settings, "adk_model", "gemini-2.0-flash"),
                instruction=instruction,
                description=description or f"{name} agent",
                tools=tools or []
            )
            
            # Cache the agent
            self._agent_cache[name] = agent
            return agent
            
        except Exception as e:
            print(f"Failed to create ADK agent '{name}': {e}")
            return None
    
    def get_cached_agent(self, name: str) -> Optional[Any]:
        """Get a cached agent by name."""
        return self._agent_cache.get(name)
    
    def clear_agent_cache(self, name: Optional[str] = None):
        """Clear agent cache (specific agent or all)."""
        if name:
            self._agent_cache.pop(name, None)
        else:
            self._agent_cache.clear()
    
    async def execute_agent(
        self,
        agent: Any,
        prompt: str,
        conversation_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """Execute an ADK agent and stream events.
        
        Args:
            agent: ADK Agent instance
            prompt: Input prompt for the agent
            conversation_id: Optional conversation identifier
            run_id: Optional run identifier
            
        Yields:
            AgentEvent: Stream of agent execution events
        """
        if run_id is None:
            run_id = f"adk_run_{uuid.uuid4().hex[:8]}"
        
        yield create_agent_event(
            AgentEventType.THINKING,
            "Starting ADK agent execution",
            run_id=run_id,
            conversation_id=conversation_id,
            reasoning="Initializing ADK agent processing"
        )
        
        try:
            # Find the appropriate execution method
            execution_method = None
            for method_name in ["run", "execute", "invoke"]:
                method = getattr(agent, method_name, None)
                if callable(method):
                    execution_method = method
                    break
            
            if execution_method is None:
                yield create_agent_event(
                    AgentEventType.ERROR,
                    "No valid execution method found on ADK agent",
                    run_id=run_id,
                    conversation_id=conversation_id
                )
                return
            
            yield create_agent_event(
                AgentEventType.THINKING,
                f"Executing agent using method: {execution_method.__name__}",
                run_id=run_id,
                conversation_id=conversation_id,
                reasoning="Found valid execution method on agent"
            )
            
            # Execute the agent
            start_time = time.time()
            result = execution_method(prompt)
            execution_time = time.time() - start_time
            
            # Process the result
            if result is not None:
                result_text = str(result)
                
                yield create_agent_event(
                    AgentEventType.MESSAGE,
                    "ADK agent execution completed",
                    run_id=run_id,
                    conversation_id=conversation_id,
                    content=result_text
                )
                
                # Try to extract structured information from result
                yield create_agent_event(
                    AgentEventType.COMPLETED,
                    f"Agent execution completed in {execution_time:.2f}s",
                    run_id=run_id,
                    conversation_id=conversation_id
                )
            else:
                yield create_agent_event(
                    AgentEventType.ERROR,
                    "ADK agent returned no result",
                    run_id=run_id,
                    conversation_id=conversation_id
                )
        
        except Exception as e:
            yield create_agent_event(
                AgentEventType.ERROR,
                f"ADK agent execution failed: {str(e)}",
                run_id=run_id,
                conversation_id=conversation_id
            )
    
    async def execute_with_streaming(
        self,
        agent_name: str,
        instruction: str,
        prompt: str,
        tools: Optional[List[Any]] = None,
        conversation_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """Create and execute an agent with streaming response.
        
        Args:
            agent_name: Name for the agent
            instruction: System instruction
            prompt: User prompt
            tools: Optional tools list
            conversation_id: Optional conversation ID
            run_id: Optional run ID
            
        Yields:
            AgentEvent: Stream of execution events
        """
        if not self._adk_available:
            yield create_agent_event(
                AgentEventType.ERROR,
                "ADK is not available. Please install and configure Google ADK.",
                run_id=run_id,
                conversation_id=conversation_id
            )
            return
        
        # Try to get cached agent first
        agent = self.get_cached_agent(agent_name)
        
        if agent is None:
            yield create_agent_event(
                AgentEventType.THINKING,
                f"Creating new ADK agent: {agent_name}",
                run_id=run_id,
                conversation_id=conversation_id
            )
            
            agent = self.create_agent(
                name=agent_name,
                instruction=instruction,
                tools=tools
            )
            
            if agent is None:
                yield create_agent_event(
                    AgentEventType.ERROR,
                    f"Failed to create ADK agent: {agent_name}",
                    run_id=run_id,
                    conversation_id=conversation_id
                )
                return
        
        # Execute the agent
        async for event in self.execute_agent(agent, prompt, conversation_id, run_id):
            yield event
    
    def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """Get information about a cached agent."""
        agent = self.get_cached_agent(agent_name)
        if agent is None:
            return {"exists": False}
        
        try:
            return {
                "exists": True,
                "name": getattr(agent, "name", agent_name),
                "model": getattr(agent, "model", "unknown"),
                "description": getattr(agent, "description", ""),
                "has_tools": len(getattr(agent, "tools", [])) > 0,
                "tool_count": len(getattr(agent, "tools", []))
            }
        except Exception as e:
            return {
                "exists": True,
                "error": f"Failed to get agent info: {e}"
            }
    
    def list_cached_agents(self) -> List[str]:
        """List names of all cached agents."""
        return list(self._agent_cache.keys())
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get ADK system status information."""
        status = {
            "adk_available": self._adk_available,
            "cached_agents": len(self._agent_cache),
            "agent_names": list(self._agent_cache.keys())
        }
        
        if self._adk_available:
            try:
                import google.adk
                status["adk_version"] = getattr(google.adk, "__version__", "unknown")
            except Exception:
                status["adk_version"] = "unknown"
        
        return status


# Global ADK manager instance
_adk_manager: Optional[ADKManager] = None


def get_adk_manager(db_path: Optional[str] = None) -> ADKManager:
    """Get or create the global ADK manager instance."""
    global _adk_manager
    if _adk_manager is None:
        if db_path is None:
            db_path = settings.sqlite_db_path
        _adk_manager = ADKManager(db_path)
    return _adk_manager


# Backward compatibility functions (replacing old adk_adapter functions)
def is_available() -> bool:
    """Backward compatibility: Check if ADK is available."""
    manager = get_adk_manager()
    return manager.is_available()


async def execute_stream(prompt: str) -> AsyncIterator[Dict[str, Any]]:
    """Backward compatibility: Execute ADK with streaming.
    
    This function maintains compatibility with the old adk_adapter interface
    while using the new ADK manager underneath.
    """
    manager = get_adk_manager()
    run_id = f"compat_run_{uuid.uuid4().hex[:8]}"
    
    if not manager.is_available():
        yield {
            "id": "run:failed",
            "type": "run_failed",
            "message": "ADK not available",
            "run_id": run_id,
            "timestamp": time.time()
        }
        return
    
    # Execute using new manager
    async for event in manager.execute_with_streaming(
        agent_name="idp_copilot_compat",
        instruction="You are an assistant that plans and executes software project setup tasks.",
        prompt=prompt,
        run_id=run_id
    ):
        # Convert to old format for compatibility
        yield {
            "id": event.id,
            "type": event.type.value,
            "message": event.message,
            "run_id": event.run_id,
            "timestamp": event.timestamp,
            "data": event.data
        }