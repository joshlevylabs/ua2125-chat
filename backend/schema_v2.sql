-- UA2-125 AI Chatbot Database Schema V2
-- Adds conversation history management and search capabilities

-- =============================================================================
-- SCHEMA UPDATES FOR CHAT HISTORY FEATURE
-- =============================================================================

-- Add title column to conversations for display in sidebar
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR(255);

-- Add summary column for auto-generated conversation summaries
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary TEXT;

-- Add is_archived column for soft-delete functionality
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT false;

-- Add is_pinned column for pinning important conversations
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT false;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_conversations_is_archived ON conversations(is_archived);
CREATE INDEX IF NOT EXISTS idx_conversations_is_pinned ON conversations(is_pinned);
CREATE INDEX IF NOT EXISTS idx_conversations_title ON conversations(title);
CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at ON conversations(last_message_at DESC);

-- =============================================================================
-- FULL TEXT SEARCH SUPPORT
-- =============================================================================

-- Add full-text search vector column to messages
ALTER TABLE messages ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_messages_search_vector ON messages USING GIN(search_vector);

-- Function to update search vector on insert/update
CREATE OR REPLACE FUNCTION update_message_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update search vector
DROP TRIGGER IF EXISTS trg_messages_search_vector ON messages;
CREATE TRIGGER trg_messages_search_vector
BEFORE INSERT OR UPDATE ON messages
FOR EACH ROW
EXECUTE FUNCTION update_message_search_vector();

-- Update existing messages with search vectors
UPDATE messages SET search_vector = to_tsvector('english', COALESCE(content, ''))
WHERE search_vector IS NULL;

-- =============================================================================
-- AUTO-GENERATE CONVERSATION TITLE
-- =============================================================================

-- Function to auto-generate conversation title from first user message
CREATE OR REPLACE FUNCTION auto_generate_conversation_title()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update title if it's NULL and this is a user message
    IF NEW.role = 'user' THEN
        UPDATE conversations
        SET title = CASE
            WHEN LENGTH(NEW.content) > 50 THEN LEFT(NEW.content, 47) || '...'
            ELSE NEW.content
        END
        WHERE id = NEW.conversation_id AND title IS NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate title on first message
DROP TRIGGER IF EXISTS trg_auto_generate_title ON messages;
CREATE TRIGGER trg_auto_generate_title
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION auto_generate_conversation_title();

-- =============================================================================
-- SEARCH FUNCTION
-- =============================================================================

-- Function to search messages across all conversations for a user
CREATE OR REPLACE FUNCTION search_conversations(
    p_user_id VARCHAR(100),
    p_search_query TEXT,
    p_limit INT DEFAULT 50
)
RETURNS TABLE (
    conversation_id UUID,
    conversation_title VARCHAR(255),
    message_id INT,
    message_role VARCHAR(20),
    message_content TEXT,
    message_timestamp TIMESTAMP WITH TIME ZONE,
    relevance REAL,
    highlight TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id as conversation_id,
        c.title as conversation_title,
        m.id as message_id,
        m.role as message_role,
        m.content as message_content,
        m.timestamp as message_timestamp,
        ts_rank(m.search_vector, plainto_tsquery('english', p_search_query)) as relevance,
        ts_headline('english', m.content, plainto_tsquery('english', p_search_query),
            'StartSel=**, StopSel=**, MaxWords=35, MinWords=15') as highlight
    FROM messages m
    INNER JOIN conversations c ON m.conversation_id = c.id
    WHERE c.user_id = p_user_id
        AND c.is_archived = false
        AND m.search_vector @@ plainto_tsquery('english', p_search_query)
    ORDER BY relevance DESC, m.timestamp DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- VIEWS FOR CONVERSATION MANAGEMENT
-- =============================================================================

-- View for conversation list with message counts and last message
CREATE OR REPLACE VIEW conversation_list AS
SELECT
    c.id,
    c.user_id,
    c.title,
    c.platform,
    c.started_at,
    c.last_message_at,
    c.is_archived,
    c.is_pinned,
    COUNT(m.id) as message_count,
    (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_message
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id
ORDER BY c.is_pinned DESC, c.last_message_at DESC;

-- =============================================================================
-- MIGRATION: Update existing conversations with titles
-- =============================================================================

-- Set titles for existing conversations based on first user message
UPDATE conversations c
SET title = (
    SELECT CASE
        WHEN LENGTH(m.content) > 50 THEN LEFT(m.content, 47) || '...'
        ELSE m.content
    END
    FROM messages m
    WHERE m.conversation_id = c.id AND m.role = 'user'
    ORDER BY m.timestamp ASC
    LIMIT 1
)
WHERE c.title IS NULL;

-- Set default title for conversations without any user messages
UPDATE conversations SET title = 'New Conversation' WHERE title IS NULL;

-- =============================================================================
-- VERSION TRACKING
-- =============================================================================

-- Create schema versions table if not exists
CREATE TABLE IF NOT EXISTS schema_versions (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- Record this migration
INSERT INTO schema_versions (version, description)
VALUES ('v2.1.0', 'Added multi-conversation support with history, search, and highlight')
ON CONFLICT (version) DO NOTHING;
