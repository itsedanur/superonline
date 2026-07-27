import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "superonline_enterprise.db")

def migrate():
    print(f"Connecting to {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    columns_to_add = {
        "platform": "VARCHAR DEFAULT 'SIKAYETVAR'",
        "content_type": "VARCHAR DEFAULT 'COMPLAINT'",
        "business_unit": "VARCHAR DEFAULT 'INTERNET_SERVICES'",
        "brand": "VARCHAR DEFAULT 'SUPERONLINE'",
        "brand_replied": "INTEGER DEFAULT 0",
        "case_status": "VARCHAR DEFAULT 'NEW'",
        "brand_reply_at": "TIMESTAMP DEFAULT NULL",
        "first_response_at": "TIMESTAMP DEFAULT NULL",
        "resolved_at": "TIMESTAMP DEFAULT NULL",
        "closed_at": "TIMESTAMP DEFAULT NULL",
        "source_author_id": "TEXT",
        "source_author_masked": "TEXT",
        "source_language": "VARCHAR DEFAULT 'tr'",
        "source_metadata_json": "TEXT DEFAULT '{}'"
    }

    # Get existing columns
    cursor.execute("PRAGMA table_info(complaints)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {existing_columns}")

    added_count = 0
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            print(f"Adding column {col_name} {col_type}...")
            cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type}")
            added_count += 1
        else:
            print(f"Column {col_name} already exists. Skipping.")

    print(f"Added {added_count} new columns.")

    # Check backfill
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE platform IS NULL OR platform = '' OR platform = 'SIKAYETVAR'")
    count = cursor.fetchone()[0]
    print(f"Total existing records matching backfill criteria: {count}")

    print("Updating existing records...")
    cursor.execute("""
        UPDATE complaints 
        SET platform = 'SIKAYETVAR',
            content_type = 'COMPLAINT',
            business_unit = 'INTERNET_SERVICES',
            brand = 'SUPERONLINE',
            brand_replied = 0,
            case_status = 'NEW'
        WHERE platform IS NULL OR platform = '' OR platform = 'SIKAYETVAR'
    """)
    print(f"Updated {cursor.rowcount} records.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
