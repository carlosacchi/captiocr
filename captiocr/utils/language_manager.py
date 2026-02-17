"""
Language file management for Tesseract OCR.
"""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from ..config.constants import CONFIG_DIR, TESSDATA_DOWNLOAD_URL


class LanguageManager:
    """Manage Tesseract language files."""
    
    def __init__(self):
        """Initialize language manager."""
        self.logger = logging.getLogger('CaptiOCR.LanguageManager')
        self.languages_file = CONFIG_DIR / 'downloaded_languages.json'
        self.downloaded_languages = self._load_downloaded_languages()
    
    def _load_downloaded_languages(self) -> Dict[str, Any]:
        """
        Load downloaded languages from JSON file.
        
        Returns:
            Dictionary of downloaded languages with their paths
        """
        try:
            if self.languages_file.exists():
                with open(self.languages_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading downloaded languages: {e}")
            return {}
    
    def _save_downloaded_languages(self) -> None:
        """Save downloaded languages to JSON file."""
        try:
            with open(self.languages_file, 'w') as f:
                json.dump(self.downloaded_languages, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving downloaded languages: {e}")
    
    def add_language(self, lang_code: str, lang_path: str) -> None:
        """
        Add a downloaded language to the tracked languages.
        
        Args:
            lang_code: Language code (e.g., 'eng', 'ita')
            lang_path: Full path to the language file
        """
        self.downloaded_languages[lang_code] = {
            'path': lang_path,
            'timestamp': datetime.now().isoformat()
        }
        self._save_downloaded_languages()
        self.logger.info(f"Added language {lang_code} at {lang_path}")
    
    def get_language_path(self, lang_code: str) -> Optional[str]:
        """
        Get the path of a downloaded language file.
        
        Args:
            lang_code: Language code
        
        Returns:
            Path to language file, or None if not found
        """
        lang_info = self.downloaded_languages.get(lang_code)
        if lang_info:
            path = lang_info['path']
            if os.path.exists(path):
                return path
            else:
                # Remove invalid path from downloaded languages
                self.logger.warning(f"Language file not found at {path}, removing from cache")
                del self.downloaded_languages[lang_code]
                self._save_downloaded_languages()
        return None
    
    def is_language_available(self, lang_code: str) -> bool:
        """
        Check if a language file is available.
        
        Args:
            lang_code: Language code
        
        Returns:
            True if language file exists, False otherwise
        """
        return self.get_language_path(lang_code) is not None
    
    def download_language(self, lang_code: str, tessdata_dir: Path, 
                          progress_callback: Optional[callable] = None) -> bool:
        """
        Download a language file from GitHub.
        
        Args:
            lang_code: Language code to download
            tessdata_dir: Directory to save the file
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure tessdata directory exists
            tessdata_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = tessdata_dir / f"{lang_code}.traineddata"
            url = TESSDATA_DOWNLOAD_URL.format(lang_code)
            
            self.logger.info(f"Downloading {lang_code} from {url}")
            
            if progress_callback:
                progress_callback(f"Downloading {lang_code}.traineddata...")
            
            # Download the file with timeout
            try:
                # Open URL with timeout
                with urllib.request.urlopen(url, timeout=300) as response:
                    # Read and write data in chunks to show progress
                    file_data = response.read()
                    with open(output_file, 'wb') as f:
                        f.write(file_data)
            except urllib.error.HTTPError as e:
                self.logger.error(f"HTTP error downloading {lang_code}: {e.code} - {e.reason}")
                return False
            except urllib.error.URLError as e:
                self.logger.error(f"Network error downloading {lang_code}: {e}")
                return False
            except Exception as e:
                self.logger.error(f"Error downloading {lang_code}: {e}")
                return False
            
            # Verify file was created and has content
            if output_file.exists() and output_file.stat().st_size > 0:
                self.add_language(lang_code, str(output_file))
                self.logger.info(f"Successfully downloaded {lang_code}")
                
                if progress_callback:
                    progress_callback(f"Downloaded {lang_code} successfully")
                
                return True
            else:
                self.logger.error(f"Downloaded file for {lang_code} is invalid")
                if output_file.exists():
                    output_file.unlink()
                return False
                
        except Exception as e:
            self.logger.error(f"Critical error downloading {lang_code}: {e}")
            return False
    
    def get_missing_languages(self, required_codes: list[str], 
                              tessdata_dirs: list[Path]) -> list[str]:
        """
        Check which required languages are missing.
        
        Args:
            required_codes: List of required language codes
            tessdata_dirs: List of directories to check
            
        Returns:
            List of missing language codes
        """
        missing = []
        
        for lang_code in required_codes:
            # Check tracked languages first
            if self.is_language_available(lang_code):
                continue
            
            # Check tessdata directories
            found = False
            for tessdata_dir in tessdata_dirs:
                lang_file = tessdata_dir / f"{lang_code}.traineddata"
                if lang_file.exists():
                    self.add_language(lang_code, str(lang_file))
                    found = True
                    break
            
            if not found:
                missing.append(lang_code)
        
        return missing
    
    def clean_invalid_entries(self) -> int:
        """
        Remove invalid entries from the language cache.
        
        Returns:
            Number of entries removed
        """
        removed = 0
        invalid_codes = []
        
        for lang_code, info in self.downloaded_languages.items():
            if not os.path.exists(info['path']):
                invalid_codes.append(lang_code)
                removed += 1
        
        for lang_code in invalid_codes:
            del self.downloaded_languages[lang_code]
        
        if removed > 0:
            self._save_downloaded_languages()
            self.logger.info(f"Cleaned {removed} invalid language entries")
        
        return removed