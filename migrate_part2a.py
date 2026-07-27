import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'superonline_enterprise.db')

def run_migration():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(complaints)")
    columns = [col["name"] for col in cursor.fetchall()]

    new_columns = {
        "like_count": "INTEGER DEFAULT 0",
        "comment_count": "INTEGER DEFAULT 0",
        "share_count": "INTEGER DEFAULT 0",
        "view_count": "INTEGER DEFAULT 0",
        "engagement_count": "INTEGER DEFAULT 0"
    }

    added_count = 0
    for col, dtype in new_columns.items():
        if col not in columns:
            print(f"Adding column {col} {dtype}...")
            cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col} {dtype}")
            added_count += 1

    print(f"Added {added_count} new columns.")

    # Backfill missing values with 0
    print("Updating existing records to ensure 0 values...")
    cursor.execute("""
        UPDATE complaints 
        SET 
            like_count = COALESCE(like_count, 0),
            comment_count = COALESCE(comment_count, 0),
            share_count = COALESCE(share_count, 0),
            view_count = COALESCE(view_count, 0),
            engagement_count = COALESCE(engagement_count, 0)
    """)
    print(f"Updated {cursor.rowcount} records.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
