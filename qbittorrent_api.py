# qbittorrent_api.py

import logging
import os
from qbittorrentapi import Client, LoginFailed

import config
from database import get_db_connection

def get_qbit_client():
    """Creates and returns a qBittorrent client instance."""
    try:
        client = Client(host=config.QBITTORRENT_HOST, port=config.QBITTORRENT_PORT, username=config.QBITTORRENT_USERNAME, password=config.QBITTORRENT_PASSWORD)
        logging.info("Connecting to qBittorrent...")
        client.auth_log_in()
        logging.info(f"Successfully connected to qBittorrent v{client.app.version}")
        return client
    except Exception as e:
        logging.error(f"Failed to connect to qBittorrent: {e}")
        return None

def update_db_with_torrent_info():
    """Fetches all torrents and files from qBittorrent and updates the database."""
    client = get_qbit_client()
    if not client: return

    logging.info("Fetching torrent list from qBittorrent...")
    # _add_torrent_columns_to_db()

    logging.info("Resetting existing torrent information in the database...")
    with get_db_connection() as conn:
        conn.execute("UPDATE files SET torrent_hash=NULL, torrent_name=NULL, category=NULL, tags=NULL WHERE torrent_hash IS NOT NULL")
        conn.commit()

    torrents_to_update = []
    try:
        for torrent in client.torrents_info():
            for file_info in client.torrents_files(torrent_hash=torrent.hash):
                # --- THE DEFINITIVE PATH FIX ---
                # 1. The `file_info.name` from the API uses forward slashes. Normalize them to the OS's native separator.
                relative_path = file_info.name.replace('/', os.sep)
                # 2. Join the torrent's save path with the normalized relative path.
                full_path = os.path.join(torrent.save_path, relative_path)
                # --- END OF FIX ---
                torrents_to_update.append((torrent.hash, torrent.name, torrent.category, ",".join(tag for tag in torrent.tags), full_path))
    except Exception as e:
        logging.error(f"An error occurred while fetching torrent data: {e}")
    finally:
        try: client.auth_log_out(); logging.info("qBittorrent connection closed.")
        except Exception: pass

    if not torrents_to_update: logging.warning("No torrent file information to update."); return

    logging.info(f"Updating {len(torrents_to_update)} file records with torrent info...")
    update_sql = "UPDATE files SET torrent_hash = ?, torrent_name = ?, category = ?, tags = ? WHERE full_path = ?"
    try:
        with get_db_connection() as conn:
            conn.executemany(update_sql, torrents_to_update)
            conn.commit()
        logging.info("Database successfully updated with torrent information.")
    except Exception as e:
        logging.error(f"Failed to update database with torrent info: {e}")

def _add_torrent_columns_to_db():
    """Adds new columns to the 'files' table to store torrent-specific data."""
    logging.debug("Verifying database schema for torrent information...")
    cols_to_add = {"torrent_hash": "TEXT", "torrent_name": "TEXT", "category": "TEXT", "tags": "TEXT"}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(files);")
        existing_cols = [row['name'] for row in cursor.fetchall()]
        for col_name, col_type in cols_to_add.items():
            if col_name not in existing_cols:
                logging.info(f"Adding column '{col_name}' to 'files' table.")
                cursor.execute(f"ALTER TABLE files ADD COLUMN {col_name} {col_type}")
        conn.commit()