# UA2-125 AI Chatbot - Website Integration Guide

## For Sonance Beta Website Development Team

This document provides comprehensive instructions for integrating the UA2-125 AI Chatbot into the Sonance Beta website.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Integration Options](#integration-options)
4. [API Reference](#api-reference)
5. [User Authentication Integration](#user-authentication-integration)
6. [Embedding the Chatbot](#embedding-the-chatbot)
7. [Styling & Customization](#styling--customization)
8. [Security Considerations](#security-considerations)
9. [Environment Configuration](#environment-configuration)
10. [Deployment Checklist](#deployment-checklist)

---

## Overview

The UA2-125 AI Chatbot is a RAG-based (Retrieval-Augmented Generation) support assistant specifically designed for the Sonance UA2-125 amplifier. It features:

- **Multi-conversation support** - Users can have multiple chat sessions
- **Chat history** - Full conversation history stored per user
- **Search functionality** - Search across all conversations
- **Real-time responses** - Powered by OpenAI GPT-4o-mini

### Key Features for Integration

| Feature | Description |
|---------|-------------|
| User identification | Pass `user_id` to track conversations per user |
| Conversation management | Create, list, delete, rename conversations |
| Search | Full-text search across all user conversations |
| Responsive UI | Works on desktop and mobile |
| Embeddable | Can be embedded as iframe or integrated directly |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SONANCE BETA WEBSITE                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   AI Support Section                 │   │
│  │  ┌───────────────┐  ┌───────────────┐              │   │
│  │  │  UA2-125 AI   │  │  Other AI     │   ...        │   │
│  │  │  Assistant    │  │  Assistants   │              │   │
│  │  └───────┬───────┘  └───────────────┘              │   │
│  └──────────┼──────────────────────────────────────────┘   │
└─────────────┼───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                 UA2-125 CHATBOT SERVICE                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    AWS ECS/Fargate                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  FastAPI    │  │  PostgreSQL │  │  OpenAI     │  │   │
│  │  │  Backend    │◄─┤  + pgvector │  │  API        │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Options

### Option 1: Iframe Embedding (Simplest)

Embed the chatbot as an iframe in your page:

```html
<!-- Basic iframe embed -->
<iframe
    src="https://ua2125-api.sonance.com?user_id=USER_ID_HERE"
    width="100%"
    height="700px"
    style="border: none; border-radius: 12px;"
    title="UA2-125 AI Assistant"
></iframe>
```

**With dynamic user ID from your auth system:**

```html
<iframe
    id="ua2125-chatbot"
    width="100%"
    height="700px"
    style="border: none; border-radius: 12px;"
    title="UA2-125 AI Assistant"
></iframe>

<script>
    // Get user ID from your authentication system
    const userId = getCurrentUser().id; // Your auth function

    document.getElementById('ua2125-chatbot').src =
        `https://ua2125-api.sonance.com?user_id=${encodeURIComponent(userId)}`;
</script>
```

### Option 2: Direct API Integration (Recommended)

Build your own UI and call the API directly:

```javascript
// API Configuration
const CHATBOT_API = 'https://ua2125-api.sonance.com';

// Get user's conversations
async function getConversations(userId) {
    const response = await fetch(
        `${CHATBOT_API}/api/conversations?user_id=${userId}`
    );
    return response.json();
}

// Send a message
async function sendMessage(userId, message, conversationId = null) {
    const response = await fetch(`${CHATBOT_API}/api/chat/v2`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: userId,
            message: message,
            conversation_id: conversationId
        })
    });
    return response.json();
}

// Search conversations
async function searchConversations(userId, query) {
    const response = await fetch(
        `${CHATBOT_API}/api/conversations/search?user_id=${userId}&q=${encodeURIComponent(query)}`
    );
    return response.json();
}
```

### Option 3: React Component Integration

If using React on the Sonance Beta portal:

```jsx
// UA2125Chatbot.jsx
import React, { useState, useEffect } from 'react';

const CHATBOT_API = 'https://ua2125-api.sonance.com';

function UA2125Chatbot({ userId }) {
    const [conversations, setConversations] = useState([]);
    const [currentConversation, setCurrentConversation] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // Load conversations on mount
    useEffect(() => {
        loadConversations();
    }, [userId]);

    async function loadConversations() {
        const res = await fetch(`${CHATBOT_API}/api/conversations?user_id=${userId}`);
        const data = await res.json();
        setConversations(data.conversations);
    }

    async function loadConversation(convId) {
        const res = await fetch(`${CHATBOT_API}/api/conversations/${convId}`);
        const data = await res.json();
        setCurrentConversation(convId);
        setMessages(data.messages);
    }

    async function sendMessage() {
        if (!input.trim() || isLoading) return;

        setIsLoading(true);
        const userMessage = input;
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

        try {
            const res = await fetch(`${CHATBOT_API}/api/chat/v2`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    message: userMessage,
                    conversation_id: currentConversation
                })
            });
            const data = await res.json();

            setCurrentConversation(data.conversation_id);
            setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
            loadConversations(); // Refresh sidebar
        } catch (error) {
            console.error('Error:', error);
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <div className="ua2125-chatbot">
            {/* Your custom UI here */}
        </div>
    );
}

export default UA2125Chatbot;
```

---

## API Reference

### Base URL

```
Production: https://ua2125-api.sonance.com
Staging: https://ua2125-api-staging.sonance.com
```

### Endpoints

#### 1. List Conversations
```http
GET /api/conversations?user_id={user_id}&include_archived=false&limit=50&offset=0
```

**Response:**
```json
{
    "conversations": [
        {
            "id": "uuid-here",
            "title": "HDMI ARC Setup Question",
            "user_id": "user123",
            "platform": "sonance-beta",
            "started_at": "2025-01-15T10:30:00Z",
            "last_message_at": "2025-01-15T10:35:00Z",
            "message_count": 4,
            "last_message": "Thank you, that solved my issue!",
            "is_pinned": false,
            "is_archived": false
        }
    ],
    "total": 1
}
```

#### 2. Create Conversation
```http
POST /api/conversations
Content-Type: application/json

{
    "user_id": "user123",
    "title": "Optional Title",
    "platform": "sonance-beta"
}
```

#### 3. Get Conversation Details
```http
GET /api/conversations/{conversation_id}
```

**Response:**
```json
{
    "id": "uuid-here",
    "title": "HDMI ARC Setup Question",
    "user_id": "user123",
    "messages": [
        {
            "id": 1,
            "role": "user",
            "content": "How do I connect HDMI ARC?",
            "timestamp": "2025-01-15T10:30:00Z"
        },
        {
            "id": 2,
            "role": "assistant",
            "content": "To connect HDMI ARC...",
            "timestamp": "2025-01-15T10:30:05Z",
            "sources": [...]
        }
    ]
}
```

#### 4. Send Message (Create or Continue Conversation)
```http
POST /api/chat/v2
Content-Type: application/json

{
    "user_id": "user123",
    "message": "How do I connect a TV using HDMI ARC?",
    "conversation_id": null  // null = create new, UUID = continue existing
}
```

**Response:**
```json
{
    "response": "To connect a TV using HDMI ARC...",
    "sources": [
        {
            "content": "HDMI ARC connection guide...",
            "source": "Installation Guide",
            "similarity": 0.92
        }
    ],
    "conversation_id": "new-uuid-if-created"
}
```

#### 5. Update Conversation (Rename, Pin, Archive)
```http
PATCH /api/conversations/{conversation_id}
Content-Type: application/json

{
    "title": "New Title",
    "is_pinned": true,
    "is_archived": false
}
```

#### 6. Delete Conversation
```http
DELETE /api/conversations/{conversation_id}?permanent=false
```
- `permanent=false`: Archives the conversation (soft delete)
- `permanent=true`: Permanently deletes

#### 7. Search Conversations
```http
GET /api/conversations/search?user_id={user_id}&q={search_query}&limit=50
```

**Response:**
```json
{
    "results": [
        {
            "conversation_id": "uuid-here",
            "conversation_title": "HDMI Setup",
            "message_id": 42,
            "message_role": "assistant",
            "message_content": "Connect the HDMI cable to the ARC port...",
            "message_timestamp": "2025-01-15T10:30:05Z",
            "relevance": 0.95,
            "highlight": "...Connect the **HDMI** cable to the ARC port..."
        }
    ],
    "total": 1,
    "query": "HDMI"
}
```

#### 8. Health Check
```http
GET /health
```

**Response:**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "embeddings_loaded": true,
    "documents_count": 45
}
```

---

## User Authentication Integration

### Passing User ID

The chatbot identifies users by a `user_id` string. This should be a **consistent, unique identifier** from your authentication system.

**Recommended approaches:**

1. **Use your existing user ID:**
```javascript
const userId = currentUser.id; // "user_abc123"
```

2. **Use email hash (if no user system):**
```javascript
const userId = await hashEmail(userEmail); // "sha256_hash"
```

3. **Use session ID (anonymous users):**
```javascript
const userId = sessionStorage.getItem('chatbot_session') || generateSessionId();
```

### SSO Integration

If using SSO (Single Sign-On) with the Sonance Beta portal:

```javascript
// After SSO authentication
const userProfile = await getSSOProfile();

// Pass to chatbot
const chatbotUrl = `https://ua2125-api.sonance.com?user_id=${userProfile.userId}&user_name=${encodeURIComponent(userProfile.name)}`;
```

---

## Embedding the Chatbot

### Full Page Integration

For a dedicated `/ai-support/ua2125` page:

```html
<!DOCTYPE html>
<html>
<head>
    <title>UA2-125 AI Assistant | Sonance Beta</title>
    <style>
        body { margin: 0; padding: 0; }
        .chatbot-container {
            width: 100%;
            height: 100vh;
        }
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
    </style>
</head>
<body>
    <div class="chatbot-container">
        <iframe
            id="ua2125-chatbot"
            src="https://ua2125-api.sonance.com"
            title="UA2-125 AI Assistant"
        ></iframe>
    </div>

    <script>
        // Inject user ID from your auth system
        window.addEventListener('load', () => {
            const userId = getUserIdFromAuth(); // Your function
            const iframe = document.getElementById('ua2125-chatbot');
            iframe.src = `https://ua2125-api.sonance.com?user_id=${userId}`;
        });
    </script>
</body>
</html>
```

### Widget/Sidebar Integration

For embedding in a sidebar or widget:

```html
<div class="ai-support-widget" style="width: 400px; height: 600px;">
    <iframe
        src="https://ua2125-api.sonance.com?user_id=USER_ID"
        style="width: 100%; height: 100%; border: none; border-radius: 12px;"
    ></iframe>
</div>
```

---

## Styling & Customization

### CSS Variables

The chatbot uses CSS variables that can be overridden. If embedding via iframe, you can pass theme parameters:

```html
<iframe src="https://ua2125-api.sonance.com?user_id=USER_ID&theme=dark"></iframe>
```

### Custom Theme (API Integration)

If building your own UI with the API:

```css
:root {
    /* Sonance brand colors */
    --sonance-primary: #1a1a2e;
    --sonance-accent: #e94560;
    --sonance-text: #ffffff;
}

.chatbot-message-user {
    background: var(--sonance-accent);
}

.chatbot-message-assistant {
    background: var(--sonance-primary);
}
```

---

## Security Considerations

### CORS Configuration

The chatbot API is configured to accept requests from:
- `https://beta.sonance.com`
- `https://www.sonance.com`
- `https://sonance.com`

**To add new domains**, update the `CORS_ORIGINS` environment variable:
```
CORS_ORIGINS=https://beta.sonance.com,https://new-domain.sonance.com
```

### Rate Limiting

The API implements rate limiting:
- **10 requests per minute** per user for chat endpoints
- **100 requests per minute** per user for read endpoints

### Data Privacy

- Conversations are stored per `user_id`
- Users can only access their own conversations
- Implement proper user authentication on your side to prevent `user_id` spoofing

---

## Environment Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `https://beta.sonance.com,https://sonance.com` |
| `LOG_LEVEL` | Logging level | `INFO` |

### AWS Deployment

The chatbot is configured for deployment on AWS with:
- **ECS Fargate** for container hosting
- **RDS PostgreSQL** with pgvector extension
- **Application Load Balancer** for HTTPS
- **Secrets Manager** for API keys

See `aws/cloudformation-template.yml` for infrastructure details.

---

## Deployment Checklist

### Pre-Deployment

- [ ] Set up PostgreSQL database with pgvector extension
- [ ] Run database migrations (`schema.sql` and `schema_v2.sql`)
- [ ] Configure OpenAI API key
- [ ] Ingest knowledge base documents
- [ ] Configure CORS origins for your domain
- [ ] Set up SSL/TLS certificate

### Integration Testing

- [ ] Test user ID passing from your auth system
- [ ] Verify conversation creation and retrieval
- [ ] Test search functionality
- [ ] Verify mobile responsiveness
- [ ] Test error handling (API down, rate limits)

### Production Go-Live

- [ ] Configure monitoring (CloudWatch, Datadog, etc.)
- [ ] Set up alerting for API errors
- [ ] Document support escalation path
- [ ] Create user documentation/help text
- [ ] Plan for knowledge base updates

---

## Support & Contacts

**For integration questions:**
- Review this documentation
- Check API health: `GET /health`
- Review server logs in CloudWatch

**API Status:**
- Health endpoint: `https://ua2125-api.sonance.com/health`

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01 | Initial release with conversation history and search |

---

*This integration guide is for the Sonance Beta website development team. For end-user documentation, see the main README.md.*
