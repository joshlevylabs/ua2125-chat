"""Quick script to check database tables"""
from database import get_cursor

with get_cursor() as cursor:
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()

    print("\n=== Database Tables ===")
    for table in tables:
        print(f"  - {table['table_name']}")

    print(f"\nTotal tables: {len(tables)}")
