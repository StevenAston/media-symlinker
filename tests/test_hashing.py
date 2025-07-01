# tests/test_hashing.py

import os
import gc
from unittest.mock import patch, MagicMock
import logging

import config
from database import get_db_connection, initialize_database
from hashing import hash_unhashed_files_per_drive

TEST_DB_FILE = "test_hashing_per_drive.sqlite"

def setup_db(conn):
    """Helper to insert a mix of files on different drives."""
    sql = "INSERT INTO files (full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, status, is_symlink, xxh128_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    records = [
        ('D:\\tobehashed1.mkv', 'D', 'f1', 'D:\\', 'downloads', 1000, 0, 'new', 0, None),
        ('E:\\tobehashed2.mkv', 'E', 'f2', 'E:\\', 'downloads', 2000, 0, 'new', 0, None),
        ('D:\\alreadyhashed.mkv', 'D', 'f3', 'D:\\', 'downloads', 3000, 0, 'hashed', 0, 'already_done_hash'),
        ('E:\\symlink.mkv', 'E', 'f4', 'E:\\', 'downloads', 4000, 0, 'new', 1, None)
    ]
    conn.executemany(sql, records)
    conn.commit()

# @patch('hashing.ThreadPoolExecutor')
def test_hashing_groups_by_drive_and_processes_correctly():
    """
    Tests that the per-drive hashing function correctly groups files and processes them.
    """
    logging.debug("TEST: Starting test_hashing_groups_by_drive_and_processes_correctly.")
    # Use a try/finally block to guarantee cleanup
    try:
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
            logging.debug("TEST: Removed existing test database.")
            
        # We patch the worker function itself. This is the simplest, most reliable mock.
        with patch('hashing._hash_file_worker') as mock_hash_worker:
            def hash_worker_side_effect(file_info):
                file_id, file_path, file_size = file_info
                logging.debug(f"TEST_MOCK_WORKER: Called for file {file_path}")
                mock_hash = f"hash_for_{os.path.basename(file_path)}"
                return {"id": file_id, "hash": mock_hash, "size": file_size}
            
            mock_hash_worker.side_effect = hash_worker_side_effect

            with patch('config.DB_FILE_PATH', TEST_DB_FILE):
                logging.debug("TEST: Initializing database.")
                initialize_database()
                with get_db_connection() as conn:
                    logging.debug("TEST: Setting up DB with mock records.")
                    setup_db(conn)

                logging.debug("TEST: Calling hash_unhashed_files_per_drive().")
                # We need to also patch the color helper so it doesn't fail
                with patch('hashing.get_hsl_color_for_bar', return_value="#ffffff"):
                    hash_unhashed_files_per_drive()
                logging.debug("TEST: hash_unhashed_files_per_drive() finished.")

                # --- Verification ---
                logging.debug("TEST: Starting verification.")
                with get_db_connection() as conn:
                    file_d = conn.execute("SELECT * FROM files WHERE full_path = 'D:\\tobehashed1.mkv'").fetchone()
                    logging.debug(f"TEST: Verifying file D. Status: {file_d['status']}, Hash: {file_d['xxh128_hash']}")
                    assert file_d['xxh128_hash'] == 'hash_for_tobehashed1.mkv'
                    
                    file_e = conn.execute("SELECT * FROM files WHERE full_path = 'E:\\tobehashed2.mkv'").fetchone()
                    logging.debug(f"TEST: Verifying file E. Status: {file_e['status']}, Hash: {file_e['xxh128_hash']}")
                    assert file_e['xxh128_hash'] == 'hash_for_tobehashed2.mkv'

    finally:
        gc.collect()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
            logging.debug("TEST: Cleaned up test database.")