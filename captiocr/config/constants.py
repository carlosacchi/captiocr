"""
Application constants and configuration values.
"""
import os
from pathlib import Path

# Import all app info from centralized source
from .app_info import app_info

# Application Info - ALL from external config
APP_NAME = app_info.app_name
APP_VERSION = app_info.version
APP_AUTHOR = app_info.author
APP_EMAIL = app_info.email
APP_URL = app_info.url

# Tesseract Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESSDATA_PREFIX = r'C:\Program Files\Tesseract-OCR\tessdata'

# Window Configuration
MAIN_WINDOW_WIDTH = 250
MAIN_WINDOW_HEIGHT = 400
MAIN_WINDOW_ALPHA = 0.92

# Capture Configuration
DEFAULT_MIN_CAPTURE_INTERVAL = 3.0  # seconds
DEFAULT_MAX_CAPTURE_INTERVAL = 6.0  # seconds
MAX_SIMILAR_CAPTURES = 1
TEXT_SIMILARITY_THRESHOLD = 0.8
MIN_TEXT_LENGTH = 10
MIN_CAPTURE_AREA_SIZE = 70  # pixels

# UI Configuration
CAPTURE_WINDOW_ALPHA = 0.1  # Semi-transparent - control frame visible, capture area distinguishable
CAPTURE_WINDOW_COLOR = 'white'  # Using white for transparent effect
CONTROL_FRAME_HEIGHT = 30  # pixels - increased to avoid overlap with capture area
SELECTION_WINDOW_ALPHA = 0.5
SELECTION_WINDOW_COLOR = 'black'

# Supported Languages
SUPPORTED_LANGUAGES = [
    ("English", "eng"),
    ("Italiano", "ita"),
    ("Français", "fra"),
    ("Español", "spa"),
    ("Deutsch", "deu"),
    ("Português", "por")
]

# File Paths
def get_app_path() -> Path:
    """Get the base application path."""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent

# Directory Structure
APP_PATH = get_app_path()
CAPTURES_DIR = APP_PATH / "captures"
CONFIG_DIR = APP_PATH / "config"
LOGS_DIR = APP_PATH / "logs"
RESOURCES_DIR = APP_PATH / "resources"
TESSDATA_DIR = APP_PATH / "tessdata"

# Logging Configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEBUG_LOG_FILE = "ocr_debug.log"

# OCR Configuration
OCR_CONFIG_CAPTION_MODE = "--psm 3 --oem 1"  # Auto segmentation for dynamic live captions
OCR_CONFIG_GENERAL = "--psm 6 --oem 1"  # Uniform text block for documents

# File Naming Patterns
CAPTURE_FILE_PREFIX = "capture_"
PROCESSED_FILE_SUFFIX = "_processed"
TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M-%S"

# Multi-Monitor Configuration
DEFAULT_DPI = 96
MONITOR_REFRESH_ON_START = True
MONITOR_DISCONNECTION_CHECK_INTERVAL = 5.0  # seconds

# Language Download Configuration
TESSDATA_DOWNLOAD_URL = "https://github.com/tesseract-ocr/tessdata/raw/main/{}.traineddata"