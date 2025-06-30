# tests/test_file_scanner.py

import os
import gc
from unittest.mock import patch, MagicMock

import config
from database import get_db_connection, initialize_database
from file_scanner import scan_directory # Import the function we are testing

TEST_DB_FILE = "test_scanner.sqlite"

def test_scan_directory_populates_db():
    """
    Tests that scan_directory correctly processes data from the generator
    and populates the database.
    """
    # This is the clean data our mock generator will provide.
    mock_file_data = [
        {"full_path": 'C:\\RealFile.mkv', "file_size": 1000, "modified_date": 0, "is_symlink": False},
        {"full_path": 'C:\\SymlinkFile.mkv', "file_size": 2000, "modified_date": 0, "is_symlink": True}
    ]

    # We patch the DB path and our private generator function. This is simple and robust.
    with patch('config.DB_FILE_PATH', TEST_DB_FILE), \
         patch('file_scanner._iterate_everything_results', return_value=mock_file_data):
        
        try:
            # Delete any leftover DB from a previously failed run.
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)
            
            initialize_database()
            # The 'dll' object can now be a simple mock because its methods are never called.
            mock_dll = MagicMock()

            # Run the function we are testing.
            scan_directory(mock_dll, config.DOWNLOADS_PATH, 'downloads')

            # Verify the results in the database.
            with get_db_connection() as conn:
                real_file = conn.execute("SELECT * FROM files WHERE full_path = 'C:\\RealFile.mkv'").fetchone()
                symlink_file = conn.execute("SELECT * FROM files WHERE full_path = 'C:\\SymlinkFile.mkv'").fetchone()
                
                assert real_file is not None
                assert symlink_file is not None
                
                assert real_file['is_symlink'] == 0
                assert symlink_file['is_symlink'] == 1
        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)