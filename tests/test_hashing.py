# tests/test_hashing.py

import os
import gc
from unittest.mock import patch, MagicMock

import config
from database import get_db_connection, initialize_database
# We import the main function and the worker function we want to mock
from hashing import hash_unhashed_files_per_drive, _process_drive_list

TEST_DB_FILE = "test_hashing_final.sqlite"

<<<<<<< Updated upstream
@patch('hashing.as_completed')
@patch('hashing.ThreadPoolExecutor')
def test_main_hashing_function(mock_ThreadPoolExecutor, mock_as_completed):
    """
    This test validates the main orchestrator function by mocking the execution flow.
    """
    # 1. Mock the executor instance
    mock_executor_instance = mock_ThreadPoolExecutor.return_value

    # 2. Simulate the `submit` call. We don't need it to do anything complex,
    #    just to return a mock future object that we can identify.
    mock_future = MagicMock()
    mock_executor_instance.submit.return_value = mock_future
    
    # 3. THE CRITICAL FIX: Configure the mock for `as_completed`.
    #    When the application calls `as_completed`, we will return a list
    #    containing our single mock_future. This ensures the loop runs once
    #    with the exact object we can track.
    mock_as_completed.return_value = [mock_future]

    # 4. We now need to patch the dictionary *before* the function call,
    #    so we will control the `future_to_drive` dictionary directly.
    #    We also patch the result of our mock future.
    with patch.dict('hashing.future_to_drive', {mock_future: 'D'}), \
         patch.object(mock_future, 'result', return_value=[{"id": 1, "hash": "a_correct_hash", "size": 1000}]):

        with patch('config.DB_FILE_PATH', TEST_DB_FILE):
            try:
                # Setup
                if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
                initialize_database()
                with get_db_connection() as conn:
                     conn.execute("INSERT INTO files (id, full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (1, 'D:\\tobehashed.mkv', 'D', 'f', 'd', 's', 1000, 0, 0))
                     conn.commit()

                # Execution
                with patch('hashing.get_hsl_color_for_bar', return_value="#ffffff"):
                    hash_unhashed_files_per_drive()

                # Verification
                with get_db_connection() as conn:
                    file1 = conn.execute("SELECT * FROM files WHERE id = 1").fetchone()
                    assert file1['status'] == 'hashed'
                    assert file1['xxh128_hash'] == 'a_correct_hash'

            finally:
                gc.collect()
                if os.path.exists(TEST_DB_FILE):
                    os.remove(TEST_DB_FILE)
=======
# This test now correctly patches the worker function that is submitted to the executor.
# This is the most stable and direct way to test the main function's logic.
@patch('hashing._process_drive_list')
def test_main_hashing_orchestrator(mock_process_drive_list):
    """
    Tests that the main hash_unhashed_files_per_drive function correctly:
    1. Queries the database for the right files.
    2. Groups them by drive.
    3. Submits them to the drive processor.
    4. Updates the database with the results returned by the processor.
    """
    # 1. Configure the mock to return predictable data.
    # This simulates that the worker for drive 'D' found one file and hashed it.
    mock_process_drive_list.return_value = [
        {"id": 1, "hash": "a_correct_hash", "size": 1000}
    ]

    try:
        # --- SETUP ---
        if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
        
        with patch('config.DB_FILE_PATH', TEST_DB_FILE):
            initialize_database()
            with get_db_connection() as conn:
                # Insert one file that needs hashing and one that does not.
                conn.execute("INSERT INTO files (id, full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (1, 'D:\\tobehashed.mkv', 'D', 'f', 'd', 's', 1000, 0, 0))
                conn.execute("INSERT INTO files (id, full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink, xxh128_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (2, 'E:\\alreadyhashed.mkv', 'E', 'f', 'd', 's', 2000, 0, 0, 'old_hash', 'hashed'))
                conn.commit()

            # --- EXECUTION ---
            # We patch the color helper because it's not relevant to this test.
            with patch('hashing.get_hsl_color_for_bar', return_value="#ffffff"):
                hash_unhashed_files_per_drive()

        # --- VERIFICATION ---
        # a) Check that our mock drive processor was called.
        # The main function should have found only the one un-hashed file on drive D.
        mock_process_drive_list.assert_called_once()
        
        # b) Check that the database was updated with the results from our mock.
        with patch('config.DB_FILE_PATH', TEST_DB_FILE):
             with get_db_connection() as conn:
                file1 = conn.execute("SELECT * FROM files WHERE id = 1").fetchone()
                assert file1['status'] == 'hashed', "The status should have been updated."
                assert file1['xxh128_hash'] == 'a_correct_hash', "The hash should have been updated."

                # c) Check that the other file was untouched.
                file2 = conn.execute("SELECT * FROM files WHERE id = 2").fetchone()
                assert file2['xxh128_hash'] == 'old_hash', "The pre-hashed file's hash should not change."

    finally:
        # --- TEARDOWN ---
        gc.collect()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
>>>>>>> Stashed changes
