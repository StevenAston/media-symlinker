# file_scanner.py

import logging
import os
import ctypes
import sys

import config
from database import get_db_connection

# ... (SDK setup and _iterate_everything_results are correct) ...
EVERYTHING_REQUEST_FILE_NAME = 0x00000001
EVERYTHING_REQUEST_PATH = 0x00000002
EVERYTHING_REQUEST_SIZE = 0x00000010
EVERYTHING_REQUEST_DATE_MODIFIED = 0x00000080
EVERYTHING_REQUEST_ATTRIBUTES = 0x00000400
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

def setup_everything_sdk():
    # ... (this function is correct)
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
    everything_dll.Everything_GetResultAttributes.argtypes = [ctypes.c_uint]
    everything_dll.Everything_GetResultAttributes.restype = ctypes.c_uint
    return everything_dll

def _iterate_everything_results(dll):
    # ... (this function is correct) ...
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
        attributes = dll.Everything_GetResultAttributes(i)
        unix_timestamp = (date_modified_ft.value - 116444736000000000) / 10000000
        yield {"full_path": full_path, "file_size": size.value, "modified_date": unix_timestamp, "is_symlink": is_symlink}

def scan_directory(dll, search_path, scan_source, physical_drive):
    """Uses the Everything SDK to find all files and store them with their physical drive."""
    logging.info(f"Scanning '{search_path}' on drive '{physical_drive}' for '{scan_source}' files...")
    normalized_path = search_path.replace('/', '\\')
    request_flags = EVERYTHING_REQUEST_PATH | EVERYTHING_REQUEST_FILE_NAME | EVERYTHING_REQUEST_SIZE | EVERYTHING_REQUEST_DATE_MODIFIED
    dll.Everything_SetRequestFlags(request_flags)
    
    search_query = f'file: path:"{normalized_path}"'
    
    # --- NEW DIAGNOSTIC LINE ---
    logging.debug(f"Executing Everything search query: [{search_query}]")
    # --- END DIAGNOSTIC ---
    
    dll.Everything_SetSearchW(search_query)
    if not dll.Everything_QueryW(True):
        logging.error(f"Everything query failed for path: {search_path}")
        return
    
    files_to_upsert = []
    # ... (The rest of the function is correct)
    for r in _iterate_everything_results(dll):
        files_to_upsert.append((
            r["full_path"],
            physical_drive,
            os.path.basename(r["full_path"]),
            os.path.dirname(r["full_path"]),
            scan_source,
            r["file_size"],
            r["modified_date"],
            1 if r["is_symlink"] else 0
        ))

    if not files_to_upsert:
        logging.info(f"No files found in '{search_path}'.")
        return
    # ... (The rest of the function is correct)
    logging.info(f"Updating database with {len(files_to_upsert)} records from '{scan_source}'...")
    upsert_sql = """
    INSERT INTO files (full_path, physical_drive, filename, directory, scan_source, file_size, modified_date, is_symlink)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(full_path) DO UPDATE SET
        physical_drive=excluded.physical_drive,
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
        logging.error(f"Failed to update database: {e}", exc_info=True)
        raise


def run_file_scan():
    """Main function to scan all configured physical drives."""
    try:
        sdk = setup_everything_sdk()
        logging.info("Scanning physical drives for media and download content...")

        # Get the correct subfolder names from the virtual paths in the config.
        media_subfolder_name = os.path.basename(config.VIRTUAL_MEDIA_PATH)
        downloads_subfolder_name = os.path.basename(config.VIRTUAL_DOWNLOADS_PATH)
        
        # Iterate through the physical drives
        for drive_letter, pool_part_path in config.PHYSICAL_DRIVE_PATHS.items():

            # Construct the full paths to the Media and Downloads subfolders
            media_folder_on_drive = os.path.join(pool_part_path, media_subfolder_name)
            downloads_folder_on_drive = os.path.join(pool_part_path, downloads_subfolder_name)
            
            if os.path.exists(media_folder_on_drive):
                scan_directory(sdk, media_folder_on_drive, 'media', drive_letter)
            else:
                logging.debug(f"Path not found, skipping scan: {media_folder_on_drive}")

            if os.path.exists(downloads_folder_on_drive):
                scan_directory(sdk, downloads_folder_on_drive, 'downloads', drive_letter)
            else:
                logging.debug(f"Path not found, skipping scan: {downloads_folder_on_drive}")
            
    except Exception as e:
        logging.critical(f"An unexpected error occurred during file scan: {e}", exc_info=True)