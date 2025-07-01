# tests/test_file_scanner.py

import os
import gc
from unittest.mock import patch, MagicMock

import config
from database import get_db_connection, initialize_database
from file_scanner import scan_directory

TEST_DB_FILE = "test_scanner.sqlite"

def test_scan_directory_populates_db_from_scratch():
    """
    Tests that scan_directory correctly processes data from the generator
    and populates an empty database.
    """
    mock_file_data = [
        {"full_path": 'C:\\RealFile.mkv', "file_size": 1000, "modified_date": 0, "is_symlink": False},
        {"full_path": 'C:\\SymlinkFile.mkv', "file_size": 2000, "modified_date": 0, "is_symlink": True}
    ]

    with patch('config.DB_FILE_PATH', TEST_DB_FILE), \
         patch('file_scanner._iterate_everything_results', return_value=mock_file_data):
        try:
            if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
            initialize_database()
            mock_dll = MagicMock()

            # This call now correctly passes the 4 required arguments.
            scan_directory(mock_dll, 'C:\\somepath', 'downloads', 'C')

            with get_db_connection() as conn:
                results = conn.execute("SELECT * FROM files ORDER BY full_path").fetchall()
                assert len(results) == 2
                assert results[0]['full_path'] == 'C:\\RealFile.mkv'
                assert results[0]['physical_drive'] == 'C'
        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)

def test_scan_directory_resets_status_on_rescan():
    """
    Tests that the ON CONFLICT clause correctly resets the status and hash
    of a file that is scanned again.
    """
    file_path = 'C:\\RealFile.mkv'
    mock_rescan_data = [
        {"full_path": file_path, "file_size": 1001, "modified_date": 1, "is_symlink": False}
    ]

    with patch('config.DB_FILE_PATH', TEST_DB_FILE), \
         patch('file_scanner._iterate_everything_results', return_value=mock_rescan_data):
        try:
            if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
            initialize_database()
            with get_db_connection() as conn:
                # The initial INSERT now includes the 'physical_drive' column.
                conn.execute("""
                    INSERT INTO files (full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink, status, xxh128_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_path, 'C', 'RealFile.mkv', 'C:\\', 'downloads', 1000, 0, 0, 'processed', 'some_old_hash'))
                conn.commit()

            mock_dll = MagicMock()
            # This call now correctly passes the 4 required arguments.
            scan_directory(mock_dll, 'C:\\somepath', 'downloads', 'C')

            with get_db_connection() as conn:
                file_record = conn.execute("SELECT * FROM files WHERE full_path = ?", (file_path,)).fetchone()
                assert file_record['file_size'] == 1001
                assert file_record['status'] == 'new'
                assert file_record['xxh128_hash'] is None
        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)