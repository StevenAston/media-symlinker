# In hashing.py

import logging
import os
import xxhash
import time
import random # <-- Import the random module
from multiprocessing import Pool
from tqdm import tqdm

import config
from database import get_db_connection

def _hash_file_worker(file_info):
    file_id, file_path, file_size = file_info
    try:
        # --- ADD THIS DEBUG LOG ---
        logging.debug(f"Worker {os.getpid()}: Starting hash for {file_path}")
        start_time = time.monotonic()
        h = xxhash.xxh128()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        end_time = time.monotonic()
        time_taken = end_time - start_time
        logging.debug(f"Worker {os.getpid()}: Finished hash for {file_path} in {time_taken:.2f}s")
        return (file_id, h.hexdigest(), file_size, time_taken)
    except Exception as e:
        logging.error(f"Worker {os.getpid()}: FAILED to hash {file_path}. Error: {e}")
        return None

def hash_all_unhashed_files():
    # ... (code is the same until you get the list of files) ...
    try:
        with get_db_connection() as conn:
            sql_get_unhashed = "SELECT id, full_path, file_size FROM files WHERE xxh128_hash IS NULL AND is_symlink = 0"
            files_to_hash = conn.execute(sql_get_unhashed).fetchall()
            total_size_to_hash = sum(f['file_size'] for f in files_to_hash)
    except Exception as e:
        logging.error(f"Failed to get list of unhashed files: {e}")
        return

    if not files_to_hash:
        logging.info("No unhashed files found."); return

    # --- YOUR SIMPLE, EFFECTIVE SHUFFLE PROPOSAL ---
    logging.info(f"Shuffling {len(files_to_hash)} files to improve disk I/O randomness...")
    random.shuffle(files_to_hash)
    # --- END SHUFFLE ---

    logging.info(f"Found {len(files_to_hash)} files to process, for a total of {total_size_to_hash / 1024**3:.2f} GiB.")
    
    update_data = []
    total_bytes_processed = 0
    total_time_spent_hashing = 0

    if config.HASHING_WORKERS <= 1:
        logging.info("Running in single-threaded mode.")
        pbar = tqdm(files_to_hash, desc="Hashing Files", unit='B', unit_scale=True, unit_divisor=1024)
        for file_info in pbar:
            result = _hash_file_worker((file_info['id'], file_info['full_path'], file_info['file_size']))
            if result:
                file_id, file_hash, file_size, time_taken = result
                update_data.append((file_hash, file_id))
                # Update progress bar and speed
                total_bytes_processed += file_size
                total_time_spent_hashing += time_taken
                if total_time_spent_hashing > 0:
                    speed = (total_bytes_processed / total_time_spent_hashing) / 1024**2
                    pbar.set_postfix_str(f"{speed:.2f} MiB/s")
        pbar.close()
    else:
        # --- THE DEFINITIVE FIX ---
        # Import Pool locally, only when it's actually needed.
        from multiprocessing import Pool
        # --- END OF FIX ---
        
        logging.info(f"Starting parallel hashing with {config.HASHING_WORKERS} workers...")
        pbar = tqdm(total=total_size_to_hash, unit='B', unit_scale=True, desc="Hashing", unit_divisor=1024)
        with Pool(processes=config.HASHING_WORKERS) as pool:
            worker_args = [(f['id'], f['full_path'], f['file_size']) for f in files_to_hash]
            for result in pool.imap_unordered(_hash_file_worker, worker_args):
                if result:
                    file_id, file_hash, file_size, time_taken = result
                    update_data.append((file_hash, file_id))
                    total_bytes_processed += file_size
                    total_time_spent_hashing += time_taken
                    if total_time_spent_hashing > 0:
                        speed = (total_bytes_processed / total_time_spent_hashing) / 1024**2
                        pbar.set_postfix_str(f"{speed:.2f} MiB/s")
                    pbar.update(file_size)
        pbar.close()

    if not update_data: logging.warning("Hashing completed, but no new hashes were generated."); return

    logging.info(f"Updating database with {len(update_data)} new file hashes...")
    update_sql = "UPDATE files SET xxh128_hash = ?, status = 'hashed', hash_date = unixepoch() WHERE id = ?"
    
    try:
        with get_db_connection() as conn:
            conn.executemany(update_sql, update_data)
            conn.commit()
        logging.info("Database successfully updated with new hashes.")
    except Exception as e:
        logging.error(f"Failed to update database with hashes: {e}")