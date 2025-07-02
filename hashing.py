# hashing.py

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from tqdm import tqdm

import config
from database import get_db_connection
from color_utils import get_hsl_color_for_bar

def _hash_file_worker(file_info):
    """Worker function to hash a single file. Now checks for shutdown."""
    if config.SHUTDOWN_EVENT.is_set():
        return None
    file_id, file_path, file_size = file_info
    try:
        import xxhash
        h = xxhash.xxh128()
        with open(file_path, 'rb', buffering=262144) as f:
            while chunk := f.read(262144):
                if config.SHUTDOWN_EVENT.is_set():
                    logging.debug(f"Shutdown requested during hashing of {file_path}.")
                    return None
                h.update(chunk)
        return {"id": file_id, "hash": h.hexdigest(), "size": file_size}
    except FileNotFoundError:
        logging.debug(f"File not found during hashing: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Could not hash file {file_path}: {e}")
        return None

def _process_drive_list(drive_info, bar_color: str):
    # This function is also likely correct, but we add logging.
    drive_letter, drive_files = drive_info
    logging.debug(f"PROCESSOR({drive_letter}): Starting with {len(drive_files)} files.")
    results = []
    
    total_size_bytes = sum(f[2] for f in drive_files)
    pbar = tqdm(total=total_size_bytes, desc=f"Hashing Drive {drive_letter}", unit='B', unit_scale=True, unit_divisor=1024, colour=bar_color)

    with pbar:
        for file_info in drive_files:
            if config.SHUTDOWN_EVENT.is_set():
                logging.warning(f"Shutdown detected, stopping hashing for drive {drive_letter}.")
                break # Exit the loop for this drive
            
            res = _hash_file_worker(file_info)
            if res:
                results.append(res)
            pbar.update(file_info[2])
            
    logging.debug(f"PROCESSOR({drive_letter}): Finished, returning {len(results)} results.")
    return results

def hash_unhashed_files_per_drive(sort_by='file_size', sort_order='ascending'):
    """The main orchestrator function with all features."""
    logging.info(f"Starting per-disk hashing process, ordering by {sort_by} {sort_order}.")
    
    try:
        with get_db_connection() as conn:
            order_direction = "ASC" if sort_order == 'ascending' else "DESC"
            sql_get_unhashed = f"""
                SELECT id, full_path, physical_drive, file_size FROM files 
                WHERE xxh128_hash IS NULL AND is_symlink = 0 ORDER BY {sort_by} {order_direction}
            """
            files_to_hash = conn.execute(sql_get_unhashed).fetchall()
            logging.debug(f"MAIN_HASHER: Found {len(files_to_hash)} files to hash from DB.")
    except Exception as e:
        logging.error(f"MAIN_HASHER: DB query failed: {e}", exc_info=True)
        logging.error(f"Failed to get list of unhashed files: {e}", exc_info=True)
        return

    if not files_to_hash:
        logging.info("MAIN_HASHER: No unhashed files found.")
        return

    files_by_drive = defaultdict(list)
    for f in files_to_hash:
        drive = f['physical_drive']
        if drive:
            files_by_drive[drive].append((f['id'], f['full_path'], f['file_size']))

    num_drives = len(files_by_drive)
    logging.info(f"Files are spread across {num_drives} physical drives: {list(files_by_drive.keys())}")

    update_data = []
    max_drive_workers = min(num_drives, config.HASHING_WORKERS)
    
    with ThreadPoolExecutor(max_workers=max_drive_workers) as executor:
        drive_jobs = []
        sorted_drives = sorted(files_by_drive.items())
        
        for i, (drive_letter, files) in enumerate(sorted_drives):
            color = get_hsl_color_for_bar(i, num_drives)
            drive_jobs.append({'drive_info': (drive_letter, files), 'bar_color': color})

        future_to_drive = {
            executor.submit(_process_drive_list, **job): job['drive_info'][0] 
            for job in drive_jobs
        }
        
        logging.info(f"Hashing started for {num_drives} drives. Press Ctrl+C to gracefully shut down and save progress.")
        try:
            # This loop waits for futures to complete.
            for future in as_completed(future_to_drive):
                # If a shutdown is requested while waiting, break the loop.
                if config.SHUTDOWN_EVENT.is_set():
                    break
                drive = future_to_drive[future]
                try:
                    drive_results = future.result()
                    if drive_results:
                        fixed_results = [(res['hash'], res['id']) for res in drive_results]
                        update_data.extend(fixed_results)
                    logging.info(f"Finished processing drive {drive}.")
                except Exception as exc:
                    logging.error(f"Drive {drive} generated an exception: {exc}", exc_info=True)
        
        except KeyboardInterrupt:
            # This is the primary catch for Ctrl+C
            config.SHUTDOWN_EVENT.set()
            logging.warning("Ctrl+C detected! Cancelling pending tasks...")
            # Actively cancel futures that have not started running yet.
            for future in future_to_drive:
                future.cancel()

    if config.SHUTDOWN_EVENT.is_set():
        logging.warning("Shutdown complete. Saving partial progress...")
    
    if not update_data:
        logging.info("No new hashes were generated in this run.")
        return

    logging.info(f"Updating database with {len(update_data)} new file hashes...")
    update_sql = "UPDATE files SET xxh128_hash = ?, status = 'hashed', hash_date = unixepoch() WHERE id = ?"
    
    try:
        with get_db_connection() as conn:
            conn.executemany(update_sql, update_data)
            conn.commit()
        logging.info("Database successfully updated.")
    except Exception as e:
        logging.error(f"Failed to update database with hashes: {e}", exc_info=True)