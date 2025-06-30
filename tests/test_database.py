# tests/test_database.py

import os
import gc
from unittest.mock import patch

# --- CHANGE IS HERE ---
# We now import BOTH functions from our database module.
from database import initialize_database, get_db_connection

TEST_DB_FILE = "test_linker.sqlite"

def test_initialize_database_creates_table_and_columns():
    """
    Tests that initialize_database creates the DB file and the 'files' table
    with all the expected columns.
    """
    # Patch the config to use our temporary test database filename.
    with patch('config.DB_FILE_PATH', TEST_DB_FILE):
        try:
            # 1. Run the function being tested. Our improved get_db_connection
            #    ensures the connection used here is properly closed.
            initialize_database()

            # 2. Assert that the database file was actually created.
            assert os.path.exists(TEST_DB_FILE), "Database file was not created"

            # 3. Connect to the new DB to verify its contents.
            # --- CRITICAL FIX IS HERE ---
            # We now use our OWN get_db_connection context manager, which
            # GUARANTEES this connection will be closed before the 'finally' block.
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Verify the 'files' table exists.
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files';")
                assert cursor.fetchone() is not None, "'files' table was not created"

                # Verify the table has the correct columns.
                cursor.execute("PRAGMA table_info(files);")
                columns_info = cursor.fetchall()
                column_names = [col[1] for col in columns_info]
                
                expected_columns = [
                    'id', 'full_path', 'filename', 'directory', 'scan_source',
                    'file_size', 'modified_date', 'xxh128_hash', 'hash_date',
                    'status', 'duplicate_of_id',
                    'is_symlink'
                ]
                
                assert column_names == expected_columns, "Table columns are not correct"
            # --- The connection used for testing is now guaranteed to be closed ---

        finally:
            # Calling gc.collect() is good practice for cleanup, especially on Windows.
            gc.collect()
            # This should now succeed as all connections have been closed.
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)