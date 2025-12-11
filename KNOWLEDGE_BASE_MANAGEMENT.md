# Living Knowledge Base Management System

## Overview
This document outlines the architecture for managing a continuously-updated knowledge base that serves multiple deployment points (beta portal, official website, etc.).

## Architecture

### Core Components

1. **Knowledge Base API** (Python/FastAPI)
   - Serves chat requests
   - Manages embeddings
   - Tracks feedback and analytics
   - Admin endpoints for knowledge management

2. **Admin Interface**
   - Add/edit/delete knowledge entries
   - Review unanswered questions
   - Track feedback and metrics
   - Import/export functionality

3. **Embeddable Widget**
   - Lightweight JavaScript widget
   - Can be embedded in any website
   - Connects to central API

4. **Database Layer**
   - PostgreSQL for production (aligns with beta portal)
   - Stores knowledge entries with metadata
   - Tracks conversations and feedback
   - Incremental embedding updates

## Deployment Strategy

### Option 1: Shared API (Recommended)
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Beta Portal    │────▶│   Central API   │◀────│ Official Site   │
│  (Node.js)      │     │   (Python)      │     │ (Any platform)  │
└─────────────────┘     │                 │     └─────────────────┘
                        │  - Knowledge DB  │
                        │  - Embeddings    │
                        │  - Analytics     │
                        └─────────────────┘
```

**Pros:**
- Single source of truth
- Consistent answers across all platforms
- Centralized knowledge management
- Easy updates

**Cons:**
- Single point of failure (mitigate with redundancy)
- API latency (mitigate with caching)

### Option 2: Distributed with Sync
```
┌─────────────────┐     ┌─────────────────┐
│  Beta Portal    │     │ Official Site   │
│  + Chatbot API  │     │ + Chatbot API   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────┬───────────────┘
                 ▼
        ┌─────────────────┐
        │  Central KB     │
        │  Sync Service   │
        └─────────────────┘
```

**Pros:**
- Better performance (local API)
- Independent deployments
- Fault tolerance

**Cons:**
- More complex infrastructure
- Sync delays
- Storage duplication

### Recommended: Option 1 (Shared API)

## Knowledge Management Features

### 1. Dynamic Knowledge Entry Addition

**API Endpoint:** `POST /api/admin/knowledge`
```json
{
  "title": "Line Output DSP Behavior",
  "content": "The Line Output is essentially a passthrough with selective DSP...",
  "category": "technical-specs",
  "tags": ["dsp", "line-output", "eq"],
  "source": "Support Team - 2025-01",
  "priority": "high"
}
```

### 2. Incremental Embedding Updates
- Add new entries without full re-ingestion
- Update/delete specific entries by ID
- Automatic embedding generation
- Version control for changes

### 3. Feedback Collection

**User Feedback:**
```json
{
  "conversation_id": "uuid",
  "helpful": true,
  "comment": "Helped me understand the issue",
  "question": "Does the Line Output have DSP?"
}
```

**Admin Dashboard Metrics:**
- Questions asked per day/week/month
- Unanswered questions (low confidence)
- Most helpful answers
- Knowledge gaps identification

### 4. Unanswered Question Tracking
- Track questions with low similarity scores (< 0.4)
- Admin review queue
- One-click "Create KB Entry" from question
- Suggest similar questions to group

## Implementation Plan

### Phase 1: Backend Enhancements (Current Project)
1. Add PostgreSQL database support
2. Create admin API endpoints
3. Implement incremental embedding updates
4. Add feedback collection
5. Track unanswered questions

### Phase 2: Admin Interface
1. Web-based admin dashboard
2. Knowledge entry CRUD operations
3. Review unanswered questions
4. Analytics and metrics

### Phase 3: Widget Creation
1. JavaScript embeddable widget
2. Styling customization options
3. Integration documentation
4. Beta portal integration

### Phase 4: Production Deployment
1. Deploy to cloud service (Railway, DigitalOcean, AWS)
2. Set up PostgreSQL database
3. Configure CORS for multiple origins
4. Add rate limiting and authentication
5. Monitoring and logging

## Database Schema

### Knowledge Entries Table
```sql
CREATE TABLE knowledge_entries (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500),
    content TEXT NOT NULL,
    category VARCHAR(100),
    tags TEXT[],
    source VARCHAR(200),
    priority VARCHAR(20) DEFAULT 'medium',
    embedding VECTOR(1536), -- pgvector extension
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    active BOOLEAN DEFAULT true
);
```

### Conversations Table
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id VARCHAR(100),
    platform VARCHAR(50), -- 'beta-portal', 'official-site', etc.
    started_at TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP DEFAULT NOW()
);
```

### Messages Table
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20), -- 'user' or 'assistant'
    content TEXT,
    sources JSONB, -- Retrieved sources with similarity
    confidence FLOAT, -- Average similarity score
    timestamp TIMESTAMP DEFAULT NOW()
);
```

### Feedback Table
```sql
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    helpful BOOLEAN,
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Unanswered Questions Table
```sql
CREATE TABLE unanswered_questions (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    confidence FLOAT, -- Similarity score
    message_id INTEGER REFERENCES messages(id),
    reviewed BOOLEAN DEFAULT false,
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);
```

## API Endpoints

### Chat API (Existing + Enhanced)
- `POST /api/chat` - Send message, get response
- `POST /api/chat/feedback` - Submit feedback on response

### Admin API (New)
- `POST /api/admin/knowledge` - Add knowledge entry
- `PUT /api/admin/knowledge/:id` - Update knowledge entry
- `DELETE /api/admin/knowledge/:id` - Delete knowledge entry
- `GET /api/admin/knowledge` - List all entries (paginated)
- `POST /api/admin/knowledge/reindex` - Trigger re-indexing

### Analytics API (New)
- `GET /api/admin/analytics/questions` - Unanswered questions
- `GET /api/admin/analytics/metrics` - Usage metrics
- `GET /api/admin/analytics/feedback` - Feedback summary

## Embedding Strategy

### Current (File-based)
- Load all documents from `data/raw/`
- Create embeddings
- Save to FAISS index

### New (Database-backed with Incremental Updates)
```python
# Add new entry
def add_knowledge_entry(entry):
    # 1. Insert into database
    entry_id = db.insert(entry)

    # 2. Generate embedding
    embedding = create_embedding(entry.content)

    # 3. Update FAISS index incrementally
    index.add_with_ids([embedding], [entry_id])

    # 4. Save updated index
    index.save("embeddings_index.faiss")

    return entry_id

# Update entry
def update_knowledge_entry(entry_id, new_content):
    # 1. Update database
    db.update(entry_id, new_content)

    # 2. Generate new embedding
    new_embedding = create_embedding(new_content)

    # 3. Remove old embedding
    index.remove_ids([entry_id])

    # 4. Add new embedding
    index.add_with_ids([new_embedding], [entry_id])

    # 5. Save updated index
    index.save("embeddings_index.faiss")

# Delete entry
def delete_knowledge_entry(entry_id):
    # 1. Soft delete in database
    db.update(entry_id, active=False)

    # 2. Remove from index
    index.remove_ids([entry_id])

    # 3. Save updated index
    index.save("embeddings_index.faiss")
```

## Integration Examples

### Beta Portal Integration

**Option A: Dedicated Page**
```javascript
// Add route in beta portal
app.get('/support-chat', (req, res) => {
  res.render('support-chat', {
    apiUrl: process.env.CHATBOT_API_URL || 'http://localhost:5000'
  });
});
```

**Option B: Floating Widget** (Recommended)
```html
<!-- Add to layout.ejs footer -->
<script>
  window.chatbotConfig = {
    apiUrl: 'https://your-chatbot-api.com',
    product: 'UA2-125',
    theme: 'sonance'
  };
</script>
<script src="https://your-chatbot-api.com/widget.js"></script>
```

### Official Website Integration
```html
<!-- Add anywhere on the page -->
<script>
  window.chatbotConfig = {
    apiUrl: 'https://your-chatbot-api.com',
    product: 'UA2-125',
    position: 'bottom-right',
    primaryColor: '#000000'
  };
</script>
<script src="https://your-chatbot-api.com/widget.js"></script>
```

## Security Considerations

### Admin API Authentication
- API key authentication for admin endpoints
- Role-based access control (RBAC)
- Audit logging for all changes

### Rate Limiting
- Per-IP rate limiting for chat API
- Higher limits for authenticated users
- Admin API requires authentication

### CORS Configuration
```python
# Allow multiple origins
ALLOWED_ORIGINS = [
    "https://beta.sonance.com",
    "https://www.sonance.com",
    "http://localhost:3000"  # Development
]
```

## Deployment Checklist

### Cloud Service Setup
- [ ] Choose provider (Railway, DigitalOcean, AWS, Heroku)
- [ ] Set up PostgreSQL database
- [ ] Install pgvector extension
- [ ] Configure environment variables
- [ ] Set up SSL/TLS certificates

### Application Deployment
- [ ] Deploy Python backend
- [ ] Migrate existing knowledge base to database
- [ ] Generate initial embeddings
- [ ] Configure CORS for all frontend domains
- [ ] Set up admin API authentication

### Monitoring & Maintenance
- [ ] Set up error logging (Sentry, LogRocket)
- [ ] Configure uptime monitoring
- [ ] Set up automated backups
- [ ] Create admin dashboard
- [ ] Document API for team

## Next Steps

1. **Immediate:** Add the Line Output DSP information to knowledge base
2. **Short-term:** Implement database layer and admin API
3. **Medium-term:** Create embeddable widget
4. **Long-term:** Deploy to production with full analytics

## Cost Estimates

### Cloud Hosting (Monthly)
- **Railway/DigitalOcean:** $15-25/month (basic tier)
- **AWS/GCP:** $20-50/month (with auto-scaling)

### Database
- **PostgreSQL:** Included with hosting or $15/month managed

### OpenAI API
- **Embeddings:** ~$0.10 per 1,000 entries
- **Chat:** ~$0.002 per response (GPT-4)
- **Estimated:** $50-100/month for active usage

**Total Estimated Cost:** $85-175/month for full production deployment
