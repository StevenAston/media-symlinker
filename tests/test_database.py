# tests/test_database.py

import os
import gc
from unittest.mock import patch
import sqlite3

from database import get_db_connection, initialize_database

TEST_DB_FILE = "test_db.sqlite"

def test_initialize_database_creates_table_and_columns():
    """
    Tests that initialize_database creates the DB file and the 'files' table
    with all the expected columns.
    """
    with patch('config.DB_FILE_PATH', TEST_DB_FILE):
        try:
            # Ensure the test starts clean
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)

            initialize_database()
            assert os.path.exists(TEST_DB_FILE), "Database file was not created"

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files';")
                assert cursor.fetchone() is not None, "'files' table was not created"

                cursor.execute("PRAGMA table_info(files);")
                columns_info = cursor.fetchall()
                actual_columns = {col[1] for col in columns_info}

                # This is the full, final set of columns for the table.
                expected_columns = {
                    'id', 'full_path', 'physical_drive', 'filename', 'directory',
                    'scan_source', 'file_size', 'modified_date', 'is_symlink',
                    'status', 'xxh128_hash', 'hash_date', 'duplicate_of_id',
                    'torrent_hash', 'torrent_name', 'category', 'tags'
                }

                assert actual_columns == expected_columns, f"Table columns mismatch. Got {actual_columns}"

        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)