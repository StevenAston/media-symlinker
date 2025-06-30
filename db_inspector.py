# db_inspector.py

import logging
from database import get_db_connection

def inspect_database_state(step_name):
    """
    Connects to the database and prints a detailed health report.
    """
    logging.info(f"--- Running Database Health Check (after {step_name}) ---")
    try:
        with get_db_connection() as conn:
            # 1. Total number of files
            total_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            logging.info(f"Total rows in 'files' table: {total_count}")

            # 2. Files with NULL hash (the ones we expect to process)
            null_hash_count = conn.execute("SELECT COUNT(*) FROM files WHERE xxh128_hash IS NULL").fetchone()[0]
            logging.info(f"Rows where xxh128_hash IS NULL: {null_hash_count}")

            # 3. Files with an EMPTY STRING hash (a common source of bugs)
            empty_string_hash_count = conn.execute("SELECT COUNT(*) FROM files WHERE xxh128_hash = ''").fetchone()[0]
            if empty_string_hash_count > 0:
                logging.warning(f"CRITICAL WARNING: Found {empty_string_hash_count} rows where hash is an empty string, not NULL!")

            # 4. Files with some other non-NULL value
            other_hash_count = conn.execute("SELECT COUNT(*) FROM files WHERE xxh128_hash IS NOT NULL AND xxh128_hash != ''").fetchone()[0]
            logging.info(f"Rows with a non-empty hash value: {other_hash_count}")

            # 5. Show a few examples of "new" files
            logging.info("Example rows with status = 'new':")
            examples = conn.execute("SELECT id, full_path, status, xxh128_hash FROM files WHERE status = 'new' LIMIT 3").fetchall()
            if examples:
                for row in examples:
                    # repr() is used to clearly show if a value is None or an empty string ''
                    logging.info(f"  ID: {row['id']}, Path: {row['full_path']}, Status: {row['status']}, Hash: {repr(row['xxh128_hash'])}")
            else:
                logging.info("  No files with status = 'new' found.")

    except Exception as e:
        logging.error(f"An error occurred during database inspection: {e}")
    
    logging.info("--- End of Health Check ---")