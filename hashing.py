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
    # This function is not the problem, but we'll keep it simple.
    file_id, file_path, file_size = file_info
    try:
        import xxhash
        h = xxhash.xxh128()
        with open(file_path, 'rb', buffering=262144) as f:
            while chunk := f.read(262144):
                h.update(chunk)
        return {"id": file_id, "hash": h.hexdigest(), "size": file_size}
    except Exception as e:
        logging.error(f"WORKER ERROR for {file_path}: {e}")
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
            if config.SHUTDOWN_EVENT.is_set(): break
            res = _hash_file_worker(file_info)
            if res:
                results.append(res)
            pbar.update(file_info[2])
            
    logging.debug(f"PROCESSOR({drive_letter}): Finished, returning {len(results)} results.")
    return results

def hash_unhashed_files_per_drive(sort_by='file_size', sort_order='ascending'):
    logging.debug("MAIN_HASHER: Starting.")
    
    try:
        with get_db_connection() as conn:
            order_direction = "ASC" if sort_order == 'ascending' else "DESC"
            sql = f"SELECT id, full_path, physical_drive, file_size FROM files WHERE xxh128_hash IS NULL AND is_symlink = 0 ORDER BY {sort_by} {order_direction}"
            files_to_hash = conn.execute(sql).fetchall()
            logging.debug(f"MAIN_HASHER: Found {len(files_to_hash)} files to hash from DB.")
    except Exception as e:
        logging.error(f"MAIN_HASHER: DB query failed: {e}", exc_info=True)
        return

    if not files_to_hash:
        logging.info("MAIN_HASHER: No unhashed files found.")
        return

    files_by_drive = defaultdict(list)
    for f in files_to_hash:
        files_by_drive[f['physical_drive']].append((f['id'], f['full_path'], f['file_size']))
    logging.debug(f"MAIN_HASHER: Grouped files into {len(files_by_drive)} drives.")

    update_data = []
    max_workers = min(len(files_by_drive), config.HASHING_WORKERS)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_drive = {
            executor.submit(_process_drive_list, item, get_hsl_color_for_bar(i, len(files_by_drive))): item[0] 
            for i, item in enumerate(sorted(files_by_drive.items()))
        }
        
        logging.debug(f"MAIN_HASHER: Submitted {len(future_to_drive)} jobs. Waiting for results...")
        for future in as_completed(future_to_drive):
            drive = future_to_drive[future]
            try:
                drive_results = future.result()
                if drive_results:
                    logging.debug(f"MAIN_HASHER: Got {len(drive_results)} results from drive {drive}.")
                    fixed_results = [(res['hash'], res['id']) for res in drive_results]
                    update_data.extend(fixed_results)
            except Exception as exc:
                logging.error(f"MAIN_HASHER: Drive {drive} future generated an exception: {exc}", exc_info=True)

    logging.debug(f"MAIN_HASHER: All futures complete. Total results to update in DB: {len(update_data)}")
    if not update_data: return

    logging.info(f"Updating database with {len(update_data)} new file hashes...")
    update_sql = "UPDATE files SET xxh128_hash = ?, status = 'hashed', hash_date = unixepoch() WHERE id = ?"
    
    try:
        with get_db_connection() as conn:
            conn.executemany(update_sql, update_data)
            conn.commit()
        logging.info("Database successfully updated.")
    except Exception as e:
        logging.error(f"Failed to update database with hashes: {e}", exc_info=True)