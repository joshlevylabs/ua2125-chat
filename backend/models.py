"""
Pydantic models for request/response validation
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request from frontend"""
    message: str = Field(..., description="User's message", min_length=1)
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=[],
        description="Previous conversation history for context"
    )


class Source(BaseModel):
    """Source document information"""
    content: str = Field(..., description="Relevant content snippet")
    source: str = Field(..., description="Source document/page")
    similarity: float = Field(..., description="Similarity score")


class ChatResponse(BaseModel):
    """Chat response to frontend"""
    response: str = Field(..., description="AI assistant's response")
    sources: List[Source] = Field(
        default=[],
        description="Source documents used"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID for tracking"
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    embeddings_loaded: bool
    documents_count: int


class DocumentChunk(BaseModel):
    """Document chunk for ingestion"""
    content: str
    metadata: dict
    source: str
    chunk_id: str


class IngestRequest(BaseModel):
    """Request to ingest a document into the knowledge base"""
    content: str = Field(..., description="Document content to ingest")
    title: Optional[str] = Field(None, description="Document title")
    category: str = Field(default="general", description="Document category")
    source: str = Field(default="sonance-beta-portal", description="Source identifier")
    tags: Optional[List[str]] = Field(default=[], description="Tags for categorization")
    priority: str = Field(default="medium", description="Priority level")
    metadata: Optional[dict] = Field(default={}, description="Additional metadata")


class IngestResponse(BaseModel):
    """Response after ingesting a document"""
    success: bool = Field(..., description="Whether ingestion was successful")
    document_id: Optional[int] = Field(None, description="ID of the created document")
    message: Optional[str] = Field(None, description="Status message")
