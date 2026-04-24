"""
Language file management for Tesseract OCR.
"""
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from ..config.constants import CONFIG_DIR, SUPPORTED_LANGUAGES, TESSDATA_DOWNLOAD_URL


# Allow-list of language codes that can be downloaded. Restricting to the
# codes the application actually advertises prevents path traversal via a
# crafted ``lang_code`` (e.g. ``"../foo"``) and limits the attack surface
# of the upstream URL template.
_ALLOWED_LANG_CODES = frozenset(code for _, code in SUPPORTED_LANGUAGES)
_LANG_CODE_PATTERN = re.compile(r"^[a-z]{2,8}(?:_[A-Za-z]{2,8})?$")
_TRUSTED_DOWNLOAD_HOSTS = frozenset({
    "github.com",
    "raw.githubusercontent.com",
})
# Minimum plausible size of a real .traineddata file (in bytes).
_MIN_TRAINEDDATA_SIZE = 100_000


def _is_allowed_lang_code(lang_code: str) -> bool:
    """Validate that a language code is on the allow-list and well-formed."""
    if lang_code not in _ALLOWED_LANG_CODES:
        return False
    return bool(_LANG_CODE_PATTERN.match(lang_code))


def _is_trusted_download_url(url: str) -> bool:
    """Reject downloads that don't go to a known-good HTTPS host."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    return parsed.hostname in _TRUSTED_DOWNLOAD_HOSTS


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
            # Validate the language code against the allow-list before
            # touching the network or the filesystem. This blocks path
            # traversal (e.g. "../foo") and unexpected codes.
            if not _is_allowed_lang_code(lang_code):
                self.logger.error(
                    f"Refusing to download '{lang_code}': "
                    "not in the supported language allow-list"
                )
                if progress_callback:
                    progress_callback(
                        f"Language '{lang_code}' is not supported"
                    )
                return False

            # Ensure tessdata directory exists
            tessdata_dir.mkdir(parents=True, exist_ok=True)

            output_file = tessdata_dir / f"{lang_code}.traineddata"
            url = TESSDATA_DOWNLOAD_URL.format(lang_code)

            # Reject any URL that doesn't resolve to a trusted host over
            # HTTPS, even if the URL template was tampered with.
            if not _is_trusted_download_url(url):
                self.logger.error(
                    f"Refusing to download {lang_code}: untrusted URL {url}"
                )
                if progress_callback:
                    progress_callback(f"Untrusted download URL for {lang_code}")
                return False

            self.logger.info(f"Downloading {lang_code} from {url}")

            if progress_callback:
                progress_callback(f"Downloading {lang_code}.traineddata...")

            # Download to a temporary file inside the same directory so we
            # can atomically rename into place once the content is
            # validated. This prevents partial/corrupt files from being
            # picked up by the OCR engine.
            tmp_file = tessdata_dir / f".{lang_code}.traineddata.part"

            try:
                with urllib.request.urlopen(url, timeout=300) as response:
                    file_data = response.read()
                tmp_file.write_bytes(file_data)
            except urllib.error.HTTPError as e:
                self.logger.error(
                    f"HTTP error downloading {lang_code}: {e.code} - {e.reason}"
                )
                if tmp_file.exists():
                    tmp_file.unlink()
                return False
            except urllib.error.URLError as e:
                self.logger.error(f"Network error downloading {lang_code}: {e}")
                if tmp_file.exists():
                    tmp_file.unlink()
                return False
            except Exception as e:
                self.logger.error(f"Error downloading {lang_code}: {e}")
                if tmp_file.exists():
                    tmp_file.unlink()
                return False

            # Verify the file is plausibly a real .traineddata payload.
            if tmp_file.stat().st_size < _MIN_TRAINEDDATA_SIZE:
                self.logger.error(
                    f"Downloaded {lang_code} is too small "
                    f"({tmp_file.stat().st_size} bytes); aborting"
                )
                tmp_file.unlink()
                return False

            # Atomically replace any existing file.
            os.replace(tmp_file, output_file)

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