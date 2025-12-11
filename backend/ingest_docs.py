"""
Document Ingestion Script

This script processes documents and creates embeddings for the RAG system.
Supports: JSON, TXT, PDF (future), and structured data formats.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict
import sys

from config import (
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)
from embeddings_index import embeddings_index

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process and chunk documents for ingestion"""

    def __init__(self):
        self.chunks = []

    def chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """
        Split text into overlapping chunks

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk (characters)
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundaries
            if end < len(text):
                # Look for sentence endings
                for delimiter in ['. ', '.\n', '! ', '? ', '\n\n']:
                    last_delimiter = text[start:end].rfind(delimiter)
                    if last_delimiter != -1:
                        end = start + last_delimiter + len(delimiter)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Ensure we always move forward to avoid infinite loops
            new_start = end - overlap
            if new_start <= start:
                new_start = start + 1
            start = new_start

        return chunks

    def process_json_file(self, file_path: Path) -> List[Dict]:
        """
        Process JSON file containing structured knowledge base entries

        Expected format:
        [
            {
                "title": "...",
                "content": "...",
                "category": "...",
                "source": "..."
            }
        ]
        """
        logger.info(f"Processing JSON file: {file_path.name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            chunks = []

            if isinstance(data, list):
                for entry in data:
                    content = entry.get('content', '')
                    title = entry.get('title', '')
                    category = entry.get('category', 'general')
                    source = entry.get('source', file_path.name)

                    # Combine title and content
                    full_text = f"{title}\n\n{content}" if title else content

                    # Chunk the content
                    text_chunks = self.chunk_text(full_text)

                    for i, chunk_text in enumerate(text_chunks):
                        chunk_id = str(uuid.uuid4())
                        chunks.append({
                            'content': chunk_text,
                            'metadata': {
                                'title': title,
                                'category': category,
                                'chunk_index': i,
                                'total_chunks': len(text_chunks)
                            },
                            'source': source,
                            'chunk_id': chunk_id
                        })

            logger.info(f"Created {len(chunks)} chunks from JSON file")
            return chunks

        except Exception as e:
            logger.error(f"Error processing JSON file {file_path}: {e}")
            return []

    def process_text_file(self, file_path: Path) -> List[Dict]:
        """Process plain text file"""
        logger.info(f"Processing text file: {file_path.name}")

        try:
            logger.info(f"  Reading file...")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"  Read {len(content)} characters")

            logger.info(f"  Chunking text...")
            text_chunks = self.chunk_text(content)
            logger.info(f"  Created {len(text_chunks)} text chunks")

            chunks = []

            for i, chunk_text in enumerate(text_chunks):
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    'content': chunk_text,
                    'metadata': {
                        'chunk_index': i,
                        'total_chunks': len(text_chunks)
                    },
                    'source': file_path.name,
                    'chunk_id': chunk_id
                })

            logger.info(f"Created {len(chunks)} chunks from text file")
            return chunks

        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            return []

    def process_pdf_file(self, file_path: Path) -> List[Dict]:
        """Process PDF file"""
        logger.info(f"Processing PDF file: {file_path.name}")

        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            text = ""

            # Extract text from all pages
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n\n[Page {page_num}]\n{page_text}"

            if not text.strip():
                logger.warning(f"No text extracted from PDF: {file_path.name}")
                return []

            # Chunk the extracted text
            text_chunks = self.chunk_text(text)
            chunks = []

            for i, chunk_text in enumerate(text_chunks):
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    'content': chunk_text,
                    'metadata': {
                        'chunk_index': i,
                        'total_chunks': len(text_chunks),
                        'pages': len(reader.pages)
                    },
                    'source': file_path.name,
                    'chunk_id': chunk_id
                })

            logger.info(f"Created {len(chunks)} chunks from PDF ({len(reader.pages)} pages)")
            return chunks

        except Exception as e:
            logger.error(f"Error processing PDF file {file_path}: {e}")
            return []

    def process_directory(self, directory: Path) -> List[Dict]:
        """Process all supported files in directory"""
        all_chunks = []

        # Process JSON files
        for json_file in directory.glob("*.json"):
            chunks = self.process_json_file(json_file)
            all_chunks.extend(chunks)

        # Process TXT files
        for txt_file in directory.glob("*.txt"):
            chunks = self.process_text_file(txt_file)
            all_chunks.extend(chunks)

        # Process PDF files
        for pdf_file in directory.glob("*.pdf"):
            chunks = self.process_pdf_file(pdf_file)
            all_chunks.extend(chunks)

        logger.info(f"Total chunks created: {len(all_chunks)}")
        return all_chunks


def main():
    """Main ingestion process"""
    logger.info("=" * 60)
    logger.info("UA2-125 AI Chatbot - Document Ingestion")
    logger.info("=" * 60)

    # Initialize processor
    processor = DocumentProcessor()

    # Check if raw data directory exists and has files
    if not RAW_DATA_DIR.exists():
        logger.error(f"Raw data directory not found: {RAW_DATA_DIR}")
        logger.info("Please create the directory and add your documents.")
        sys.exit(1)

    files = list(RAW_DATA_DIR.glob("*.json")) + list(RAW_DATA_DIR.glob("*.txt")) + list(RAW_DATA_DIR.glob("*.pdf"))
    if not files:
        logger.warning(f"No documents found in {RAW_DATA_DIR}")
        logger.info("Please add knowledge base files to the data/raw directory.")
        logger.info("\nSupported formats:")
        logger.info("  - JSON: Structured knowledge entries")
        logger.info("  - TXT: Plain text documents")
        logger.info("  - PDF: PDF documents (manuals, datasheets, etc.)")
        sys.exit(1)

    # Process documents
    logger.info(f"\nProcessing files from: {RAW_DATA_DIR}")
    all_chunks = processor.process_directory(RAW_DATA_DIR)

    if not all_chunks:
        logger.error("No chunks created. Please check your input files.")
        sys.exit(1)

    # Save processed chunks
    processed_file = PROCESSED_DATA_DIR / "processed_chunks.json"
    with open(processed_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2)
    logger.info(f"\n✅ Saved {len(all_chunks)} processed chunks to {processed_file}")

    # Create embeddings and build index
    logger.info("\n📊 Creating embeddings (this may take a few minutes)...")
    success = embeddings_index.add_documents(all_chunks)

    if success:
        # Save index to disk
        embeddings_index.save_index()
        logger.info("\n✅ Embeddings created and index saved successfully!")

        # Show stats
        stats = embeddings_index.get_stats()
        logger.info("\n" + "=" * 60)
        logger.info("Index Statistics:")
        logger.info(f"  Total chunks: {stats['total_chunks']}")
        logger.info(f"  Embedding dimension: {stats['embedding_dimension']}")
        logger.info(f"  Index size: {stats['index_size_mb']:.2f} MB")
        logger.info("=" * 60)

        logger.info("\n🚀 Ready to start the chatbot server!")
        logger.info("   Run: python app.py")
    else:
        logger.error("\n❌ Failed to create embeddings. Please check your OpenAI API key.")
        sys.exit(1)


if __name__ == "__main__":
    main()
