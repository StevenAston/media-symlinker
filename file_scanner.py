# file_scanner.py

import ctypes
import logging
import os
import sys

import config
from database import get_db_connection

EVERYTHING_REQUEST_FILE_NAME = 0x00000001
EVERYTHING_REQUEST_PATH = 0x00000002
EVERYTHING_REQUEST_SIZE = 0x00000010
EVERYTHING_REQUEST_DATE_MODIFIED = 0x00000080

def setup_everything_sdk():
    """Loads the Everything DLL and sets up the function prototypes for ctypes."""
    dll_path = "C:\\Program Files\\Everything\\Everything64.dll" if sys.maxsize > 2**32 else "C:\\Program Files (x86)\\Everything\\Everything32.dll"
    if not os.path.exists(dll_path): raise FileNotFoundError(f"Could not find Everything DLL at {dll_path}")
    everything_dll = ctypes.WinDLL(dll_path)
    everything_dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
    everything_dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint]
    everything_dll.Everything_QueryW.argtypes = [ctypes.c_bool]
    everything_dll.Everything_GetNumResults.restype = ctypes.c_uint
    everything_dll.Everything_GetResultSize.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_longlong)]
    everything_dll.Everything_GetResultDateModified.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_longlong)]
    everything_dll.Everything_GetResultPathW.argtypes = [ctypes.c_uint]
    everything_dll.Everything_GetResultPathW.restype = ctypes.c_wchar_p
    everything_dll.Everything_GetResultFileNameW.argtypes = [ctypes.c_uint]
    everything_dll.Everything_GetResultFileNameW.restype = ctypes.c_wchar_p
    return everything_dll

def _iterate_everything_results(dll):
    """
    A private generator that yields a dictionary for each result from an Everything query.
    This function encapsulates all the ctypes-specific logic.
    """
    num_results = dll.Everything_GetNumResults()
    size, date_modified_ft = ctypes.c_longlong(0), ctypes.c_longlong(0)
    for i in range(num_results):
        path_part = dll.Everything_GetResultPathW(i)
        filename_part = dll.Everything_GetResultFileNameW(i)
        if not filename_part: continue
        full_path = os.path.join(path_part, filename_part)
        is_symlink = os.path.islink(full_path)
        dll.Everything_GetResultSize(i, ctypes.byref(size))
        dll.Everything_GetResultDateModified(i, ctypes.byref(date_modified_ft))
        unix_timestamp = (date_modified_ft.value - 116444736000000000) / 10000000
        yield {"full_path": full_path, "file_size": size.value, "modified_date": unix_timestamp, "is_symlink": is_symlink}

def scan_directory(dll, search_path, scan_source):
    """
    Uses the Everything SDK to find all files in a given path and inserts/updates them in the database.
    """
    logging.info(f"Scanning '{search_path}' for files...")
    normalized_path = search_path.replace('/', '\\')
    request_flags = EVERYTHING_REQUEST_PATH | EVERYTHING_REQUEST_FILE_NAME | EVERYTHING_REQUEST_SIZE | EVERYTHING_REQUEST_DATE_MODIFIED
    dll.Everything_SetRequestFlags(request_flags)
    dll.Everything_SetSearchW(f'file: path:"{normalized_path}"')
    if not dll.Everything_QueryW(True): logging.error(f"Everything query failed for path: {search_path}"); return
    
    # We now call our clean, isolated generator. This is the key to testability.
    results_generator = _iterate_everything_results(dll)
    
    files_to_upsert = [(r["full_path"], os.path.basename(r["full_path"]), os.path.dirname(r["full_path"]), scan_source, r["file_size"], r["modified_date"], 1 if r["is_symlink"] else 0) for r in results_generator]
    if not files_to_upsert: logging.info(f"No files found in '{search_path}'."); return

    logging.info(f"Updating database with {len(files_to_upsert)} records from '{scan_source}'...")
    upsert_sql = """
    INSERT INTO files (full_path, filename, directory, scan_source, file_size, modified_date, is_symlink)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(full_path) DO UPDATE SET
        file_size=excluded.file_size,
        modified_date=excluded.modified_date,
        is_symlink=excluded.is_symlink,
        status='new',
        xxh128_hash=NULL
    """
    try:
        with get_db_connection() as conn:
            conn.executemany(upsert_sql, files_to_upsert)
            conn.commit()
        logging.info(f"Database successfully updated for '{scan_source}'.")
    except Exception as e:
        logging.error(f"Failed to update database: {e}")
        raise

def run_file_scan():
    """Main function to set up and run the file scanning process."""
    try:
        sdk = setup_everything_sdk()
        scan_directory(sdk, config.DOWNLOADS_PATH, 'downloads')
        scan_directory(sdk, config.MEDIA_PATH, 'media')
    except FileNotFoundError as e:
        logging.critical(f"Cannot proceed with file scan. Error: {e}")
    except Exception as e:
        logging.critical(f"An unexpected error occurred during file scan: {e}")