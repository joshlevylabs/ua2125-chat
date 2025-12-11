"""
FastAPI application for UA2-125 AI Chatbot Assistant
With conversation history management and search capabilities
"""
import logging
import uuid
import re
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config import HOST, PORT, CORS_ORIGINS, LOG_LEVEL
from models import (
    ChatRequest, ChatResponse, HealthResponse, IngestRequest, IngestResponse,
    ConversationCreate, ConversationUpdate, ConversationSummary, ConversationListResponse,
    ConversationDetail, MessageDetail, SearchResult, SearchResponse, ChatRequestWithUser,
    Source
)
from rag_engine import rag_engine
from db_embeddings_index import db_embeddings_index
from database import get_cursor

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database connection on startup"""
    logger.info("Starting UA2-125 AI Chatbot Assistant...")
    try:
        stats = db_embeddings_index.get_stats()
        logger.info(f"✅ Connected to PostgreSQL database with {stats['total_documents']} documents")
    except Exception as e:
        logger.error(f"⚠️  Database connection failed: {e}")
    yield
    # Cleanup on shutdown (if needed)
    logger.info("Shutting down UA2-125 AI Chatbot Assistant...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="UA2-125 AI Chatbot Assistant",
    description="RAG-based chatbot for Sonance UA2-125 amplifier support",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/", response_class=FileResponse)
async def serve_frontend():
    """Serve frontend HTML"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend not found. Please check frontend directory."}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        stats = db_embeddings_index.get_stats()
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            embeddings_loaded=True,
            documents_count=stats["total_documents"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            embeddings_loaded=False,
            documents_count=0
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint

    Processes user message, retrieves relevant context, and generates response
    """
    try:
        logger.info(f"Received chat request: {request.message[:100]}...")

        # Get or create conversation ID
        conversation_id = request.conversation_id if hasattr(request, 'conversation_id') and request.conversation_id else str(uuid.uuid4())

        # Process chat request
        response_text, sources = rag_engine.chat(
            user_message=request.message,
            conversation_history=request.conversation_history
        )

        # Calculate average similarity for confidence tracking
        avg_similarity = sum(s.similarity for s in sources) / len(sources) if sources else 0.0

        # Save conversation to database
        try:
            with get_cursor() as cursor:
                # Create or update conversation
                cursor.execute("""
                    INSERT INTO conversations (id, started_at)
                    VALUES (%s::uuid, NOW())
                    ON CONFLICT (id) DO NOTHING
                """, (conversation_id,))

                # Save user message
                cursor.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s::uuid, 'user', %s)
                    RETURNING id
                """, (conversation_id, request.message))
                user_msg_id = cursor.fetchone()['id']

                # Save assistant response
                cursor.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s::uuid, 'assistant', %s)
                    RETURNING id
                """, (conversation_id, response_text))

                # Track low-confidence responses (similarity < 0.5)
                if avg_similarity < 0.5 and sources:
                    cursor.execute("""
                        INSERT INTO unanswered_questions (question, confidence, message_id)
                        VALUES (%s, %s, %s)
                    """, (request.message, avg_similarity, user_msg_id))
                    logger.info(f"Logged low-confidence question (similarity: {avg_similarity:.3f})")

        except Exception as db_error:
            logger.error(f"Error saving conversation to database: {db_error}")
            # Continue anyway - don't fail the request if DB save fails

        return ChatResponse(
            response=response_text,
            sources=sources,
            conversation_id=conversation_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request. Please try again."
        )


@app.get("/api/stats")
async def get_stats():
    """Get statistics about the knowledge base"""
    return db_embeddings_index.get_stats()


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest):
    """
    Ingest a document into the knowledge base.
    Called by Sonance Beta portal when bugs are resolved, feedback is reviewed, etc.
    """
    try:
        logger.info(f"Ingesting document: {request.title or 'Untitled'} ({request.category})")

        # Add document to the knowledge base
        doc_id = db_embeddings_index.add_document(
            content=request.content,
            metadata=request.metadata or {},
            source=request.source,
            title=request.title,
            category=request.category,
            tags=request.tags or [],
            priority=request.priority
        )

        if doc_id:
            logger.info(f"Successfully ingested document with ID: {doc_id}")
            return IngestResponse(
                success=True,
                document_id=doc_id,
                message=f"Document ingested successfully with ID {doc_id}"
            )
        else:
            logger.error("Failed to ingest document - no ID returned")
            return IngestResponse(
                success=False,
                document_id=None,
                message="Failed to ingest document"
            )

    except Exception as e:
        logger.error(f"Error ingesting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest document: {str(e)}"
        )


# =============================================================================
# CONVERSATION MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str = Query(..., description="User identifier"),
    include_archived: bool = Query(False, description="Include archived conversations"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of conversations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get list of conversations for a user.
    Returns conversations sorted by pinned status and last message time.
    """
    try:
        with get_cursor() as cursor:
            # Build query based on whether to include archived
            archive_filter = "" if include_archived else "AND c.is_archived = false"

            cursor.execute(f"""
                SELECT
                    c.id::text,
                    c.title,
                    c.user_id,
                    c.platform,
                    c.started_at::text,
                    c.last_message_at::text,
                    COALESCE(c.is_pinned, false) as is_pinned,
                    COALESCE(c.is_archived, false) as is_archived,
                    COUNT(m.id) as message_count,
                    (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_message
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = %s {archive_filter}
                GROUP BY c.id
                ORDER BY COALESCE(c.is_pinned, false) DESC, c.last_message_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))

            rows = cursor.fetchall()

            # Get total count
            cursor.execute(f"""
                SELECT COUNT(*) as total
                FROM conversations c
                WHERE c.user_id = %s {archive_filter}
            """, (user_id,))
            total = cursor.fetchone()['total']

            conversations = [
                ConversationSummary(
                    id=row['id'],
                    title=row['title'] or "New Conversation",
                    user_id=row['user_id'],
                    platform=row['platform'] or 'web',
                    started_at=row['started_at'],
                    last_message_at=row['last_message_at'],
                    message_count=row['message_count'] or 0,
                    last_message=row['last_message'][:100] + '...' if row['last_message'] and len(row['last_message']) > 100 else row['last_message'],
                    is_pinned=row['is_pinned'],
                    is_archived=row['is_archived']
                )
                for row in rows
            ]

            return ConversationListResponse(
                conversations=conversations,
                total=total
            )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@app.post("/api/conversations", response_model=ConversationSummary)
async def create_conversation(request: ConversationCreate):
    """
    Create a new conversation.
    Returns the created conversation with its ID.
    """
    try:
        conversation_id = str(uuid.uuid4())

        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO conversations (id, user_id, title, platform, started_at, last_message_at)
                VALUES (%s::uuid, %s, %s, %s, NOW(), NOW())
                RETURNING id::text, user_id, title, platform, started_at::text, last_message_at::text
            """, (conversation_id, request.user_id, request.title, request.platform))

            row = cursor.fetchone()

            return ConversationSummary(
                id=row['id'],
                title=row['title'] or "New Conversation",
                user_id=row['user_id'],
                platform=row['platform'],
                started_at=row['started_at'],
                last_message_at=row['last_message_at'],
                message_count=0,
                last_message=None,
                is_pinned=False,
                is_archived=False
            )

    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str):
    """
    Get a single conversation with all its messages.
    """
    try:
        with get_cursor() as cursor:
            # Get conversation details
            cursor.execute("""
                SELECT
                    id::text, user_id, title, platform,
                    started_at::text, last_message_at::text,
                    COALESCE(is_pinned, false) as is_pinned,
                    COALESCE(is_archived, false) as is_archived
                FROM conversations
                WHERE id = %s::uuid
            """, (conversation_id,))

            conv = cursor.fetchone()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Get all messages
            cursor.execute("""
                SELECT id, role, content, sources, timestamp::text
                FROM messages
                WHERE conversation_id = %s::uuid
                ORDER BY timestamp ASC
            """, (conversation_id,))

            messages = cursor.fetchall()

            message_list = []
            for msg in messages:
                sources = None
                if msg['sources']:
                    try:
                        import json
                        sources_data = msg['sources'] if isinstance(msg['sources'], list) else json.loads(msg['sources'])
                        sources = [Source(**s) for s in sources_data] if sources_data else None
                    except:
                        sources = None

                message_list.append(MessageDetail(
                    id=msg['id'],
                    role=msg['role'],
                    content=msg['content'],
                    timestamp=msg['timestamp'],
                    sources=sources
                ))

            return ConversationDetail(
                id=conv['id'],
                title=conv['title'] or "New Conversation",
                user_id=conv['user_id'],
                platform=conv['platform'] or 'web',
                started_at=conv['started_at'],
                last_message_at=conv['last_message_at'],
                is_pinned=conv['is_pinned'],
                is_archived=conv['is_archived'],
                messages=message_list
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@app.patch("/api/conversations/{conversation_id}", response_model=ConversationSummary)
async def update_conversation(conversation_id: str, request: ConversationUpdate):
    """
    Update a conversation (rename, pin, archive).
    """
    try:
        with get_cursor() as cursor:
            # Build dynamic update query
            updates = []
            params = []

            if request.title is not None:
                updates.append("title = %s")
                params.append(request.title)
            if request.is_pinned is not None:
                updates.append("is_pinned = %s")
                params.append(request.is_pinned)
            if request.is_archived is not None:
                updates.append("is_archived = %s")
                params.append(request.is_archived)

            if not updates:
                raise HTTPException(status_code=400, detail="No updates provided")

            params.append(conversation_id)

            cursor.execute(f"""
                UPDATE conversations
                SET {', '.join(updates)}
                WHERE id = %s::uuid
                RETURNING id::text, user_id, title, platform, started_at::text, last_message_at::text,
                          COALESCE(is_pinned, false) as is_pinned, COALESCE(is_archived, false) as is_archived
            """, params)

            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Get message count
            cursor.execute("""
                SELECT COUNT(*) as count,
                       (SELECT content FROM messages WHERE conversation_id = %s::uuid ORDER BY timestamp DESC LIMIT 1) as last_message
                FROM messages WHERE conversation_id = %s::uuid
            """, (conversation_id, conversation_id))
            msg_info = cursor.fetchone()

            return ConversationSummary(
                id=row['id'],
                title=row['title'] or "New Conversation",
                user_id=row['user_id'],
                platform=row['platform'] or 'web',
                started_at=row['started_at'],
                last_message_at=row['last_message_at'],
                message_count=msg_info['count'] or 0,
                last_message=msg_info['last_message'][:100] + '...' if msg_info['last_message'] and len(msg_info['last_message']) > 100 else msg_info['last_message'],
                is_pinned=row['is_pinned'],
                is_archived=row['is_archived']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update conversation")


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, permanent: bool = Query(False, description="Permanently delete instead of archive")):
    """
    Delete a conversation.
    By default, archives the conversation. Use permanent=true to permanently delete.
    """
    try:
        with get_cursor() as cursor:
            if permanent:
                # Permanently delete
                cursor.execute("""
                    DELETE FROM conversations WHERE id = %s::uuid
                    RETURNING id
                """, (conversation_id,))
            else:
                # Soft delete (archive)
                cursor.execute("""
                    UPDATE conversations SET is_archived = true WHERE id = %s::uuid
                    RETURNING id
                """, (conversation_id,))

            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Conversation not found")

            return {"success": True, "message": "Conversation deleted" if permanent else "Conversation archived"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


# =============================================================================
# SEARCH ENDPOINT
# =============================================================================

@app.get("/api/conversations/search", response_model=SearchResponse)
async def search_conversations(
    user_id: str = Query(..., description="User identifier"),
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results")
):
    """
    Search across all conversations for a user.
    Uses PostgreSQL full-text search for fast, relevant results.
    """
    try:
        with get_cursor() as cursor:
            # Check if search_vector column exists, fall back to LIKE if not
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'search_vector'
            """)
            has_search_vector = cursor.fetchone() is not None

            if has_search_vector:
                # Use full-text search
                cursor.execute("""
                    SELECT
                        c.id::text as conversation_id,
                        c.title as conversation_title,
                        m.id as message_id,
                        m.role as message_role,
                        m.content as message_content,
                        m.timestamp::text as message_timestamp,
                        ts_rank(m.search_vector, plainto_tsquery('english', %s)) as relevance
                    FROM messages m
                    INNER JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.user_id = %s
                        AND COALESCE(c.is_archived, false) = false
                        AND m.search_vector @@ plainto_tsquery('english', %s)
                    ORDER BY relevance DESC, m.timestamp DESC
                    LIMIT %s
                """, (q, user_id, q, limit))
            else:
                # Fallback to ILIKE search
                search_pattern = f"%{q}%"
                cursor.execute("""
                    SELECT
                        c.id::text as conversation_id,
                        c.title as conversation_title,
                        m.id as message_id,
                        m.role as message_role,
                        m.content as message_content,
                        m.timestamp::text as message_timestamp,
                        1.0 as relevance
                    FROM messages m
                    INNER JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.user_id = %s
                        AND COALESCE(c.is_archived, false) = false
                        AND m.content ILIKE %s
                    ORDER BY m.timestamp DESC
                    LIMIT %s
                """, (user_id, search_pattern, limit))

            rows = cursor.fetchall()

            results = []
            for row in rows:
                # Create highlight snippet
                content = row['message_content']
                highlight = content

                # Try to find and highlight the search term
                match = re.search(re.escape(q), content, re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    highlight = ('...' if start > 0 else '') + content[start:end] + ('...' if end < len(content) else '')
                elif len(content) > 150:
                    highlight = content[:150] + '...'

                results.append(SearchResult(
                    conversation_id=row['conversation_id'],
                    conversation_title=row['conversation_title'] or "Untitled",
                    message_id=row['message_id'],
                    message_role=row['message_role'],
                    message_content=row['message_content'],
                    message_timestamp=row['message_timestamp'],
                    relevance=float(row['relevance']),
                    highlight=highlight
                ))

            return SearchResponse(
                results=results,
                total=len(results),
                query=q
            )

    except Exception as e:
        logger.error(f"Error searching conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search conversations")


# =============================================================================
# ENHANCED CHAT ENDPOINT WITH USER TRACKING
# =============================================================================

@app.post("/api/chat/v2", response_model=ChatResponse)
async def chat_v2(request: ChatRequestWithUser):
    """
    Enhanced chat endpoint with user identification and conversation management.
    Automatically creates new conversation if conversation_id is not provided.
    """
    try:
        logger.info(f"Received chat request from user {request.user_id}: {request.message[:100]}...")

        conversation_id = request.conversation_id

        with get_cursor() as cursor:
            # Create new conversation if needed
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO conversations (id, user_id, platform, started_at, last_message_at)
                    VALUES (%s::uuid, %s, 'sonance-beta', NOW(), NOW())
                """, (conversation_id, request.user_id))
                logger.info(f"Created new conversation: {conversation_id}")
            else:
                # Verify conversation exists and belongs to user
                cursor.execute("""
                    SELECT id FROM conversations WHERE id = %s::uuid AND user_id = %s
                """, (conversation_id, request.user_id))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Conversation not found")

            # Get conversation history from database if not provided
            conversation_history = request.conversation_history or []
            if not conversation_history:
                cursor.execute("""
                    SELECT role, content FROM messages
                    WHERE conversation_id = %s::uuid
                    ORDER BY timestamp ASC
                    LIMIT 20
                """, (conversation_id,))
                history_rows = cursor.fetchall()
                conversation_history = [
                    {"role": row['role'], "content": row['content']}
                    for row in history_rows
                ]

        # Process chat request with RAG engine
        response_text, sources = rag_engine.chat(
            user_message=request.message,
            conversation_history=conversation_history
        )

        # Calculate average similarity for confidence tracking
        avg_similarity = sum(s.similarity for s in sources) / len(sources) if sources else 0.0

        # Save messages to database
        try:
            with get_cursor() as cursor:
                # Save user message
                cursor.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s::uuid, 'user', %s)
                    RETURNING id
                """, (conversation_id, request.message))
                user_msg_id = cursor.fetchone()['id']

                # Save assistant response with sources
                import json
                sources_json = json.dumps([{"content": s.content, "source": s.source, "similarity": s.similarity} for s in sources]) if sources else None

                cursor.execute("""
                    INSERT INTO messages (conversation_id, role, content, sources, confidence)
                    VALUES (%s::uuid, 'assistant', %s, %s::jsonb, %s)
                """, (conversation_id, response_text, sources_json, avg_similarity))

                # Track low-confidence responses
                if avg_similarity < 0.5 and sources:
                    cursor.execute("""
                        INSERT INTO unanswered_questions (question, confidence, message_id)
                        VALUES (%s, %s, %s)
                    """, (request.message, avg_similarity, user_msg_id))
                    logger.info(f"Logged low-confidence question (similarity: {avg_similarity:.3f})")

        except Exception as db_error:
            logger.error(f"Error saving conversation to database: {db_error}")

        return ChatResponse(
            response=response_text,
            sources=sources,
            conversation_id=conversation_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request. Please try again."
        )


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL.lower()
    )
