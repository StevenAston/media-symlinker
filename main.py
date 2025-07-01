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

def main(args):
    """Main application logic."""
    logger_setup.setup_logging(args.verbose)
    
    # Parse the --order-by argument ---
    sort_by = 'file_size' # Default sort column
    sort_order = 'ascending' # Default sort order
    if args.order_by:
        parts = args.order_by.lower().split(',')
        if len(parts) == 2:
            col, order = parts
            # Validate the user input
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
        # --- MODIFIED: Pass the sorting options to the hashing function ---
        hash_unhashed_files_per_drive(sort_by=sort_by, sort_order=sort_order)
        
        logging.info("--- Step 4: Syncing with qBittorrent ---")
        update_db_with_torrent_info()
<<<<<<< Updated upstream
    
def signal_handler(sig, frame):
    """
    This function will be called when Ctrl+C is pressed.
    It sets the global shutdown event in the hashing module.
    """
    from hashing import SHUTDOWN_EVENT
    if not SHUTDOWN_EVENT.is_set():
        print() # Print a newline to not overwrite the current progress bar
        logging.warning("Ctrl+C detected! Initiating graceful shutdown. Please wait...")
        SHUTDOWN_EVENT.set()
    else:
        logging.warning("Multiple Ctrl+C detected. Forcing exit.")
        sys.exit(1)
=======
>>>>>>> Stashed changes

if __name__ == '__main__':
    # Shutdown signal handler
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="Find and symlink duplicate media files.")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Increase logging verbosity.")
    
    parser.add_argument(
        '-o', '--order-by',
        type=str,
        default='size,ascending',
        help="Order of files to process. Format: 'column,direction'. "
             "Column can be 'size', 'name', or 'date'. "
             "Direction can be 'ascending'/'asc' or 'descending'/'desc'."
    )
    
    parser.add_argument('--step', choices=['full', 'scan', 'process'], default='full', help="Run a specific part of the process.")
    parser.add_argument('--cleanup', action='store_true', help="Run the backup file cleanup process.")
    parser.add_argument('-y', '--yes', action='store_true', help="Automatically answer yes to confirmation prompts.")
    
    args = parser.parse_args()
    main(args)