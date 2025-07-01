# hashing2.py

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from tqdm import tqdm
import time

import config
from database import get_db_connection
from color_utils import get_hsl_color_for_bar

def _hash_file_worker(file_info):
    """Worker function to hash a single file."""
    file_id, file_path, file_size = file_info
    logging.debug(f"WORKER: Starting hash for file ID {file_id} at {file_path}")
    try:
        import xxhash
        h = xxhash.xxh128()
        with open(file_path, 'rb', buffering=262144) as f:
            while chunk := f.read(262144):
                h.update(chunk)
        result = {"id": file_id, "hash": h.hexdigest(), "size": file_size}
        logging.debug(f"WORKER: Finished hash for file ID {file_id}. Result: {result['hash']}")
        return result
    except Exception as e:
        logging.error(f"WORKER: Error hashing file {file_path}: {e}", exc_info=True)
        return None

def _process_drive_list(drive_info, bar_color: str):
    """This function runs in a master thread for a single drive."""
    drive_letter, drive_files = drive_info
    logging.debug(f"DRIVE PROCESSOR ({drive_letter}): Starting to process {len(drive_files)} files.")
    results = []
    
    total_size_bytes = sum(f[2] for f in drive_files)
    
    pbar = tqdm(total=total_size_bytes, desc=f"Hashing Drive {drive_letter}", unit='B', unit_scale=True, unit_divisor=1024)

    with pbar:
        for file_info in drive_files:
            logging.debug(f"DRIVE PROCESSOR ({drive_letter}): Calling worker for {file_info[1]}")
            res = _hash_file_worker(file_info)
            if res:
                results.append(res)
            pbar.update(file_info[2])
    
    logging.debug(f"DRIVE PROCESSOR ({drive_letter}): Finished. Returning {len(results)} results.")
    return results

def hash_unhashed_files_per_drive(sort_by='file_size', sort_order='ascending'):
    """Finds all unhashed files, groups them, and processes them in parallel."""
    logging.debug("HASH_MAIN: Starting.")
    
    try:
        with get_db_connection() as conn:
            order_direction = "ASC" if sort_order == 'ascending' else "DESC"
            sql_get_unhashed = f"SELECT id, full_path, physical_drive, file_size FROM files WHERE xxh128_hash IS NULL AND is_symlink = 0 ORDER BY {sort_by} {order_direction}"
            logging.debug(f"HASH_MAIN: Executing query to find unhashed files: {sql_get_unhashed}")
            files_to_hash = conn.execute(sql_get_unhashed).fetchall()
            logging.debug(f"HASH_MAIN: Found {len(files_to_hash)} files to hash from DB.")
    except Exception as e:
        logging.error(f"HASH_MAIN: Failed to get list of unhashed files: {e}", exc_info=True)
        return

    if not files_to_hash:
        logging.info("HASH_MAIN: No unhashed files found. Exiting.")
        return

    files_by_drive = defaultdict(list)
    for f in files_to_hash:
        drive = f['physical_drive']
        if drive:
            files_by_drive[drive].append((f['id'], f['full_path'], f['file_size']))

    num_drives = len(files_by_drive)
    max_drive_workers = min(num_drives, config.HASHING_WORKERS)
    logging.info(f"HASH_MAIN: Creating master worker pool with {max_drive_workers} workers for {num_drives} drives.")
    
    update_data = []
    with ThreadPoolExecutor(max_workers=max_drive_workers) as executor:
        logging.debug("HASH_MAIN: Submitting drive jobs to executor.")
        # The enumerate provides the index for the color calculation.
        future_to_drive = {
            executor.submit(_process_drive_list, item, get_hsl_color_for_bar(i, num_drives)): item[0] 
            for i, item in enumerate(sorted(files_by_drive.items()))
        }
        
        logging.debug(f"HASH_MAIN: Waiting for {len(future_to_drive)} futures to complete.")
        for future in as_completed(future_to_drive):
            drive = future_to_drive[future]
            logging.debug(f"HASH_MAIN: Future for drive {drive} completed.")
            try:
                drive_results = future.result()
                if drive_results:
                    logging.debug(f"HASH_MAIN: Got {len(drive_results)} results from drive {drive}.")
                    fixed_results = [(res['hash'], res['id']) for res in drive_results]
                    update_data.extend(fixed_results)
            except Exception as exc:
                logging.error(f"HASH_MAIN: Drive {drive} generated an exception in its future: {exc}", exc_info=True)

    logging.info(f"HASH_MAIN: All drive futures completed. Total results: {len(update_data)}")
    
    if not update_data:
        logging.warning("Hashing completed, but no new hashes were generated.")
        return

    logging.info(f"Updating database with {len(update_data)} new file hashes...")
    update_sql = "UPDATE files SET xxh128_hash = ?, status = 'hashed', hash_date = unixepoch() WHERE id = ?"
    
    try:
        with get_db_connection() as conn:
            conn.executemany(update_sql, update_data)
            conn.commit()
        logging.info("Database successfully updated with new hashes.")
    except Exception as e:
        logging.error(f"Failed to update database with hashes: {e}")