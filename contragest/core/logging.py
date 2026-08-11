import logging
import os
import errno
from logging.handlers import RotatingFileHandler

class _SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that gracefully skips rotation if file is locked by another process."""

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            # Another process has the log file locked (common on Windows).
            # Skip rotation and continue writing to the current file.
            pass
        except OSError as exc:
            if exc.errno == errno.EACCES:
                pass
            else:
                raise

def setup_logger(name="contragest"):
    """
    Sets up a logger with a rotating file handler.
    Logs are saved to the 'logs' directory in the project root.
    """
    # Define log directory and file
    # contragest/core/logging.py -> core -> contragest -> ProjectRoot
    # CONTRAGEST_BASE_DIR lets the Windows service pin a stable location when
    # the app is frozen (PyInstaller) and __file__ resolves to _MEIPASS/_internal.
    base_dir = os.environ.get("CONTRAGEST_BASE_DIR") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.environ.get("CONTRAGEST_LOG_DIR") or os.path.join(base_dir, "logs")
    log_file = os.path.join(log_dir, "contragest.log")

    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid adding multiple handlers if logger is already set up
    if not logger.handlers:
        # File Handler (Rotating)
        # Max size 5MB, keep 5 backup files
        file_handler = _SafeRotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # Console Handler (Optional, for dev)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
