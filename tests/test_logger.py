# tests/test_logger.py
import logging
import os
from unittest.mock import patch

# We must import the modules we want to test
from logger_setup import setup_logging
from config import LOG_FILE_PATH

def test_setup_logging_creates_handlers():
    """
    Tests that calling setup_logging() correctly adds two handlers
    to the root logger.
    """
    # Get the root logger and clear any existing handlers
    logger = logging.getLogger()
    logger.handlers = []

    # Call the function we are testing
    setup_logging()

    # Assert (verify) that our expectations are met
    assert len(logger.handlers) == 2, "Expected two handlers to be configured"
    
    # Check that one handler is a StreamHandler (for the console)
    # and the other is a FileHandler (for the log file).
    handler_types = [type(h) for h in logger.handlers]
    assert logging.StreamHandler in handler_types, "A StreamHandler was not found"
    assert logging.FileHandler in handler_types, "A FileHandler was not found"

    # Clean up the created log file after the test
    # This is good practice to keep the project directory clean.
    # We must close the handlers so the file lock is released before deleting.
    for handler in logger.handlers:
        handler.close()
    
    if os.path.exists(LOG_FILE_PATH):
        os.remove(LOG_FILE_PATH)