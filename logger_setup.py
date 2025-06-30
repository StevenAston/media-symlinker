# In logger_setup.py

import logging
import sys
from config import LOG_FILE_PATH

def setup_logging(level=logging.INFO): # Add a level parameter
    """Configures the root logger."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Always capture everything at the root

    if logger.hasHandlers(): logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # The file handler will now log DEBUG messages and above
    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG) # Capture DEBUG to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError as e:
        print(f"Error: Unable to set up log file at {LOG_FILE_PATH}. Error: {e}")

    # The console handler will respect the level passed in (defaulting to INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level) # Use the function argument for the console
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("Logging configured.")