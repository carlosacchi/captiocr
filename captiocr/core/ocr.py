"""
OCR processing module using Tesseract.
"""
import os
import sys
import shutil
import urllib.parse
from pathlib import Path
from typing import Optional
import logging
import subprocess

try:
    import pytesseract
    from PIL import Image
except ImportError as e:
    logging.error(f"Required package not found: {e}")
    raise

from ..config.constants import (
    TESSERACT_CMD, TESSDATA_PREFIX,
    OCR_CONFIG_CAPTION_MODE, OCR_CONFIG_GENERAL,
    TESSERACT_INSTALLER_URL, TESSERACT_INSTALLER_TRUSTED_HOSTS,
    TESSERACT_INSTALLER_MIN_SIZE_BYTES,
    TESSERACT_PATH_CACHE,
)


def _is_trusted_installer_url(url: str) -> bool:
    """
    Validate that the Tesseract installer URL points to a trusted upstream
    host over HTTPS. Defense-in-depth in case the constant is overridden
    or modified at runtime.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    return parsed.hostname in TESSERACT_INSTALLER_TRUSTED_HOSTS


class OCRProcessor:
    """Handle OCR operations using Tesseract."""
    
    def __init__(self):
        """Initialize OCR processor."""
        self.logger = logging.getLogger('CaptiOCR.OCRProcessor')
        self.tesseract_initialized = False
        self.resolved_cmd: Optional[str] = None
        self.resolved_tessdata: Optional[str] = None
        self.initialize_tesseract()

    def _derive_tessdata_dir(self, cmd_path: str) -> Optional[str]:
        """
        Derive the tessdata directory from a tesseract executable path.

        Windows installs (and the bundled binary) keep tessdata next to the
        executable; Homebrew/MacPorts/Linux keep it at <prefix>/share/tessdata.
        """
        base = Path(cmd_path).parent
        for candidate in (base / 'tessdata', base.parent / 'share' / 'tessdata'):
            if candidate.is_dir():
                return str(candidate)
        return None
    
    def _resolve_tesseract_cmd(self) -> Optional[str]:
        """
        Resolve the Tesseract executable path by searching multiple locations.

        Search order:
        0. Binary bundled inside the frozen application (macOS .app).
        1. Cached path saved from a previous successful detection.
        2. Default path from constants (fastest when installed normally).
        3. System PATH via shutil.which.
        4. Well-known Homebrew/MacPorts locations on macOS (GUI apps do not
           inherit the shell PATH, so PATH lookup alone is not enough).
        5. Windows registry HKLM/HKCU SOFTWARE\\Tesseract-OCR InstallDir.
        6. Glob search under %LOCALAPPDATA%\\Programs\\ (any subfolder name).

        Returns:
            Absolute path string to the tesseract executable, or None.
        """
        # 0. Binary bundled inside the frozen app (PyInstaller)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            exe_name = 'tesseract.exe' if sys.platform == 'win32' else 'tesseract'
            bundled = Path(sys._MEIPASS) / exe_name
            if bundled.exists():
                self.logger.info(f"Using bundled Tesseract: {bundled}")
                return str(bundled)

        # 1. Cached path from a previous successful detection
        try:
            if TESSERACT_PATH_CACHE.exists():
                cached = TESSERACT_PATH_CACHE.read_text(encoding='utf-8').strip()
                if cached and os.path.exists(cached):
                    self.logger.debug(f"Tesseract found via cache: {cached}")
                    return cached
        except Exception as e:
            self.logger.debug(f"Cache read failed: {e}")

        # 2. Default constant path
        if os.path.exists(TESSERACT_CMD):
            self.logger.debug(f"Tesseract found at default path: {TESSERACT_CMD}")
            return TESSERACT_CMD

        # 3. System PATH
        found_in_path = shutil.which('tesseract')
        if found_in_path:
            self.logger.info(f"Tesseract found in PATH: {found_in_path}")
            return found_in_path

        # 4. Well-known install locations on macOS
        if sys.platform == 'darwin':
            for candidate in (
                '/opt/homebrew/bin/tesseract',
                '/usr/local/bin/tesseract',
                '/opt/local/bin/tesseract',
            ):
                if os.path.exists(candidate):
                    self.logger.info(f"Tesseract found at: {candidate}")
                    return candidate

        # 5. Windows registry
        if sys.platform == 'win32':
            try:
                import winreg
                for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    for reg_path in (
                        r'SOFTWARE\Tesseract-OCR',
                        r'SOFTWARE\WOW6432Node\Tesseract-OCR',
                    ):
                        try:
                            with winreg.OpenKey(root_key, reg_path) as key:
                                install_dir, _ = winreg.QueryValueEx(key, 'InstallDir')
                                candidate = str(Path(install_dir) / 'tesseract.exe')
                                if os.path.exists(candidate):
                                    self.logger.info(f"Tesseract found via registry: {candidate}")
                                    return candidate
                        except (FileNotFoundError, OSError):
                            continue
            except Exception as e:
                self.logger.debug(f"Registry search failed: {e}")

        # 6. Glob search under %LOCALAPPDATA%\Programs\ — finds any subfolder name
        if sys.platform == 'win32':
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            if local_app_data:
                try:
                    for found in sorted(Path(local_app_data).glob('Programs/**/tesseract.exe')):
                        self.logger.info(f"Tesseract found via glob: {found}")
                        return str(found)
                except Exception as e:
                    self.logger.debug(f"Glob search failed: {e}")

        self.logger.error("Tesseract executable not found in any known location")
        return None

    def initialize_tesseract(self) -> bool:
        """
        Initialize Tesseract for OCR operations.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            cmd = self._resolve_tesseract_cmd()
            if cmd is None:
                return False

            # Set Tesseract executable path
            pytesseract.pytesseract.tesseract_cmd = cmd
            self.resolved_cmd = cmd

            # Derive tessdata prefix from the resolved install directory
            tessdata_dir = self._derive_tessdata_dir(cmd)
            if tessdata_dir:
                self.resolved_tessdata = tessdata_dir
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
                self.logger.info(f"Using tessdata: {tessdata_dir}")
            else:
                # Fallback to constant (e.g. when found via PATH on non-Windows)
                self.resolved_tessdata = TESSDATA_PREFIX
                os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
                self.logger.info(f"Using system tessdata: {TESSDATA_PREFIX}")

            # Verify installation
            version = self.get_tesseract_version()
            if version:
                self.logger.info(f"Tesseract initialized: {version}")
                self.tesseract_initialized = True
                # Cache the resolved path for fast lookup on next startup
                try:
                    TESSERACT_PATH_CACHE.parent.mkdir(parents=True, exist_ok=True)
                    TESSERACT_PATH_CACHE.write_text(cmd, encoding='utf-8')
                except Exception as e:
                    self.logger.debug(f"Could not write Tesseract path cache: {e}")
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
                [self.resolved_cmd or TESSERACT_CMD, "--version"],
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
            system_tessdata = self.resolved_tessdata or os.environ.get('TESSDATA_PREFIX', TESSDATA_PREFIX)
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
        system_tessdata = self.resolved_tessdata or TESSDATA_PREFIX
        try:
            # English always uses system tessdata
            if lang_code == "eng":
                os.environ['TESSDATA_PREFIX'] = system_tessdata
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
                os.environ['TESSDATA_PREFIX'] = system_tessdata
                self.logger.debug(f"Using system tessdata for {lang_code}")

        except Exception as e:
            self.logger.error(f"Error setting tessdata path: {e}")
            # Fallback to system tessdata
            os.environ['TESSDATA_PREFIX'] = system_tessdata
    
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
    
    def initialize_tesseract_with_hint(self, cmd_path: str) -> bool:
        """
        Initialize Tesseract using an explicitly provided executable path.
        Used when the user manually browses to tesseract.exe.

        Args:
            cmd_path: Absolute path to tesseract.exe

        Returns:
            True if initialization succeeded, False otherwise
        """
        if not os.path.exists(cmd_path):
            self.logger.error(f"Provided Tesseract path does not exist: {cmd_path}")
            return False

        pytesseract.pytesseract.tesseract_cmd = cmd_path
        self.resolved_cmd = cmd_path

        tessdata_dir = self._derive_tessdata_dir(cmd_path)
        if tessdata_dir:
            self.resolved_tessdata = tessdata_dir
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
        else:
            self.resolved_tessdata = TESSDATA_PREFIX
            os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX

        version = self.get_tesseract_version()
        if version:
            self.logger.info(f"Tesseract initialized from user-provided path: {version}")
            self.tesseract_initialized = True
            try:
                TESSERACT_PATH_CACHE.parent.mkdir(parents=True, exist_ok=True)
                TESSERACT_PATH_CACHE.write_text(cmd_path, encoding='utf-8')
            except Exception as e:
                self.logger.debug(f"Could not write Tesseract path cache: {e}")
            return True

        self.logger.error(f"Tesseract at {cmd_path} failed version check")
        return False

    def _try_winget_install(self) -> bool:
        """
        Try to install Tesseract via winget (no UAC elevation required).

        Uses --scope user so the install goes into AppData, and works through
        the Windows Update infrastructure which is typically allowed on
        corporate networks.

        Returns:
            True if winget install succeeded, False otherwise.
        """
        winget_cmd = shutil.which('winget')
        if not winget_cmd:
            self.logger.info("winget not found in PATH, skipping")
            return False
        try:
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

            self.logger.info("Installing Tesseract via winget --scope user ...")
            result = subprocess.run(
                [
                    winget_cmd, 'install',
                    '--id', 'UB-Mannheim.TesseractOCR',
                    '--scope', 'user',
                    '--silent',
                    '--accept-package-agreements',
                    '--accept-source-agreements',
                ],
                capture_output=True,
                text=True,
                timeout=300,
                startupinfo=startupinfo,
            )
            if result.returncode == 0:
                self.logger.info(f"winget install succeeded: {result.stdout.strip()}")
                return True
            self.logger.warning(
                f"winget install failed (rc={result.returncode}): {result.stderr.strip()}"
            )
            return False
        except Exception as e:
            self.logger.error(f"winget install error: {e}")
            return False

    def _try_brew_install(self) -> bool:
        """
        Try to install Tesseract via Homebrew on macOS.

        Returns:
            True if the brew install succeeded, False otherwise.
        """
        brew_cmd = shutil.which('brew')
        if not brew_cmd:
            # GUI apps don't inherit the shell PATH — check known locations
            for candidate in ('/opt/homebrew/bin/brew', '/usr/local/bin/brew'):
                if os.path.exists(candidate):
                    brew_cmd = candidate
                    break
        if not brew_cmd:
            self.logger.info("Homebrew not found, skipping brew install")
            return False

        try:
            self.logger.info("Installing Tesseract via Homebrew ...")
            result = subprocess.run(
                [brew_cmd, 'install', 'tesseract'],
                capture_output=True,
                text=True,
                timeout=900,
            )
            if result.returncode == 0:
                self.logger.info("brew install tesseract succeeded")
                return True
            self.logger.warning(
                f"brew install failed (rc={result.returncode}): {result.stderr.strip()}"
            )
            return False
        except Exception as e:
            self.logger.error(f"brew install error: {e}")
            return False

    def _try_installer_download(self) -> bool:
        """
        Download and run the official Tesseract installer from GitHub.

        Installs to %LOCALAPPDATA%\\Programs\\Tesseract-OCR to avoid UAC.
        Note: if the Inno Setup installer enforces admin rights internally,
        this may still fail on locked-down machines.

        Returns:
            True if installation succeeded, False otherwise.
        """
        try:
            import tempfile
            import urllib.request
            import hashlib
            import time

            installer_url = TESSERACT_INSTALLER_URL
            if not _is_trusted_installer_url(installer_url):
                self.logger.error(
                    f"Refusing to download installer from untrusted URL: {installer_url}"
                )
                return False

            local_app_data = os.environ.get('LOCALAPPDATA', '')
            install_dir = (
                Path(local_app_data) / 'Programs' / 'Tesseract-OCR'
                if local_app_data
                else Path(TESSERACT_CMD).parent
            )
            self.logger.info(f"Tesseract will be installed to: {install_dir}")

            with tempfile.TemporaryDirectory(prefix="tesseract_install_") as temp_dir:
                installer_path = Path(temp_dir) / "tesseract-installer.exe"

                self.logger.info("Downloading Tesseract installer...")
                try:
                    with urllib.request.urlopen(installer_url, timeout=300) as response:
                        final_url = response.geturl()
                        if not _is_trusted_installer_url(final_url):
                            self.logger.error(
                                f"Installer redirected to untrusted URL: {final_url}"
                            )
                            return False
                        installer_data = response.read()
                        with open(installer_path, 'wb') as f:
                            f.write(installer_data)
                except Exception as e:
                    self.logger.error(f"Download failed: {e}")
                    return False

                if len(installer_data) < TESSERACT_INSTALLER_MIN_SIZE_BYTES:
                    self.logger.error(
                        f"Downloaded file too small ({len(installer_data)} bytes). "
                        "Installation aborted — download may be corrupt."
                    )
                    return False

                sha256_hash = hashlib.sha256(installer_data).hexdigest()
                self.logger.info(
                    f"Installer downloaded ({len(installer_data)} bytes, SHA256: {sha256_hash})"
                )

                self.logger.info("Running Tesseract installer...")
                try:
                    subprocess.run(
                        [str(installer_path), "/SILENT", "/NORESTART",
                         f"/DIR={install_dir}"],
                        check=True,
                        timeout=300,
                    )
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Installer process failed (rc={e.returncode})")
                    return False

                expected_exe = install_dir / 'tesseract.exe'
                for _ in range(120):
                    if os.path.exists(expected_exe) or self._resolve_tesseract_cmd() is not None:
                        time.sleep(2)
                        self.logger.info("Tesseract installation completed")
                        return self.initialize_tesseract()
                    time.sleep(1)

                self.logger.error("Tesseract installation timed out")
                return False

        except Exception as e:
            self.logger.error(f"Installer download/run error: {e}")
            return False

    def install_tesseract(self) -> bool:
        """
        Attempt to install Tesseract automatically.

        Windows: tries winget first (no UAC, corporate-network friendly),
        then falls back to downloading the official Inno Setup installer.
        macOS: installs via Homebrew when available.

        Returns:
            True if installation successful, False otherwise
        """
        if sys.platform not in ('win32', 'darwin'):
            self.logger.error("Automatic Tesseract installation not supported on this platform")
            return False

        try:
            import time
            from tkinter import messagebox

            self.logger.info("Starting Tesseract installation...")

            if sys.platform == 'darwin':
                install_detail = (
                    "It will be installed via Homebrew "
                    "(no administrator rights required)."
                )
            else:
                install_detail = (
                    "It will be installed automatically for the current user "
                    "(no administrator rights required)."
                )

            consent = messagebox.askyesno(
                "Install Tesseract OCR",
                (
                    "CaptiOCR needs Tesseract OCR to work.\n\n"
                    f"{install_detail}\n\n"
                    "Do you want to continue?"
                ),
            )
            if not consent:
                self.logger.info("User declined Tesseract installation")
                return False

            if sys.platform == 'darwin':
                if self._try_brew_install():
                    time.sleep(1)
                    return self.initialize_tesseract()
                return False

            # 1. Try winget (preferred: no UAC, corporate-friendly)
            if self._try_winget_install():
                time.sleep(2)
                return self.initialize_tesseract()

            # 2. Fall back to direct installer download
            self.logger.info("winget unavailable or failed — trying direct download")
            return self._try_installer_download()

        except Exception as e:
            self.logger.error(f"Error installing Tesseract: {e}")
            return False