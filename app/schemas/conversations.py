from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional,  Union

class FileData(BaseModel):
    name: str
    type: str
    file: Union[str, bytes]

class Message(BaseModel):
    content: Optional[str] = None
    files: Optional[List[FileData]] = None
    timestamp: datetime

class ProcessedMessage(BaseModel):
    content: Optional[str] = None
    images: Optional[List[str]] = None
    context: Optional[List[str]] = None
    recent_conversations: Optional[List[str]] = None

class WebSearchResponse(BaseModel):
    content: str
    search_result: str
    url: str
    title: str
    score: Optional[float] = None

class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    messages: List[Message] = Field(default_factory=list)

class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="New title for the conversation")