"""Updated chat API using the new core ADK agent."""
from typing import List, Literal, Optional
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from app.agent.core_agent import IDPAgent
from app.agent.events import AgentEvent
from app.settings import settings


router = APIRouter(prefix="/chat/v2", tags=["chat-v2"])


Role = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    conversation_id: Optional[str] = None
    stream: bool = True


class ClarificationRequest(BaseModel):
    conversation_id: str
    response: str
    original_message: str
    run_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    run_id: str
    reply: str
    clarification_needed: bool = False
    missing_fields: Optional[List[str]] = None
    events: Optional[List[dict]] = None


# Global agent instance
agent_instance = None


def get_agent() -> IDPAgent:
    """Get or create the global agent instance."""
    global agent_instance
    if agent_instance is None:
        agent_instance = IDPAgent(settings.sqlite_db_path)
    return agent_instance


@router.post("/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest) -> ChatResponse:
    """Process a chat message (non-streaming version)."""
    # Get the last user message
    last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
    if last_user is None:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    
    agent = get_agent()
    events = []
    final_reply = ""
    clarification_needed = False
    missing_fields = []
    
    try:
        # Process message and collect events
        async for event in agent.process_message(conversation_id, last_user.content, run_id):
            event_dict = {
                "id": event.id,
                "type": event.type.value,
                "message": event.message,
                "timestamp": event.timestamp,
                "data": event.data
            }
            events.append(event_dict)
            
            # Check for clarification needs
            if event.type.value == "agent_clarification":
                clarification_needed = True
                if event.data and "required_fields" in event.data:
                    missing_fields = event.data["required_fields"]
                final_reply = event.message
            elif event.type.value == "agent_message":
                if event.data and "content" in event.data:
                    final_reply = event.data["content"]
                else:
                    final_reply = event.message
            elif event.type.value == "agent_completed":
                final_reply = event.message
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")
    
    return ChatResponse(
        conversation_id=conversation_id,
        run_id=run_id,
        reply=final_reply or "Processing complete",
        clarification_needed=clarification_needed,
        missing_fields=missing_fields if missing_fields else None,
        events=events
    )


@router.options("/stream")
async def chat_stream_options():
    """Handle OPTIONS request for stream endpoint."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Process a chat message with streaming response."""
    # Get the last user message
    last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
    if last_user is None:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    
    agent = get_agent()
    
    async def event_stream():
        """Stream agent events as Server-Sent Events."""
        try:
            async for event in agent.process_message(conversation_id, last_user.content, run_id):
                # Convert event to SSE format
                event_data = {
                    "id": event.id,
                    "type": event.type.value,
                    "message": event.message,
                    "timestamp": event.timestamp,
                    "run_id": event.run_id,
                    "conversation_id": event.conversation_id,
                    "data": event.data
                }
                
                # Format as SSE
                sse_data = f"data: {json.dumps(event_data)}\n\n"
                yield sse_data
            
            # Send completion event
            completion_event = {
                "id": f"completion_{uuid.uuid4().hex[:8]}",
                "type": "stream_complete",
                "message": "Stream completed",
                "timestamp": 0,
                "run_id": run_id,
                "conversation_id": conversation_id,
                "data": None
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as e:
            # Send error event
            error_event = {
                "id": f"error_{uuid.uuid4().hex[:8]}",
                "type": "stream_error",
                "message": f"Stream error: {str(e)}",
                "timestamp": 0,
                "run_id": run_id,
                "conversation_id": conversation_id,
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.post("/clarification")
async def handle_clarification(request: ClarificationRequest):
    """Handle clarification response and continue conversation."""
    agent = get_agent()
    run_id = request.run_id or f"run_{uuid.uuid4().hex[:8]}"
    
    async def clarification_stream():
        """Stream clarification handling events."""
        try:
            async for event in agent.handle_clarification(
                request.conversation_id, 
                request.response, 
                request.original_message,
                run_id
            ):
                # Convert event to SSE format
                event_data = {
                    "id": event.id,
                    "type": event.type.value,
                    "message": event.message,
                    "timestamp": event.timestamp,
                    "run_id": event.run_id,
                    "conversation_id": event.conversation_id,
                    "data": event.data
                }
                
                # Format as SSE
                sse_data = f"data: {json.dumps(event_data)}\n\n"
                yield sse_data
            
            # Send completion event
            completion_event = {
                "id": f"completion_{uuid.uuid4().hex[:8]}",
                "type": "stream_complete",
                "message": "Clarification stream completed",
                "timestamp": 0,
                "run_id": run_id,
                "conversation_id": request.conversation_id,
                "data": None
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as e:
            # Send error event
            error_event = {
                "id": f"error_{uuid.uuid4().hex[:8]}",
                "type": "stream_error",
                "message": f"Clarification error: {str(e)}",
                "timestamp": 0,
                "run_id": run_id,
                "conversation_id": request.conversation_id,
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        clarification_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/conversation/{conversation_id}/history")
async def get_conversation_history(conversation_id: str):
    """Get conversation history for a given conversation ID."""
    agent = get_agent()
    
    try:
        interactions = await agent.memory.load_context(conversation_id)
        
        history = []
        for interaction in interactions:
            history.append({
                "id": interaction.id,
                "user_message": interaction.user_message,
                "agent_response": interaction.agent_response,
                "tool_calls": interaction.tool_calls,
                "tool_results": interaction.tool_results,
                "reasoning": interaction.reasoning,
                "timestamp": interaction.timestamp,
                "metadata": interaction.metadata
            })
        
        return {
            "conversation_id": conversation_id,
            "interactions": history,
            "total_interactions": len(history)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load conversation history: {str(e)}")


@router.delete("/conversation/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """Clear conversation history."""
    agent = get_agent()
    
    try:
        await agent.memory.clear_context(conversation_id)
        return {
            "conversation_id": conversation_id,
            "message": "Conversation cleared successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear conversation: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for the chat API."""
    agent = get_agent()
    
    return {
        "status": "healthy",
        "adk_available": agent._adk_available,
        "agent_engine": "adk" if agent._adk_available else "fallback",
        "database_path": agent.db_path
    }