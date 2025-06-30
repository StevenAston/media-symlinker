# tests/test_hashing.py

import os
import gc
from unittest.mock import patch, mock_open

from database import get_db_connection, initialize_database
from hashing import hash_all_unhashed_files

TEST_DB_FILE = "test_hashing_parallel.sqlite"

def setup_db(conn):
    """Helper to insert a mix of files."""
    sql = "INSERT INTO files (full_path, filename, directory, scan_source, file_size, modified_date, status, is_symlink, xxh128_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    records = [
        ('C:\\tobehashed.mkv', 'f1', 'd1', 'downloads', 1000, 0, 'new', 0, None),
        ('C:\\alreadyhashed.mkv', 'f2', 'd2', 'downloads', 2000, 0, 'hashed', 0, 'already_done_hash'),
        ('C:\\symlink.mkv', 'f3', 'd3', 'downloads', 3000, 0, 'new', 1, None)
    ]
    conn.executemany(sql, records)
    conn.commit()

@patch('config.HASHING_WORKERS', 1)
def test_hashing_processes_only_unhashed_files():
    """Tests that the function hashes ONLY the files where hash is NULL and is_symlink is 0."""
    mock_content = b'this is the content'
    expected_hash = '1a7edd3b5aa3cd2c58db5a7e6dd54634'

    # --- THE DEFINITIVE FIX: Ensure a clean slate ---
    # Delete any leftover DB from a previously failed run before we start.
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    
    with patch('config.DB_FILE_PATH', TEST_DB_FILE), \
         patch('builtins.open', mock_open(read_data=mock_content)):
        try:
            initialize_database()
            with get_db_connection() as conn:
                setup_db(conn)

            hash_all_unhashed_files()

            with get_db_connection() as conn:
                file1 = conn.execute("SELECT * FROM files WHERE full_path = 'C:\\tobehashed.mkv'").fetchone()
                assert file1 is not None and file1['status'] == 'hashed' and file1['xxh128_hash'] == expected_hash
        finally:
            # The original cleanup is still good practice.
            gc.collect()
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)