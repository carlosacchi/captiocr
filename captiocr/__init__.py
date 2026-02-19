"""
CaptiOCR - Screen Caption Capture Tool
"""
# Import from centralized config (no runtime deps required)
from .config.app_info import app_info

__version__ = app_info.version
__author__ = app_info.author
__email__ = app_info.email
__url__ = app_info.url

# Lazy module exports: defer imports of modules that depend on runtime
# packages (keyboard, pytesseract, PIL) so that importing the captiocr
# package itself does not fail when optional deps are missing.
__all__ = ['ScreenCapture', 'OCRProcessor', 'Settings']


def __getattr__(name):
    if name == 'ScreenCapture':
        from .core.capture import ScreenCapture
        return ScreenCapture
    if name == 'OCRProcessor':
        from .core.ocr import OCRProcessor
        return OCRProcessor
    if name == 'Settings':
        from .config.settings import Settings
        return Settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
