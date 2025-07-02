# main.py

import logging
import argparse
import signal
import sys

import logger_setup
from database import initialize_database, get_db_connection
from file_scanner import run_file_scan
from hashing import hash_unhashed_files_per_drive
from qbittorrent_api import update_db_with_torrent_info
from duplicate_finder import identify_and_link_duplicates
from symlink_processor import process_duplicates, cleanup_backup_files
from db_inspector import inspect_database_state
import config

def signal_handler(sig, frame):
    """
    This function will be called when Ctrl+C is pressed.
    It sets the global shutdown event.
    """
    if not config.SHUTDOWN_EVENT.is_set():
        print()
        logging.warning("Ctrl+C detected! Initiating graceful shutdown. Please wait, progress will be saved...")
        config.SHUTDOWN_EVENT.set()
    else:
        logging.warning("Multiple Ctrl+C detected. Forcing exit.")
        sys.exit(1)

# --- THIS IS THE MISSING FUNCTION ---
def get_counts():
    """Gets current counts of file statuses from the DB for reporting."""
    with get_db_connection() as conn:
        counts = {
            'new': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'new'").fetchone()[0],
            'hashed': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'hashed'").fetchone()[0],
            'duplicate_found': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'duplicate_found'").fetchone()[0],
            'processed': conn.execute("SELECT COUNT(*) FROM files WHERE status = 'processed'").fetchone()[0],
            'error': conn.execute("SELECT COUNT(*) FROM files WHERE status LIKE 'error%'").fetchone()[0],
        }
        return counts

def main(args):
    """Main application logic."""
    logger_setup.setup_logging(args.verbose)
    
    sort_by = 'file_size'
    sort_order = 'ascending'
    if args.order_by:
        parts = args.order_by.lower().split(',')
        if len(parts) == 2:
            col, order = parts
            if col in ['size', 'name', 'date']:
                sort_by = {'size': 'file_size', 'name': 'full_path', 'date': 'modified_date'}[col]
            if order in ['ascending', 'asc', 'descending', 'desc']:
                sort_order = 'ascending' if order in ['ascending', 'asc'] else 'descending'
        else:
            logging.warning(f"Invalid --order-by format '{args.order_by}'. Using default 'size,ascending'.")

    if args.step == 'full' or args.step == 'scan':
        logging.info("--- Step 1: Initializing Database ---")
        initialize_database()
        
        logging.info("--- Step 2: Scanning Files ---")
        run_file_scan()
        
        inspect_database_state("File Scan")
        
        logging.info("--- Step 3: Hashing Files ---")
        hash_unhashed_files_per_drive(sort_by=sort_by, sort_order=sort_order)
        
        if config.SHUTDOWN_EVENT.is_set():
            logging.warning("Shutdown complete. Exiting application.")
            return

        logging.info("--- Step 4: Syncing with qBittorrent ---")
        update_db_with_torrent_info()
    
    if args.step == 'full' or args.step == 'process':
        logging.info("--- Step 5: Identifying Duplicates ---")
        num_found = identify_and_link_duplicates()
        
        # This call will now work correctly.
        counts = get_counts()
        
        logging.info("--- DRY RUN REPORT ---")
        logging.info(f"Found {num_found} new duplicates.")
        logging.info(f"Total files pending processing: {counts['duplicate_found']}")
        
        if counts['duplicate_found'] > 0 and not args.yes:
            confirm = input("Proceed with symlinking process? (y/n): ").lower()
            if confirm != 'y':
                logging.warning("Processing aborted by user.")
                return
        elif counts['duplicate_found'] == 0:
            logging.info("No duplicates to process.")
            # We add a return here to prevent the script from continuing if there's nothing to do.
            return

        logging.info("--- Step 6: Processing Duplicates ---")
        process_duplicates()
        
    if args.cleanup:
        logging.info("--- Step 7: Cleanup Backup Files ---")
        cleanup_backup_files()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="Find and symlink duplicate media files.")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Increase logging verbosity.")
    parser.add_argument('-o', '--order-by', type=str, default='size,ascending', help="Order of files to process. Format: 'column,direction'. Column can be 'size', 'name', or 'date'. Direction can be 'ascending'/'asc' or 'descending'/'desc'.")
    parser.add_argument('--step', choices=['full', 'scan', 'process'], default='full', help="Run a specific part of the process.")
    parser.add_argument('--cleanup', action='store_true', help="Run the backup file cleanup process.")
    parser.add_argument('-y', '--yes', action='store_true', help="Automatically answer yes to confirmation prompts.")
    
    args = parser.parse_args()
    main(args)