# database.py

import sqlite3
import logging
import config
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """Establishes and yields a connection to the SQLite database."""
    conn = None
    try:
        logging.debug(f"Attempting to connect to database at: {config.DB_FILE_PATH}")
        conn = sqlite3.connect(config.DB_FILE_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logging.error(f"Database connection failed: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()

def initialize_database():
    # ...
    create_files_table_sql = """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_path TEXT UNIQUE NOT NULL,
        physical_drive TEXT, -- REQUIRED for per-disk hashing
        filename TEXT NOT NULL,
        directory TEXT NOT NULL,
        scan_source TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        modified_date REAL NOT NULL,
        is_symlink INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'new',
        xxh128_hash TEXT,
        hash_date REAL,
        duplicate_of_id INTEGER,
        torrent_hash TEXT,
        torrent_name TEXT,
        category TEXT,
        tags TEXT,
        FOREIGN KEY (duplicate_of_id) REFERENCES files (id)
    );
    """
    create_path_index_sql = "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_full_path ON files (full_path);"
    create_hash_index_sql = "CREATE INDEX IF NOT EXISTS idx_files_xxh128_hash ON files (xxh128_hash);"
    create_size_index_sql = "CREATE INDEX IF NOT EXISTS idx_files_file_size ON files (file_size);"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            logging.debug("Creating 'files' table with full schema if it doesn't exist.")
            cursor.execute(create_files_table_sql)
            
            logging.debug("Creating database indexes.")
            cursor.execute(create_path_index_sql)
            cursor.execute(create_hash_index_sql)
            cursor.execute(create_size_index_sql)
            
            conn.commit()
            logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {e}", exc_info=True)
        raise