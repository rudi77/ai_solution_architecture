from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.conversation.service import store


router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
	id: str = Field(min_length=3)


class ConversationResponse(BaseModel):
	id: str
	messages: List[dict]


class PostMessageRequest(BaseModel):
	role: str
	content: str


@router.post("", response_model=ConversationResponse)
async def create_conversation(payload: CreateConversationRequest) -> ConversationResponse:
	conv = store.create(payload.id)
	return ConversationResponse(id=conv.id, messages=[m.__dict__ for m in conv.messages])


@router.post("/{conversation_id}/messages", response_model=ConversationResponse)
async def post_message(conversation_id: str, payload: PostMessageRequest) -> ConversationResponse:
	conv = store.get(conversation_id)
	if conv is None:
		raise HTTPException(status_code=404, detail="Conversation not found")
	store.add_message(conversation_id, payload.role, payload.content)
	return ConversationResponse(id=conversation_id, messages=[m.__dict__ for m in store.get(conversation_id).messages])


