# symlink_processor.py

import logging
import os
import time
from collections import defaultdict
from tqdm import tqdm

import config
from database import get_db_connection
from qbittorrent_api import get_qbit_client

def _get_files_to_process():
    """Fetches all files marked as 'duplicate_found' from the database."""
    sql = """
    SELECT
        d.id as download_file_id,
        d.full_path as download_path,
        d.torrent_hash,
        m.full_path as media_path
    FROM
        files d
    JOIN
        files m ON d.duplicate_of_id = m.id
    WHERE
        d.status = 'duplicate_found' AND d.torrent_hash IS NOT NULL;
    """
    with get_db_connection() as conn:
        return conn.execute(sql).fetchall()

def _update_file_status(file_id, status, error_msg=None):
    """Updates the status of a file in the database."""
    # We could expand this to log errors to a new column if needed
    sql = "UPDATE files SET status = ? WHERE id = ?"
    with get_db_connection() as conn:
        conn.execute(sql, (status, file_id))
        conn.commit()

def process_duplicates():
    """
    Main function to process all identified duplicates.
    It stops torrents, renames files, creates symlinks, and rechecks.
    """
    files_to_process = _get_files_to_process()
    if not files_to_process:
        logging.info("No duplicate files are pending processing.")
        return

    # Group files by torrent hash to process them in batches
    torrents_to_process = defaultdict(list)
    for f in files_to_process:
        torrents_to_process[f['torrent_hash']].append(f)

    logging.info(f"Processing {len(files_to_process)} files across {len(torrents_to_process)} torrents.")
    
    client = get_qbit_client()
    if not client:
        logging.error("Cannot process symlinks, qBittorrent connection failed.")
        return

    # Use tqdm to show progress for torrents
    pbar = tqdm(torrents_to_process.items(), desc="Processing Torrents", unit="torrent")
    for torrent_hash, files in pbar:
        try:
            torrent_name = files[0]['download_path'] # Get a name for display
            pbar.set_postfix_str(os.path.basename(torrent_name), refresh=True)

            logging.info(f"Pausing torrent: {torrent_hash}")
            client.torrents_pause(torrent_hashes=torrent_hash)

            all_files_in_torrent_processed = True
            for file_data in files:
                download_path = file_data['download_path']
                media_path = file_data['media_path']
                file_id = file_data['download_file_id']
                
                # 1. Rename original to .bak
                backup_path = download_path + config.BACKUP_SUFFIX
                logging.info(f"Renaming '{download_path}' to '{backup_path}'")
                try:
                    os.rename(download_path, backup_path)
                except Exception as e:
                    logging.error(f"Failed to rename {download_path}: {e}")
                    _update_file_status(file_id, 'error_rename')
                    all_files_in_torrent_processed = False
                    continue
                
                # 2. Create symlink
                logging.info(f"Creating symlink from '{download_path}' to '{media_path}'")
                try:
                    os.symlink(media_path, download_path)
                except Exception as e:
                    logging.error(f"Failed to create symlink at {download_path}: {e}")
                    _update_file_status(file_id, 'error_symlink')
                    # Attempt to restore the backup file
                    os.rename(backup_path, download_path)
                    all_files_in_torrent_processed = False
                    continue
                
                # 3. Mark as processed in DB
                _update_file_status(file_id, 'processed')

            if all_files_in_torrent_processed:
                logging.info(f"Rechecking torrent: {torrent_hash}")
                client.torrents_recheck(torrent_hashes=torrent_hash)
            
            logging.info(f"Resuming torrent: {torrent_hash}")
            client.torrents_resume(torrent_hashes=torrent_hash)

        except Exception as e:
            logging.error(f"An unexpected error occurred processing torrent {torrent_hash}: {e}")
            # Mark all files in this batch as errored
            for file_data in files:
                _update_file_status(file_data['download_file_id'], 'error_unknown')
    
    try:
        client.auth_log_out()
    except Exception: pass

def cleanup_backup_files():
    """Finds and deletes all .bak files created by the script."""
    sql = "SELECT full_path FROM files WHERE status = 'processed'"
    with get_db_connection() as conn:
        processed_files = conn.execute(sql).fetchall()

    if not processed_files:
        logging.info("No backup files found to clean up.")
        return
        
    logging.info(f"Found {len(processed_files)} processed files. Checking for .bak files...")
    
    files_to_delete = []
    for row in processed_files:
        bak_path = row['full_path'] + config.BACKUP_SUFFIX
        if os.path.exists(bak_path):
            files_to_delete.append(bak_path)
            
    if not files_to_delete:
        logging.info("No .bak files found to delete.")
        return

    print(f"--- WARNING ---")
    print(f"You are about to permanently delete {len(files_to_delete)} .bak files.")
    confirm = input("Are you sure you want to continue? (y/n): ").lower()
    
    if confirm == 'y':
        logging.info(f"User confirmed. Deleting {len(files_to_delete)} backup files...")
        for f in tqdm(files_to_delete, desc="Deleting .bak files"):
            try:
                os.remove(f)
            except Exception as e:
                logging.error(f"Failed to delete {f}: {e}")
        logging.info("Backup file cleanup complete.")
    else:
        logging.info("Cleanup aborted by user.")