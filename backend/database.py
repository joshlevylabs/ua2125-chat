"""
Database Configuration and Connection Module

Handles PostgreSQL connection with pgvector support for embeddings storage.
"""
import logging
import os
from typing import Optional
from contextlib import contextmanager
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Database configuration from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'ua2125_chatbot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_SSL = os.getenv('DB_SSL', 'false').lower() == 'true'

# Connection pool
_connection_pool: Optional[SimpleConnectionPool] = None


def get_connection_string() -> str:
    """Get PostgreSQL connection string"""
    if DATABASE_URL:
        return DATABASE_URL

    conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Add SSL mode if enabled
    if DB_SSL:
        conn_str += "?sslmode=require"

    return conn_str


def init_connection_pool(min_conn=1, max_conn=10):
    """Initialize connection pool"""
    global _connection_pool

    if _connection_pool is not None:
        logger.warning("Connection pool already initialized")
        return

    try:
        _connection_pool = SimpleConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            dsn=get_connection_string()
        )
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def close_connection_pool():
    """Close all connections in the pool"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_connection():
    """Get a connection from the pool (context manager)"""
    global _connection_pool

    if _connection_pool is None:
        init_connection_pool()

    conn = _connection_pool.getconn()
    try:
        yield conn
    finally:
        _connection_pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor=True):
    """Get a cursor from a connection (context manager)"""
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()


def test_connection() -> bool:
    """Test database connection"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                logger.info("✅ Database connection successful")
                return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def check_pgvector_extension() -> bool:
    """Check if pgvector extension is installed"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
            result = cursor.fetchone()
            if result:
                logger.info("✅ pgvector extension is installed")
                return True
            else:
                logger.warning("⚠️  pgvector extension is not installed")
                return False
    except Exception as e:
        logger.error(f"Error checking pgvector extension: {e}")
        return False


def enable_pgvector_extension():
    """Enable pgvector extension (requires superuser privileges)"""
    try:
        with get_cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("✅ pgvector extension enabled")
            return True
    except Exception as e:
        logger.error(f"Failed to enable pgvector extension: {e}")
        logger.info("You may need to run this SQL command manually as a superuser:")
        logger.info("  CREATE EXTENSION vector;")
        return False


def create_schema():
    """Create database schema if it doesn't exist"""
    schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')

    if not os.path.exists(schema_file):
        logger.error(f"Schema file not found: {schema_file}")
        return False

    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        with get_cursor() as cursor:
            cursor.execute(schema_sql)

        logger.info("✅ Database schema created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create schema: {e}")
        return False


def init_database():
    """Initialize database: connection pool, pgvector, and schema"""
    logger.info("Initializing database...")

    # Test connection
    if not test_connection():
        return False

    # Check/enable pgvector
    if not check_pgvector_extension():
        enable_pgvector_extension()

    # Create schema
    if not create_schema():
        return False

    logger.info("✅ Database initialized successfully")
    return True


if __name__ == "__main__":
    """Test database connection and initialization"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)
    print(f"Host: {DB_HOST}")
    print(f"Port: {DB_PORT}")
    print(f"Database: {DB_NAME}")
    print(f"User: {DB_USER}")
    print("=" * 60)

    if init_database():
        print("\n✅ Database is ready!")
    else:
        print("\n❌ Database initialization failed")
