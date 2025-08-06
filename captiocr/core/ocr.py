"""
OCR processing module using Tesseract.
"""
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import logging
import subprocess

try:
    import pytesseract
    from PIL import Image
except ImportError as e:
    logging.error(f"Required package not found: {e}")
    sys.exit(1)

from ..config.constants import (
    TESSERACT_CMD, TESSDATA_PREFIX,
    OCR_CONFIG_CAPTION_MODE, OCR_CONFIG_GENERAL
)


class OCRProcessor:
    """Handle OCR operations using Tesseract."""
    
    def __init__(self):
        """Initialize OCR processor."""
        self.logger = logging.getLogger('CaptiOCR.OCRProcessor')
        self.tesseract_initialized = False
        self.initialize_tesseract()
    
    def initialize_tesseract(self) -> bool:
        """
        Initialize Tesseract for OCR operations.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if Tesseract executable exists
            if not os.path.exists(TESSERACT_CMD):
                self.logger.error(f"Tesseract not found at: {TESSERACT_CMD}")
                return False
            
            # Set Tesseract executable path
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            
            # Set tessdata directory - always start with system tessdata
            # Local tessdata will be used dynamically when specific languages are found there
            os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
            self.logger.info(f"Using system tessdata: {TESSDATA_PREFIX}")
            
            # Verify installation
            version = self.get_tesseract_version()
            if version:
                self.logger.info(f"Tesseract initialized: {version}")
                self.tesseract_initialized = True
                return True
            else:
                self.logger.error("Failed to verify Tesseract installation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error initializing Tesseract: {e}")
            return False
    
    def get_tesseract_version(self) -> Optional[str]:
        """
        Get Tesseract version information.
        
        Returns:
            Version string or None if error
        """
        try:
            # Use subprocess to avoid console window on Windows
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            result = subprocess.run(
                [TESSERACT_CMD, "--version"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo
            )
            
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split('\n')[0]
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting Tesseract version: {e}")
            return None
    
    def is_tesseract_available(self) -> bool:
        """
        Check if Tesseract is available and initialized.
        
        Returns:
            True if available, False otherwise
        """
        return self.tesseract_initialized
    
    def check_language_available(self, lang_code: str) -> bool:
        """
        Check if a language is available in Tesseract (like original).
        
        Args:
            lang_code: Language code to check
            
        Returns:
            True if language is available
        """
        try:
            # English is always available by default in Tesseract installations
            if lang_code == "eng":
                self.logger.debug("English language is always available by default")
                return True
            
            # Check multiple locations like original CaptiOCR_old.py
            
            # 1. Check local tessdata directory (where languages are downloaded)
            from ..config.constants import TESSDATA_DIR
            local_tessdata = Path(TESSDATA_DIR)
            local_lang_file = local_tessdata / f"{lang_code}.traineddata"
            
            if local_lang_file.exists():
                self.logger.debug(f"Language {lang_code} found in local tessdata: {local_lang_file}")
                return True
            
            # 2. Check system Tesseract tessdata directory
            system_tessdata = os.environ.get('TESSDATA_PREFIX', TESSDATA_PREFIX)
            system_lang_file = Path(system_tessdata) / f"{lang_code}.traineddata"
            
            if system_lang_file.exists():
                self.logger.debug(f"Language {lang_code} found in system tessdata: {system_lang_file}")
                return True
            
            self.logger.debug(f"Language {lang_code} not found in either location")
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking language availability: {e}")
            return False
    
    def _set_tessdata_for_language(self, lang_code: str) -> None:
        """
        Set the appropriate tessdata path for the given language.
        
        Args:
            lang_code: Language code
        """
        try:
            # English always uses system tessdata
            if lang_code == "eng":
                os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
                self.logger.debug("Using system tessdata for English")
                return
            
            # Check if language exists in local tessdata
            from ..config.constants import TESSDATA_DIR
            local_tessdata = Path(TESSDATA_DIR)
            local_lang_file = local_tessdata / f"{lang_code}.traineddata"
            
            if local_lang_file.exists():
                os.environ['TESSDATA_PREFIX'] = str(local_tessdata)
                self.logger.debug(f"Using local tessdata for {lang_code}")
            else:
                os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
                self.logger.debug(f"Using system tessdata for {lang_code}")
                
        except Exception as e:
            self.logger.error(f"Error setting tessdata path: {e}")
            # Fallback to system tessdata
            os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
    
    def get_ocr_config(self, caption_mode: bool = False) -> str:
        """
        Get OCR configuration string.
        
        Args:
            caption_mode: Whether to use caption-optimized settings
            
        Returns:
            Configuration string for Tesseract
        """
        if caption_mode:
            return OCR_CONFIG_CAPTION_MODE
        else:
            return OCR_CONFIG_GENERAL
    
    def process_image(self, image: Image.Image, lang_code: str = "eng", 
                      caption_mode: bool = False) -> str:
        """
        Process an image and extract text using OCR.
        
        Args:
            image: PIL Image object
            lang_code: Language code for OCR
            caption_mode: Whether to use caption-optimized settings
            
        Returns:
            Extracted text
            
        Raises:
            RuntimeError: If Tesseract is not initialized
        """
        if not self.tesseract_initialized:
            raise RuntimeError("Tesseract is not initialized")
        
        try:
            # Check if language is available and set appropriate tessdata path
            if not self.check_language_available(lang_code):
                self.logger.warning(f"Language {lang_code} not available, using English")
                lang_code = "eng"
            
            # Set appropriate tessdata path for the language
            self._set_tessdata_for_language(lang_code)
            
            # Get OCR configuration
            config = self.get_ocr_config(caption_mode)
            self.logger.debug(f"Using OCR config: '{config}' for caption_mode={caption_mode}")
            
            # Perform OCR
            text = pytesseract.image_to_string(
                image,
                lang=lang_code,
                config=config
            ).strip()
            
            return text
            
        except Exception as e:
            self.logger.error(f"Error processing image: {e}")
            return ""
    
    def optimize_image_for_ocr(self, image: Image.Image, 
                               max_dimension: int = 1000) -> Image.Image:
        """
        Optimize image for better OCR results.
        
        Args:
            image: PIL Image object
            max_dimension: Maximum dimension (width or height) in pixels
            
        Returns:
            Optimized image
        """
        try:
            # Check if resizing is needed
            width, height = image.size
            
            if width * height > max_dimension * max_dimension:
                # Calculate new dimensions maintaining aspect ratio
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                
                # Resize image
                image = image.resize(
                    (new_width, new_height),
                    resample=Image.Resampling.LANCZOS
                )
                
                self.logger.debug(
                    f"Resized image from {width}x{height} to "
                    f"{new_width}x{new_height} for OCR"
                )
            
            return image
            
        except Exception as e:
            self.logger.error(f"Error optimizing image: {e}")
            return image
    
    def install_tesseract(self) -> bool:
        """
        Attempt to install Tesseract (Windows only).
        
        Returns:
            True if installation successful, False otherwise
        """
        if sys.platform != 'win32':
            self.logger.error("Automatic Tesseract installation only supported on Windows")
            return False
        
        try:
            # Import Windows-specific modules
            import tempfile
            import urllib.request
            
            self.logger.info("Starting Tesseract installation...")
            
            # Download URL for Tesseract installer
            installer_url = (
                "https://github.com/tesseract-ocr/tesseract/releases/download/"
                "5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
            )
            
            # Create temp directory
            with tempfile.TemporaryDirectory(prefix="tesseract_install_") as temp_dir:
                installer_path = Path(temp_dir) / "tesseract-installer.exe"
                
                # Download installer
                self.logger.info("Downloading Tesseract installer...")
                urllib.request.urlretrieve(installer_url, installer_path)
                
                # Run installer
                self.logger.info("Running Tesseract installer...")
                result = subprocess.run(
                    [str(installer_path), "/SILENT", "/NORESTART", 
                     f"/DIR={TESSERACT_CMD.parent}"],
                    check=True
                )
                
                # Wait for installation to complete
                import time
                max_wait = 120  # seconds
                
                for i in range(max_wait):
                    if os.path.exists(TESSERACT_CMD):
                        time.sleep(3)  # Wait a bit more to ensure completion
                        self.logger.info("Tesseract installation completed")
                        return self.initialize_tesseract()
                    time.sleep(1)
                
                self.logger.error("Tesseract installation timed out")
                return False
                
        except Exception as e:
            self.logger.error(f"Error installing Tesseract: {e}")
            return False