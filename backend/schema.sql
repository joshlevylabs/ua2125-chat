-- UA2-125 AI Chatbot Database Schema
-- Requires PostgreSQL with pgvector extension

-- Enable pgvector extension (may require superuser)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Knowledge Entries Table
-- Stores all knowledge base entries with embeddings
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500),
    content TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    tags TEXT[],
    source VARCHAR(200),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    active BOOLEAN DEFAULT true
);

-- Create indexes for fast retrieval
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_active ON knowledge_entries(active);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_category ON knowledge_entries(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_created_at ON knowledge_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_tags ON knowledge_entries USING GIN(tags);

-- Create vector similarity search index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_embedding ON knowledge_entries
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Conversations Table
-- Tracks all chat conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100),
    platform VARCHAR(50) DEFAULT 'web', -- 'beta-portal', 'official-site', 'web', etc.
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_platform ON conversations(platform);
CREATE INDEX IF NOT EXISTS idx_conversations_started_at ON conversations(started_at DESC);

-- Messages Table
-- Stores all messages in conversations
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB, -- Retrieved sources with similarity scores
    confidence FLOAT, -- Average similarity score of retrieved sources
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_confidence ON messages(confidence);

-- Feedback Table
-- User feedback on assistant responses
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    helpful BOOLEAN,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON messages(id);
CREATE INDEX IF NOT EXISTS idx_feedback_helpful ON feedback(helpful);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);

-- Unanswered Questions Table
-- Tracks questions that had low confidence or no good answer
CREATE TABLE IF NOT EXISTS unanswered_questions (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    confidence FLOAT, -- Best similarity score found
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    reviewed BOOLEAN DEFAULT false,
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolved_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_unanswered_questions_reviewed ON unanswered_questions(reviewed);
CREATE INDEX IF NOT EXISTS idx_unanswered_questions_resolved ON unanswered_questions(resolved);
CREATE INDEX IF NOT EXISTS idx_unanswered_questions_confidence ON unanswered_questions(confidence);
CREATE INDEX IF NOT EXISTS idx_unanswered_questions_created_at ON unanswered_questions(created_at DESC);

-- Analytics/Metrics Views
-- View for popular questions (by similarity)
CREATE OR REPLACE VIEW popular_questions AS
SELECT
    m.content as question,
    COUNT(*) as count,
    AVG(m.confidence) as avg_confidence,
    MAX(m.timestamp) as last_asked
FROM messages m
WHERE m.role = 'user' AND m.confidence IS NOT NULL
GROUP BY m.content
ORDER BY count DESC;

-- View for low confidence responses
CREATE OR REPLACE VIEW low_confidence_responses AS
SELECT
    m.id,
    m.conversation_id,
    m.content as question,
    m.confidence,
    m.timestamp,
    u.content as user_question,
    a.content as assistant_response
FROM messages m
LEFT JOIN messages u ON u.id = m.id - 1 AND u.role = 'user'
LEFT JOIN messages a ON a.id = m.id + 1 AND a.role = 'assistant'
WHERE m.confidence < 0.5
ORDER BY m.timestamp DESC;

-- View for daily usage metrics
CREATE OR REPLACE VIEW daily_metrics AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as total_messages,
    COUNT(DISTINCT conversation_id) as unique_conversations,
    AVG(confidence) as avg_confidence,
    COUNT(CASE WHEN confidence < 0.5 THEN 1 END) as low_confidence_count
FROM messages
WHERE role = 'user' AND confidence IS NOT NULL
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- Functions
-- Function to update knowledge entry timestamp
CREATE OR REPLACE FUNCTION update_knowledge_entry_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
CREATE TRIGGER trg_knowledge_entries_updated_at
BEFORE UPDATE ON knowledge_entries
FOR EACH ROW
EXECUTE FUNCTION update_knowledge_entry_timestamp();

-- Function to update conversation last_message_at
CREATE OR REPLACE FUNCTION update_conversation_last_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET last_message_at = NEW.timestamp
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update conversation timestamp when message is added
CREATE TRIGGER trg_messages_update_conversation
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION update_conversation_last_message();

-- Function for vector similarity search
CREATE OR REPLACE FUNCTION search_knowledge(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.2,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id integer,
    title varchar(500),
    content text,
    category varchar(100),
    source varchar(200),
    similarity float,
    metadata jsonb
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ke.id,
        ke.title,
        ke.content,
        ke.category,
        ke.source,
        1 - (ke.embedding <=> query_embedding) as similarity,
        ke.metadata
    FROM knowledge_entries ke
    WHERE ke.active = true
        AND (1 - (ke.embedding <=> query_embedding)) > match_threshold
    ORDER BY ke.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Insert default admin user (for API authentication)
-- Password should be changed in production
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);

-- Initial Setup Complete
-- Don't forget to:
-- 1. Set up proper authentication
-- 2. Change default admin passwords
-- 3. Configure backup strategy
-- 4. Set up monitoring
