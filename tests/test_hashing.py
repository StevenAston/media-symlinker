# tests/test_hashing.py

import os
import gc
import pytest
from unittest.mock import patch, MagicMock

import config
from database import get_db_connection, initialize_database
# We import all the functions we want to test or mock
from hashing import hash_unhashed_files_per_drive, _process_drive_list, _hash_file_worker

TEST_DB_FILE = "test_hashing_final.sqlite"

# --- Test 1: Test the innermost worker function in isolation ---
def test_hash_file_worker_correctly_hashes():
    """Tests that the _hash_file_worker correctly hashes content."""
    mock_content = b'this is the test content'
    # This is the known, correct hash for the string above.
    expected_hash = 'a9743c380ea0f5ad410955782a16010e'
    
    # Create a temporary file to be hashed
    temp_file_path = "temp_test_file.tmp"
    try:
        with open(temp_file_path, "wb") as f:
            f.write(mock_content)
        
        # The worker takes a tuple: (id, path, size)
        result = _hash_file_worker((1, temp_file_path, len(mock_content)))
        
        assert result is not None, "Worker should return a result"
        assert result['id'] == 1
        assert result['hash'] == expected_hash, "The generated hash is incorrect"

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- Test 2: Test the drive processor function in isolation ---
@patch('hashing._hash_file_worker')
def test_process_drive_list(mock_hash_worker):
    """Tests that the drive processor calls the hash worker for the correct files."""
    # Configure the mock to return a predictable result for any file
    mock_hash_worker.return_value = {"id": 1, "hash": "mock_hash", "size": 1000}
    
    # This is the list of files for a single drive
    drive_files = [
        (1, 'D:\\file1.mkv', 1000),
        (2, 'D:\\file2.mkv', 2000),
    ]
    drive_info = ('D', drive_files)
    
    # Run the drive processor
    results = _process_drive_list(drive_info, "#ffffff")
    
    # Assertions
    assert len(results) == 2, "Should have processed both files"
    assert mock_hash_worker.call_count == 2, "Hash worker should be called for each file"
    assert results[0]['hash'] == 'mock_hash'

# --- Test 3: The main integration test ---
# This test verifies that the main function calls the drive processor correctly.
@patch('hashing._process_drive_list')
def test_main_hashing_orchestrator(mock_process_drive_list):
    """
    This test validates the main orchestrator function.
    """
    mock_process_drive_list.return_value = [
        {"id": 1, "hash": "a_correct_hash", "size": 1000}
    ]

    try:
        # --- SETUP ---
        if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
        
        with patch('config.DB_FILE_PATH', TEST_DB_FILE):
            initialize_database()
            with get_db_connection() as conn:
                # Insert one file that needs hashing
                conn.execute("INSERT INTO files (id, full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (1, 'D:\\tobehashed.mkv', 'D', 'f', 'd', 's', 1000, 0, 0))
                conn.commit()

            # --- EXECUTION ---
            with patch('hashing.get_hsl_color_for_bar', return_value="#ffffff"):
                hash_unhashed_files_per_drive()

        # --- VERIFICATION ---
        mock_process_drive_list.assert_called_once()
        
        with patch('config.DB_FILE_PATH', TEST_DB_FILE):
            with get_db_connection() as conn:
                file1 = conn.execute("SELECT * FROM files WHERE id = 1").fetchone()
                assert file1['status'] == 'hashed'
                assert file1['xxh128_hash'] == 'a_correct_hash'

    finally:
        # --- TEARDOWN ---
        gc.collect()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)