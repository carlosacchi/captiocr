"""
CaptiOCR - Screen Caption Capture Tool
"""
# Import from centralized config
from .config.app_info import app_info

__version__ = app_info.version
__author__ = app_info.author
__email__ = app_info.email
__url__ = app_info.url

# Module exports
from .core.capture import ScreenCapture
from .core.ocr import OCRProcessor
from .config.settings import Settings

__all__ = ['ScreenCapture', 'OCRProcessor', 'Settings']