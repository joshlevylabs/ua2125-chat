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


# =============================================================================
# CONVERSATION MANAGEMENT MODELS
# =============================================================================

class ConversationCreate(BaseModel):
    """Request to create a new conversation"""
    user_id: str = Field(..., description="User identifier")
    title: Optional[str] = Field(None, description="Optional conversation title")
    platform: str = Field(default="sonance-beta", description="Platform identifier")


class ConversationUpdate(BaseModel):
    """Request to update a conversation"""
    title: Optional[str] = Field(None, description="New conversation title")
    is_pinned: Optional[bool] = Field(None, description="Pin/unpin conversation")
    is_archived: Optional[bool] = Field(None, description="Archive/unarchive conversation")


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display"""
    id: str = Field(..., description="Conversation UUID")
    title: Optional[str] = Field(None, description="Conversation title")
    user_id: Optional[str] = Field(None, description="User identifier")
    platform: str = Field(default="web", description="Platform")
    started_at: str = Field(..., description="When conversation started")
    last_message_at: str = Field(..., description="When last message was sent")
    message_count: int = Field(default=0, description="Number of messages")
    last_message: Optional[str] = Field(None, description="Preview of last message")
    is_pinned: bool = Field(default=False, description="Is conversation pinned")
    is_archived: bool = Field(default=False, description="Is conversation archived")


class ConversationListResponse(BaseModel):
    """Response containing list of conversations"""
    conversations: List[ConversationSummary] = Field(default=[], description="List of conversations")
    total: int = Field(..., description="Total number of conversations")


class MessageDetail(BaseModel):
    """Detailed message information"""
    id: int = Field(..., description="Message ID")
    role: str = Field(..., description="Role: user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")
    sources: Optional[List[Source]] = Field(None, description="Retrieved sources (for assistant messages)")


class ConversationDetail(BaseModel):
    """Full conversation with all messages"""
    id: str = Field(..., description="Conversation UUID")
    title: Optional[str] = Field(None, description="Conversation title")
    user_id: Optional[str] = Field(None, description="User identifier")
    platform: str = Field(default="web", description="Platform")
    started_at: str = Field(..., description="When conversation started")
    last_message_at: str = Field(..., description="When last message was sent")
    is_pinned: bool = Field(default=False, description="Is conversation pinned")
    is_archived: bool = Field(default=False, description="Is conversation archived")
    messages: List[MessageDetail] = Field(default=[], description="All messages in conversation")


class SearchResult(BaseModel):
    """Single search result"""
    conversation_id: str = Field(..., description="Conversation UUID")
    conversation_title: Optional[str] = Field(None, description="Conversation title")
    message_id: int = Field(..., description="Message ID")
    message_role: str = Field(..., description="Role of message")
    message_content: str = Field(..., description="Message content")
    message_timestamp: str = Field(..., description="Message timestamp")
    relevance: float = Field(..., description="Search relevance score")
    highlight: Optional[str] = Field(None, description="Highlighted snippet")


class SearchResponse(BaseModel):
    """Response containing search results"""
    results: List[SearchResult] = Field(default=[], description="Search results")
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Search query used")


class ChatRequestWithUser(BaseModel):
    """Chat request with user identification"""
    message: str = Field(..., description="User's message", min_length=1)
    user_id: str = Field(..., description="User identifier for conversation tracking")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID, or create new")
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=[],
        description="Previous conversation history for context"
    )
