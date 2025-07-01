# logger_setup.py

import logging
import sys
from config import LOG_FILE_PATH

def setup_logging(verbosity: int = 0):
    """
    Configures the root logger to output to both a file and the console.
    Verbosity level controls the console output level.
    """
    file_log_level = logging.DEBUG
    
    if verbosity >= 1:
        console_log_level = logging.DEBUG
    else:
        console_log_level = logging.INFO

    logger = logging.getLogger()
    logger.setLevel(file_log_level) 

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError as e:
        print(f"Error: Unable to set up log file at {LOG_FILE_PATH}. Error: {e}")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(f"Logging configured. Console level: {logging.getLevelName(console_log_level)}, File level: {logging.getLevelName(file_log_level)}")