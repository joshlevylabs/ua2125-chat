"""
FastAPI application for UA2-125 AI Chatbot Assistant
"""
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config import HOST, PORT, CORS_ORIGINS, LOG_LEVEL
from models import ChatRequest, ChatResponse, HealthResponse, IngestRequest, IngestResponse
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
