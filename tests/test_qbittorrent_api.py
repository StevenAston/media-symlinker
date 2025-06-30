# tests/test_qbittorrent_api.py

import os
import gc
from unittest.mock import patch, MagicMock

import config
from database import get_db_connection, initialize_database
from qbittorrent_api import update_db_with_torrent_info

TEST_DB_FILE = "test_qbit.sqlite"

def setup_test_db_with_mock_files():
    """Helper function to create and populate a test database with file records."""
    initialize_database()
    with get_db_connection() as conn:
        # Use os.path.join for consistency
        full_path = os.path.join(config.DOWNLOADS_PATH, "Some.Movie.2023.1080p.mkv")
        conn.execute("""
            INSERT INTO files (full_path, filename, directory, scan_source, file_size, modified_date, is_symlink)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (full_path, 'Some.Movie.2023.1080p.mkv', config.DOWNLOADS_PATH, 'downloads', 12345, 0, 0))
        conn.commit()

def test_update_db_with_torrent_info():
    """
    Tests that torrent info is correctly fetched from a mock client
    and used to update the database.
    """
    mock_client = MagicMock()
    
    mock_torrent = MagicMock()
    mock_torrent.hash = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'
    mock_torrent.name = 'Some.Movie.2023'
    # --- THE FIX ---
    # Do not add a trailing slash. Let os.path.join handle it.
    mock_torrent.save_path = config.DOWNLOADS_PATH
    mock_torrent.category = 'movies'
    mock_torrent.tags = ['1080p', 'x265']
    
    mock_torrent_file = MagicMock()
    # Use forward slashes here to accurately simulate the API response
    mock_torrent_file.name = "Some.Movie.2023.1080p.mkv"
    
    mock_client.torrents_info.return_value = [mock_torrent]
    mock_client.torrents_files.return_value = [mock_torrent_file]
    
    with patch('config.DB_FILE_PATH', TEST_DB_FILE), \
         patch('qbittorrent_api.Client', return_value=mock_client):
        try:
            setup_test_db_with_mock_files()
            update_db_with_torrent_info()

            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Query by the known path to be certain
                path_to_check = os.path.join(config.DOWNLOADS_PATH, "Some.Movie.2023.1080p.mkv")
                result = conn.execute("SELECT * FROM files WHERE full_path = ?", (path_to_check,)).fetchone()
                
                assert 'torrent_hash' in result.keys()
                assert result['torrent_hash'] == mock_torrent.hash
                assert result['torrent_name'] == mock_torrent.name
                assert result['category'] == 'movies'
                assert result['tags'] == '1080p,x265'

        finally:
            gc.collect()
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)