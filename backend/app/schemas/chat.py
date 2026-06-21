from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user message to the AI assistant.")
    session_id: Optional[str] = Field(None, description="The unique session/thread identifier.")

class ChatMessageResponse(BaseModel):
    id: str = Field(..., description="Unique message identifier.")
    role: str = Field("assistant", description="Role of the message author.")
    content: str = Field(..., description="The content of the message.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the message was created.")

class ChatResponse(BaseModel):
    session_id: str = Field(..., description="The session identifier linked to the conversation thread.")
    message: ChatMessageResponse = Field(..., description="The generated assistant message response.")
