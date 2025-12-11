"""
PostgreSQL-backed Embeddings Index

Replaces FAISS with PostgreSQL + pgvector for scalable, database-backed embeddings storage.
Supports incremental updates and vector similarity search.
"""
import logging
import json
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
import numpy as np

from config import OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIMENSION, SIMILARITY_THRESHOLD
from database import get_cursor, init_connection_pool

logger = logging.getLogger(__name__)


class DatabaseEmbeddingsIndex:
    """PostgreSQL-backed embeddings index with pgvector"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.embedding_model = EMBEDDING_MODEL
        self.dimension = EMBEDDING_DIMENSION

        # Initialize connection pool
        init_connection_pool()

        logger.info(f"Initialized DatabaseEmbeddingsIndex with {EMBEDDING_MODEL}")

    def create_embedding(self, text: str) -> List[float]:
        """
        Create embedding for a single text string

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            return None

    def create_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Create embeddings for multiple texts in batches

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Creating embeddings for batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error creating batch embeddings: {e}")
                # Return None for failed embeddings
                all_embeddings.extend([None] * len(batch))

        return all_embeddings

    def add_document(
        self,
        content: str,
        metadata: Dict,
        source: str,
        title: Optional[str] = None,
        category: str = "general",
        tags: List[str] = None,
        priority: str = "medium"
    ) -> Optional[int]:
        """
        Add a single document to the database

        Args:
            content: Document text
            metadata: Additional metadata as dict
            source: Source file/document name
            title: Optional title
            category: Category (e.g., 'technical-specs', 'troubleshooting')
            tags: List of tags
            priority: Priority level ('low', 'medium', 'high', 'critical')

        Returns:
            Document ID if successful, None otherwise
        """
        # Create embedding
        embedding = self.create_embedding(content)
        if embedding is None:
            logger.error("Failed to create embedding")
            return None

        # Convert embedding to PostgreSQL vector format
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        # Insert into database
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO knowledge_entries
                    (title, content, category, tags, source, priority, embedding, metadata, active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb, %s)
                    RETURNING id
                """, (
                    title,
                    content,
                    category,
                    tags or [],
                    source,
                    priority,
                    embedding_str,
                    json.dumps(metadata),  # Convert dict to JSON string
                    True
                ))

                result = cursor.fetchone()
                doc_id = result['id']
                logger.info(f"Added document {doc_id} to database")
                return doc_id

        except Exception as e:
            logger.error(f"Error adding document to database: {e}")
            return None

    def add_documents_batch(self, documents: List[Dict]) -> Tuple[int, int]:
        """
        Add multiple documents to the database in batch

        Args:
            documents: List of document dictionaries with keys:
                - content: str (required)
                - source: str (required)
                - title: str (optional)
                - category: str (optional)
                - tags: List[str] (optional)
                - priority: str (optional)
                - metadata: dict (optional)
                - chunk_id: str (optional)

        Returns:
            Tuple of (success_count, total_count)
        """
        logger.info(f"Adding {len(documents)} documents to database")

        # Create embeddings for all documents
        contents = [doc['content'] for doc in documents]
        embeddings = self.create_embeddings_batch(contents)

        # Insert documents
        success_count = 0

        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            if embedding is None:
                logger.warning(f"Skipping document {i+1} due to embedding failure")
                continue

            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'

            try:
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO knowledge_entries
                        (title, content, category, tags, source, priority, embedding, metadata, active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb, %s)
                        RETURNING id
                    """, (
                        doc.get('title'),
                        doc['content'],
                        doc.get('category', 'general'),
                        doc.get('tags', []),
                        doc.get('source', 'unknown'),
                        doc.get('priority', 'medium'),
                        embedding_str,
                        json.dumps(doc.get('metadata', {})),  # Convert dict to JSON string
                        True
                    ))

                    result = cursor.fetchone()
                    success_count += 1

                    if (i + 1) % 100 == 0:
                        logger.info(f"Inserted {i + 1}/{len(documents)} documents")

            except Exception as e:
                logger.error(f"Error inserting document {i+1}: {e}")
                continue

        logger.info(f"Successfully added {success_count}/{len(documents)} documents")
        return success_count, len(documents)

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = SIMILARITY_THRESHOLD,
        category: Optional[str] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Search for similar documents using vector similarity

        Args:
            query: Search query text
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            category: Optional category filter

        Returns:
            List of (metadata, similarity_score) tuples
        """
        # Create query embedding
        query_embedding = self.create_embedding(query)
        if query_embedding is None:
            logger.error("Failed to create query embedding")
            return []

        # Convert to PostgreSQL vector format
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        try:
            with get_cursor() as cursor:
                # Use the search_knowledge function from schema
                if category:
                    # Custom query with category filter
                    cursor.execute("""
                        SELECT
                            id,
                            title,
                            content,
                            category,
                            source,
                            metadata,
                            1 - (embedding <=> %s::vector) as similarity
                        FROM knowledge_entries
                        WHERE active = true
                            AND category = %s
                            AND (1 - (embedding <=> %s::vector)) > %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (embedding_str, category, embedding_str, threshold, embedding_str, top_k))
                else:
                    # Use built-in function for general search
                    cursor.execute("""
                        SELECT * FROM search_knowledge(%s::vector, %s, %s)
                    """, (embedding_str, threshold, top_k))

                results = cursor.fetchall()

                # Format results
                formatted_results = []
                for row in results:
                    metadata = {
                        'id': row['id'],
                        'title': row.get('title'),
                        'content': row['content'],
                        'category': row['category'],
                        'source': row['source'],
                        'metadata': row.get('metadata', {}),
                        'chunk_id': str(row['id'])  # Use database ID as chunk_id
                    }
                    similarity = float(row['similarity'])
                    formatted_results.append((metadata, similarity))

                logger.info(f"Found {len(formatted_results)} results for query")
                return formatted_results

        except Exception as e:
            logger.error(f"Error searching database: {e}")
            return []

    def update_document(
        self,
        doc_id: int,
        content: Optional[str] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Update an existing document

        Args:
            doc_id: Document ID to update
            content: New content (will regenerate embedding if provided)
            title: New title
            category: New category
            tags: New tags
            priority: New priority
            metadata: New metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            # If content is updated, regenerate embedding
            embedding_str = None
            if content:
                embedding = self.create_embedding(content)
                if embedding is None:
                    logger.error("Failed to create embedding for updated content")
                    return False
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'

            with get_cursor() as cursor:
                # Build dynamic UPDATE query
                updates = []
                params = []

                if content:
                    updates.append("content = %s")
                    params.append(content)
                    updates.append("embedding = %s::vector")
                    params.append(embedding_str)

                if title is not None:
                    updates.append("title = %s")
                    params.append(title)

                if category is not None:
                    updates.append("category = %s")
                    params.append(category)

                if tags is not None:
                    updates.append("tags = %s")
                    params.append(tags)

                if priority is not None:
                    updates.append("priority = %s")
                    params.append(priority)

                if metadata is not None:
                    updates.append("metadata = %s")
                    params.append(metadata)

                if not updates:
                    logger.warning("No fields to update")
                    return False

                # Add doc_id to params
                params.append(doc_id)

                query = f"""
                    UPDATE knowledge_entries
                    SET {', '.join(updates)}
                    WHERE id = %s
                """

                cursor.execute(query, params)
                logger.info(f"Updated document {doc_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False

    def delete_document(self, doc_id: int, soft: bool = True) -> bool:
        """
        Delete a document (soft or hard delete)

        Args:
            doc_id: Document ID to delete
            soft: If True, marks as inactive; if False, permanently deletes

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                if soft:
                    cursor.execute("""
                        UPDATE knowledge_entries
                        SET active = false
                        WHERE id = %s
                    """, (doc_id,))
                    logger.info(f"Soft deleted document {doc_id}")
                else:
                    cursor.execute("""
                        DELETE FROM knowledge_entries
                        WHERE id = %s
                    """, (doc_id,))
                    logger.info(f"Hard deleted document {doc_id}")

                return True

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get statistics about the knowledge base"""
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_docs,
                        COUNT(*) FILTER (WHERE active = true) as active_docs,
                        COUNT(DISTINCT category) as categories,
                        COUNT(DISTINCT source) as sources
                    FROM knowledge_entries
                """)
                stats = cursor.fetchone()

                return {
                    'total_documents': stats['total_docs'],
                    'active_documents': stats['active_docs'],
                    'categories': stats['categories'],
                    'sources': stats['sources'],
                    'embedding_dimension': self.dimension,
                    'embedding_model': self.embedding_model
                }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def clear_all(self, confirm: bool = False) -> bool:
        """
        Clear all knowledge entries (use with caution!)

        Args:
            confirm: Must be True to execute

        Returns:
            True if successful, False otherwise
        """
        if not confirm:
            logger.warning("Clear all operation requires confirm=True")
            return False

        try:
            with get_cursor() as cursor:
                cursor.execute("DELETE FROM knowledge_entries")
                logger.warning("Cleared all knowledge entries from database")
                return True

        except Exception as e:
            logger.error(f"Error clearing database: {e}")
            return False


# Global instance
db_embeddings_index = DatabaseEmbeddingsIndex()


if __name__ == "__main__":
    """Test database embeddings index"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Database Embeddings Index Test")
    print("=" * 60)

    # Get stats
    stats = db_embeddings_index.get_stats()
    print("\nCurrent Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test search
    print("\nTesting search...")
    results = db_embeddings_index.search("HDMI ARC connection", top_k=3)
    print(f"Found {len(results)} results")

    for i, (metadata, similarity) in enumerate(results, 1):
        print(f"\n{i}. Similarity: {similarity:.3f}")
        print(f"   Source: {metadata['source']}")
        print(f"   Content: {metadata['content'][:100]}...")
