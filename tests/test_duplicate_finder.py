# tests/test_duplicate_finder.py

import os
import gc
from unittest.mock import patch  # <-- IMPORT THE PATCH FUNCTION

import config
from database import get_db_connection, initialize_database
from duplicate_finder import identify_and_link_duplicates

TEST_DB_FILE = "test_finder.sqlite"

def setup_test_db_with_hashed_dupes():
    """Helper function to create a db with two files that are duplicates."""
    initialize_database()
    
    shared_hash = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'

    with get_db_connection() as conn:
        # File from downloads
        conn.execute("""
            INSERT INTO files (id, full_path, scan_source, status, xxh128_hash, file_size, filename, directory, modified_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'C:\\Downloads\\movie.mkv', 'downloads', 'hashed', shared_hash, 1000, 'f', 'd', 0))
        
        # Confirmed duplicate in media
        conn.execute("""
            INSERT INTO files (id, full_path, scan_source, status, xxh128_hash, file_size, filename, directory, modified_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 'D:\\Media\\Movies\\movie.mkv', 'media', 'hashed', shared_hash, 1000, 'f', 'd', 0))

        # A non-duplicate file
        conn.execute("""
            INSERT INTO files (id, full_path, scan_source, status, xxh128_hash, file_size, filename, directory, modified_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (3, 'C:\\Downloads\\other.mkv', 'downloads', 'hashed', 'ffffffffffffffffffffffffffffffff', 500, 'f', 'd', 0))
        conn.commit()

def test_identify_and_link_duplicates():
    """
    Tests that the function correctly identifies duplicate files by hash
    and updates the database records accordingly.
    """
    with patch('config.DB_FILE_PATH', TEST_DB_FILE):
        try:
            setup_test_db_with_hashed_dupes()

            num_found = identify_and_link_duplicates()
            
            assert num_found == 1, "Expected to find 1 duplicate pair"

            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM files WHERE id = 1")
                download_file = cursor.fetchone()
                assert download_file['status'] == 'duplicate_found'
                assert download_file['duplicate_of_id'] == 2

                cursor.execute("SELECT * FROM files WHERE id = 2")
                media_file = cursor.fetchone()
                assert media_file['status'] == 'hashed'
                assert media_file['duplicate_of_id'] is None

                cursor.execute("SELECT * FROM files WHERE id = 3")
                other_file = cursor.fetchone()
                assert other_file['status'] == 'hashed'

        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)