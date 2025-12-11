"""
Vector store implementation using numpy and OpenAI embeddings
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    VECTOR_INDEX_FILE,
    METADATA_FILE,
    TOP_K_RESULTS,
    SIMILARITY_THRESHOLD
)

logger = logging.getLogger(__name__)


class EmbeddingsIndex:
    """Vector store for document embeddings with cosine similarity search"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: List[Dict] = []
        self.is_loaded = False

    def load_index(self) -> bool:
        """Load existing embeddings and metadata from disk"""
        try:
            if VECTOR_INDEX_FILE.exists() and METADATA_FILE.exists():
                self.embeddings = np.load(str(VECTOR_INDEX_FILE))
                with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                self.is_loaded = True
                logger.info(f"Loaded {len(self.metadata)} document chunks from index")
                return True
            else:
                logger.warning("Index files not found. Please run document ingestion.")
                return False
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            return False

    def save_index(self) -> bool:
        """Save embeddings and metadata to disk"""
        try:
            if self.embeddings is not None:
                np.save(str(VECTOR_INDEX_FILE), self.embeddings)
                with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.metadata, f, indent=2)
                logger.info(f"Saved {len(self.metadata)} document chunks to index")
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving index: {e}")
            return False

    def create_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a single text using OpenAI API"""
        try:
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            embedding = np.array(response.data[0].embedding)
            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise

    def create_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts in batch"""
        try:
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts
            )
            embeddings = np.array([item.embedding for item in response.data])
            return embeddings
        except Exception as e:
            logger.error(f"Error creating batch embeddings: {e}")
            raise

    def add_documents(self, chunks: List[Dict]) -> bool:
        """
        Add document chunks to the index

        Args:
            chunks: List of dicts with 'content', 'metadata', 'source', 'chunk_id'
        """
        try:
            texts = [chunk['content'] for chunk in chunks]
            logger.info(f"Creating embeddings for {len(texts)} chunks...")

            # Create embeddings in smaller batches to avoid API limits
            batch_size = 100  # Process 100 chunks at a time
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}...")
                batch_embeddings = self.create_embeddings_batch(batch_texts)
                all_embeddings.append(batch_embeddings)

            new_embeddings = np.vstack(all_embeddings) if len(all_embeddings) > 1 else all_embeddings[0]

            # Update index
            if self.embeddings is None:
                self.embeddings = new_embeddings
                self.metadata = chunks
            else:
                self.embeddings = np.vstack([self.embeddings, new_embeddings])
                self.metadata.extend(chunks)

            self.is_loaded = True
            logger.info(f"Added {len(chunks)} chunks to index")
            return True
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return False

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def search(
        self,
        query: str,
        top_k: int = TOP_K_RESULTS,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> List[Tuple[Dict, float]]:
        """
        Search for relevant documents using cosine similarity

        Args:
            query: Search query text
            top_k: Number of top results to return
            threshold: Minimum similarity score threshold

        Returns:
            List of tuples (metadata_dict, similarity_score)
        """
        if not self.is_loaded or self.embeddings is None:
            logger.warning("Index not loaded. Please load or create index first.")
            return []

        try:
            # Create query embedding
            query_embedding = self.create_embedding(query)

            # Calculate similarities
            similarities = np.array([
                self.cosine_similarity(query_embedding, doc_embedding)
                for doc_embedding in self.embeddings
            ])

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]

            # Filter by threshold and prepare results
            results = []
            for idx in top_indices:
                similarity = float(similarities[idx])
                if similarity >= threshold:
                    results.append((self.metadata[idx], similarity))

            logger.info(f"Found {len(results)} relevant chunks for query")
            return results
        except Exception as e:
            logger.error(f"Error searching index: {e}")
            return []

    def get_stats(self) -> Dict:
        """Get statistics about the index"""
        return {
            "is_loaded": self.is_loaded,
            "total_chunks": len(self.metadata) if self.metadata else 0,
            "embedding_dimension": self.embeddings.shape[1] if self.embeddings is not None else 0,
            "index_size_mb": self.embeddings.nbytes / (1024 * 1024) if self.embeddings is not None else 0
        }


# Global instance
embeddings_index = EmbeddingsIndex()
