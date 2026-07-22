from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    system_prompt: str = ""
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=4096)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    found_in_materials: bool = False


class ChatHistoryEntry(BaseModel):
    id: int
    ip_address: str
    question: str
    answer: str
    timestamp: datetime
    found_in_materials: bool


class UploadResponse(BaseModel):
    status: str
    message: str
