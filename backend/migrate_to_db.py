"""
Migration Script: File-based to Database-backed Storage

Migrates existing knowledge base from processed_chunks.json to PostgreSQL.
Preserves all metadata and regenerates embeddings using the new model.
"""
import json
import logging
from pathlib import Path
import sys

from config import PROCESSED_DATA_DIR
from db_embeddings_index import db_embeddings_index
from database import init_connection_pool, get_cursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_processed_chunks() -> list:
    """Load processed chunks from JSON file"""
    chunks_file = PROCESSED_DATA_DIR / "processed_chunks.json"

    if not chunks_file.exists():
        logger.error(f"Processed chunks file not found: {chunks_file}")
        logger.info("Please run 'python ingest_docs.py' first to process documents")
        return []

    try:
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
        return chunks

    except Exception as e:
        logger.error(f"Error loading chunks: {e}")
        return []


def check_existing_data() -> int:
    """Check if there's already data in the database"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM knowledge_entries WHERE active = true")
            result = cursor.fetchone()
            return result['count']
    except Exception as e:
        logger.error(f"Error checking existing data: {e}")
        return 0


def prepare_documents(chunks: list) -> list:
    """
    Convert processed chunks to document format for database insertion

    Args:
        chunks: List of chunk dictionaries from processed_chunks.json

    Returns:
        List of document dictionaries ready for insertion
    """
    documents = []

    for chunk in chunks:
        # Extract metadata
        metadata = chunk.get('metadata', {})

        # Determine category based on source file name
        source = chunk.get('source', 'unknown')
        category = 'general'

        if 'troubleshooting' in source.lower():
            category = 'troubleshooting'
        elif 'truth' in source.lower() or 'i/o' in source.lower():
            category = 'technical-specs'
        elif 'accessories' in source.lower() or 'mounting' in source.lower():
            category = 'installation'
        elif 'sell' in source.lower() or 'site' in source.lower():
            category = 'product-info'
        elif 'line-output' in source.lower() or 'dsp' in source.lower():
            category = 'technical-specs'

        # Extract tags from content (simple keyword extraction)
        content_lower = chunk['content'].lower()
        tags = []

        # Common technical terms
        if 'hdmi' in content_lower:
            tags.append('HDMI')
        if 'arc' in content_lower or 'earc' in content_lower:
            tags.append('ARC')
        if 'amplifier' in content_lower or 'amp' in content_lower:
            tags.append('amplifier')
        if 'speaker' in content_lower:
            tags.append('speakers')
        if 'input' in content_lower:
            tags.append('inputs')
        if 'output' in content_lower:
            tags.append('outputs')
        if 'dsp' in content_lower:
            tags.append('DSP')
        if 'sonarc' in content_lower:
            tags.append('SonArc')
        if 'firmware' in content_lower:
            tags.append('firmware')
        if 'troubleshoot' in content_lower or 'issue' in content_lower:
            tags.append('troubleshooting')

        # Create document
        doc = {
            'content': chunk['content'],
            'source': source,
            'title': metadata.get('title'),
            'category': category,
            'tags': tags,
            'priority': 'medium',
            'metadata': {
                'chunk_index': metadata.get('chunk_index'),
                'total_chunks': metadata.get('total_chunks'),
                'pages': metadata.get('pages'),
                'original_chunk_id': chunk.get('chunk_id')
            },
            'chunk_id': chunk.get('chunk_id')
        }

        documents.append(doc)

    logger.info(f"Prepared {len(documents)} documents for insertion")
    return documents


def migrate():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("UA2-125 Chatbot - Database Migration")
    logger.info("=" * 60)

    # Initialize database connection
    logger.info("\n1. Checking database connection...")
    init_connection_pool()

    # Check for existing data
    logger.info("\n2. Checking for existing data...")
    existing_count = check_existing_data()

    if existing_count > 0:
        logger.warning(f"Found {existing_count} existing documents in database")
        response = input("\nDo you want to clear existing data and start fresh? (yes/no): ")

        if response.lower() == 'yes':
            logger.info("Clearing existing data...")
            if db_embeddings_index.clear_all(confirm=True):
                logger.info("✅ Existing data cleared")
            else:
                logger.error("❌ Failed to clear existing data")
                return False
        else:
            logger.info("Keeping existing data and adding new entries")

    # Load processed chunks
    logger.info("\n3. Loading processed chunks...")
    chunks = load_processed_chunks()

    if not chunks:
        logger.error("No chunks to migrate")
        return False

    # Prepare documents
    logger.info("\n4. Preparing documents...")
    documents = prepare_documents(chunks)

    # Migrate to database
    logger.info(f"\n5. Migrating {len(documents)} documents to database...")
    logger.info("This will take a few minutes to generate embeddings...")

    success_count, total_count = db_embeddings_index.add_documents_batch(documents)

    # Show results
    logger.info("\n" + "=" * 60)
    logger.info("Migration Results:")
    logger.info(f"  Total documents: {total_count}")
    logger.info(f"  Successfully migrated: {success_count}")
    logger.info(f"  Failed: {total_count - success_count}")

    if success_count == total_count:
        logger.info("✅ Migration completed successfully!")
    elif success_count > 0:
        logger.warning(f"⚠️  Partial migration: {success_count}/{total_count} succeeded")
    else:
        logger.error("❌ Migration failed")
        return False

    # Show final statistics
    logger.info("\n6. Final database statistics:")
    stats = db_embeddings_index.get_stats()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    logger.info("\n" + "=" * 60)
    logger.info("🚀 Database migration complete!")
    logger.info("   The chatbot is now database-backed.")
    logger.info("   You can now:")
    logger.info("   - Add new knowledge without full re-ingestion")
    logger.info("   - Update existing entries")
    logger.info("   - Track conversations and feedback")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nMigration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
