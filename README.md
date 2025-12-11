# UA2-125 AI Chatbot Assistant

A production-ready RAG (Retrieval-Augmented Generation) chatbot for providing intelligent support for the Sonance UA2-125 amplifier. Built with FastAPI, OpenAI embeddings, and a clean HTML/JS frontend.

## Overview

The UA2-125 AI Assistant helps installers, integrators, dealers, technicians, and end-users with:
- Installation and wiring guidance
- HDMI ARC/eARC setup and troubleshooting
- Technical specifications lookup
- Troubleshooting and diagnostics
- Accessories and mounting information

**Key Features:**
- RAG-based architecture for accurate, source-grounded answers
- Real-time document retrieval with similarity scoring
- Clean, professional chat interface
- Extensible knowledge base system
- Production-ready FastAPI backend

## Architecture

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frontend UI    │  (HTML/CSS/JS)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI Server │  (Python)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RAG Engine     │
│  - Embeddings   │  (OpenAI text-embedding-3-large)
│  - Vector Store │  (NumPy + Cosine Similarity)
│  - LLM          │  (GPT-4o-mini)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Knowledge Base │  (JSON/TXT documents)
└─────────────────┘
```

## Prerequisites

- Python 3.9 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- pip (Python package manager)
- Git (optional, for version control)

## Quick Start

### 1. Clone or Download the Project

```bash
cd ua2125-chat
```

### 2. Set Up Python Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 5. Ingest Knowledge Base

The project includes a seed knowledge base with UA2-125 specifications. Ingest it into the system:

```bash
python ingest_docs.py
```

This will:
- Process all documents in `data/raw/`
- Create embeddings using OpenAI API
- Build and save the vector index
- Display statistics about the indexed content

**Expected output:**
```
============================================================
UA2-125 AI Chatbot - Document Ingestion
============================================================
Processing files from: data/raw
Processing JSON file: ua2125_knowledge_base.json
Created 21 chunks from JSON file
Total chunks created: 21

✅ Saved 21 processed chunks to data/processed/processed_chunks.json

📊 Creating embeddings (this may take a few minutes)...
Added 21 chunks to index

✅ Embeddings created and index saved successfully!

============================================================
Index Statistics:
  Total chunks: 21
  Embedding dimension: 3072
  Index size: 0.25 MB
============================================================

🚀 Ready to start the chatbot server!
   Run: python app.py
```

### 6. Start the Server

```bash
python app.py
```

The server will start on `http://localhost:8000`

### 7. Access the Chatbot

Open your web browser and navigate to:

```
http://localhost:8000
```

You should see the UA2-125 AI Assistant chat interface.

## Usage Examples

Try these sample queries:

1. **Specifications:**
   - "What's the power output at 4 ohms?"
   - "What is the frequency response?"

2. **Installation:**
   - "How do I connect a TV using HDMI ARC?"
   - "What's the proper speaker wiring for stereo mode?"

3. **Troubleshooting:**
   - "Why is my amplifier going into protection mode?"
   - "How do I fix no sound from HDMI ARC?"

4. **Setup:**
   - "What are the input priority settings?"
   - "How do I configure the input trim?"

## Adding New Documents

### Option 1: JSON Format (Recommended)

Create a new JSON file in `backend/data/raw/` following this structure:

```json
[
  {
    "title": "Document Title",
    "category": "category_name",
    "source": "Source Name",
    "content": "Your content here..."
  }
]
```

### Option 2: Plain Text

Simply add `.txt` files to `backend/data/raw/`. The system will automatically chunk and index them.

### Option 3: PDF Support (Future)

PDF ingestion can be added by extending `ingest_docs.py` with PyPDF2 (already included in requirements).

### Re-indexing

After adding new documents, re-run the ingestion script:

```bash
cd backend
python ingest_docs.py
```

The system will process all documents and rebuild the index.

## Project Structure

```
ua2125-chat/
├── backend/
│   ├── app.py                 # FastAPI server
│   ├── rag_engine.py          # RAG logic (retrieve + generate)
│   ├── embeddings_index.py    # Vector store implementation
│   ├── models.py              # Pydantic models
│   ├── config.py              # Configuration settings
│   ├── ingest_docs.py         # Document ingestion script
│   ├── requirements.txt       # Python dependencies
│   └── data/
│       ├── raw/               # Raw documents (JSON, TXT, PDF)
│       ├── processed/         # Processed chunks
│       └── index/             # Vector embeddings index
├── frontend/
│   ├── index.html             # Chat UI
│   └── static/
│       └── styles.css         # Styling
├── .env.example               # Environment variables template
├── README.md                  # This file
├── DEPLOYMENT.md              # Deployment guide
└── TESTING.md                 # QA testing plan
```

## API Endpoints

### `GET /`
Serves the chat frontend interface

### `GET /health`
Health check endpoint
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "embeddings_loaded": true,
  "documents_count": 21
}
```

### `POST /api/chat`
Main chat endpoint

**Request:**
```json
{
  "message": "How do I connect HDMI ARC?",
  "conversation_history": []
}
```

**Response:**
```json
{
  "response": "To connect a TV using HDMI ARC...",
  "sources": [
    {
      "content": "How to Connect a TV Using HDMI ARC/eARC...",
      "source": "Installation Guide",
      "similarity": 0.912
    }
  ],
  "conversation_id": "uuid-here"
}
```

### `GET /api/stats`
Get knowledge base statistics

## Configuration

Edit `backend/config.py` to customize:

- **Embedding Model:** `EMBEDDING_MODEL = "text-embedding-3-large"`
- **LLM Model:** `LLM_MODEL = "gpt-4o-mini"`
- **Chunk Size:** `CHUNK_SIZE = 800`
- **Retrieval Count:** `TOP_K_RESULTS = 5`
- **Similarity Threshold:** `SIMILARITY_THRESHOLD = 0.7`
- **System Prompt:** Customize the chatbot's personality and behavior

## Troubleshooting

### "Index files not found" Error

**Solution:** Run the document ingestion script:
```bash
cd backend
python ingest_docs.py
```

### "OpenAI API Error"

**Solution:**
1. Verify your API key is correct in `.env`
2. Check your OpenAI account has credits
3. Ensure internet connectivity

### Port Already in Use

**Solution:** Change the port in `backend/config.py` or set `PORT` environment variable:
```bash
export PORT=8080  # macOS/Linux
set PORT=8080     # Windows CMD
```

### Empty Responses

**Solution:**
1. Check if documents were ingested successfully
2. Verify vector index files exist in `data/index/`
3. Try lowering `SIMILARITY_THRESHOLD` in `config.py`

## Development

### Running in Development Mode

The server automatically reloads on code changes:

```bash
cd backend
python app.py
```

### Adding Custom Tools

Extend `rag_engine.py` to add custom retrieval logic or processing steps.

### Modifying the UI

Edit `frontend/index.html` and `frontend/static/styles.css` to customize the appearance.

## Performance Considerations

- **Embedding Dimension:** text-embedding-3-large (3072 dimensions) provides high accuracy
- **Vector Search:** NumPy cosine similarity is fast for <10,000 documents
- **Scaling:** For larger knowledge bases (>10k docs), consider migrating to:
  - Pinecone
  - Weaviate
  - Qdrant
  - ChromaDB

## Security Notes

**For Production Deployment:**

1. **Environment Variables:** Never commit `.env` file with real API keys
2. **CORS:** Restrict `CORS_ORIGINS` in `config.py` to your domain
3. **API Rate Limiting:** Implement rate limiting for production
4. **Authentication:** Add user authentication if needed
5. **HTTPS:** Always use HTTPS in production

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guidelines.

## Support & Resources

- **Product Page:** https://sonance.com/products/93550
- **Technical Documentation:** Included in knowledge base
- **Issue Tracker:** [Report issues here]

## Future Enhancements

Potential additions:
- [ ] PDF document ingestion
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Image/diagram support in responses
- [ ] Integration with Salesforce/Zendesk
- [ ] Analytics and usage tracking
- [ ] Admin dashboard for knowledge base management
- [ ] Salsify API integration for automatic product data sync

## License

Proprietary - Sonance by Dana Innovations

---

**Built with Claude Code** | Powered by Sonance AI Support Platform
