# main.py

import logging
import argparse

import logger_setup
from database import initialize_database, get_db_connection
from file_scanner import run_file_scan
from hashing import hash_all_unhashed_files
from qbittorrent_api import update_db_with_torrent_info
from duplicate_finder import identify_and_link_duplicates
from symlink_processor import process_duplicates, cleanup_backup_files
from db_inspector import inspect_database_state # <-- IMPORT THE NEW MODULE

def get_counts():
    # ... (this function remains the same)
    with get_db_connection() as conn:
        counts = {'new': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'new'").fetchone()[0], 'hashed': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'hashed'").fetchone()[0], 'duplicate_found': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'duplicate_found'").fetchone()[0], 'processed': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'processed'").fetchone()[0], 'error': conn.execute("SELECT COUNT(*) FROM files WHERE status LIKE 'error%'").fetchone()[0],}
        return counts

def main(args):
    """Main application logic."""
    # logger_setup.setup_logging()
    
    if args.step == 'full' or args.step == 'scan':
        logging.info("--- Step 1: Initializing Database ---")
        initialize_database()
        logging.info("--- Step 2: Scanning Files ---")
        run_file_scan()

        # --- THE DIAGNOSTIC STEP ---
        inspect_database_state("File Scan")

        logging.info("--- Step 3: Hashing Files ---")
        hash_all_unhashed_files()
        logging.info("--- Step 4: Syncing with qBittorrent ---")
        update_db_with_torrent_info()
    
    # ... (the rest of the file remains the same)
    if args.step == 'full' or args.step == 'process':
        logging.info("--- Step 5: Identifying Duplicates ---")
        num_found = identify_and_link_duplicates()
        counts = get_counts()
        logging.info(f"--- DRY RUN REPORT ---")
        logging.info(f"Found {num_found} new duplicates.")
        logging.info(f"Total files pending processing: {counts['duplicate_found']}")
        if counts['duplicate_found'] > 0 and not args.yes:
            confirm = input("Proceed with symlinking process? (y/n): ").lower()
            if confirm != 'y': logging.warning("Processing aborted by user."); return
        elif counts['duplicate_found'] == 0: logging.info("No duplicates to process."); return
        logging.info("--- Step 6: Processing Duplicates ---")
        process_duplicates()
    if args.cleanup:
        logging.info("--- Step 7: Cleanup Backup Files ---")
        cleanup_backup_files()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Find and symlink duplicate media files.")
    parser.add_argument('--step', choices=['full', 'scan', 'process'], default='full', help="Run a specific part of the process.")
    parser.add_argument('--cleanup', action='store_true', help="Run the backup file cleanup process.")
    parser.add_argument('-y', '--yes', action='store_true', help="Automatically answer yes to confirmation prompts.")
    # --- ADD THIS ARGUMENT ---
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable verbose DEBUG level logging to console.")
    
    args = parser.parse_args()
    
    # --- ADD THIS LOGIC ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger_setup.setup_logging(level=log_level)
    
    main(args)