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
TEXT_SIMILARITY_THRESHOLD = 0.80  # Fidelity-first: match v0.12.3 default
MIN_TEXT_LENGTH = 10  # Used only in post-processing delta extraction
MIN_CAPTURE_AREA_SIZE = 70  # pixels

# Delta Extraction Sensitivity Configuration
DEFAULT_MIN_DELTA_WORDS = 5  # Minimum words for significant delta
DEFAULT_RECENT_TEXTS_WINDOW_SIZE = 5  # Number of previous captures to compare
DEFAULT_DELTA_BUFFER_THRESHOLD = 3  # Fragments to accumulate before flushing
DEFAULT_INCREMENTAL_THRESHOLD = 0.7  # Percentage overlap for incremental detection (70%)

# Post-Processing Configuration (ROVER + TF-IDF scoring pipeline)
POST_PROCESS_EMIT_SCORE_THRESHOLD = 2.0   # Min aggregate novelty score to emit a frame
POST_PROCESS_FREQ_WINDOW_SIZE = 30        # Sliding window size (frames) for IDF frequency tracking
POST_PROCESS_FRAME_CONSENSUS_WINDOW = 3   # Frame voting window: ROVER checks this many recent frames
POST_PROCESS_MIN_SENTENCE_WORDS = 2       # Minimum words for a sentence to be considered meaningful

# Legacy post-processing constants — kept for backward compatibility with saved configs
POST_PROCESS_DEDUP_ENTER_THRESHOLD = 0.82
POST_PROCESS_DEDUP_EXIT_THRESHOLD = 0.55
POST_PROCESS_MIN_LENGTH_RATIO = 0.60
POST_PROCESS_MIN_NEW_WORDS = 3

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


def get_user_data_path() -> Path:
    """
    Get the writable user data root for CaptiOCR.

    Resolution order:
      1. ``CAPTIOCR_USER_DATA`` environment variable (power-user override).
      2. ``%LOCALAPPDATA%\\CaptiOCR`` on Windows.
      3. ``%APPDATA%\\CaptiOCR`` as Windows fallback.
      4. ``~/.captiocr`` on other platforms.

    Storing writable data outside the install directory avoids requiring
    write access to ``Program Files`` and keeps user content isolated from
    the application binaries.
    """
    override = os.environ.get("CAPTIOCR_USER_DATA")
    if override:
        return Path(override)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "CaptiOCR"

    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "CaptiOCR"

    return Path.home() / ".captiocr"


# Directory Structure
APP_PATH = get_app_path()
USER_DATA_PATH = get_user_data_path()


def _resolve_writable_dir(name: str) -> Path:
    """
    Resolve a writable subdirectory, preferring an existing legacy location
    next to the application (for backward compatibility with installs that
    pre-date the per-user data layout). New installs use ``USER_DATA_PATH``.
    """
    legacy = APP_PATH / name
    try:
        if legacy.exists() and any(legacy.iterdir()):
            return legacy
    except OSError:
        pass
    return USER_DATA_PATH / name


# Writable directories live under the per-user data path so we never need
# write access to the install directory (e.g. Program Files). Existing
# legacy directories next to the app are honored to avoid breaking upgrades.
CAPTURES_DIR = _resolve_writable_dir("captures")
CONFIG_DIR = _resolve_writable_dir("config")
LOGS_DIR = _resolve_writable_dir("logs")
TESSDATA_DIR = _resolve_writable_dir("tessdata")

# Read-only resources stay alongside the application binaries.
RESOURCES_DIR = APP_PATH / "resources"

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

# Tesseract installer download (Windows). Pinned to an official upstream
# release URL on github.com so that an attacker cannot point us at a
# different installer without modifying source code.
TESSERACT_INSTALLER_URL = (
    "https://github.com/tesseract-ocr/tesseract/releases/download/"
    "5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
)
TESSERACT_INSTALLER_TRUSTED_HOSTS = (
    "github.com",
    "objects.githubusercontent.com",
)
TESSERACT_INSTALLER_MIN_SIZE_BYTES = 5_000_000

# Update Check Configuration
GITHUB_RELEASES_API = "https://api.github.com/repos/CarloSacchi/CaptiOCR/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/CarloSacchi/CaptiOCR/releases/latest"