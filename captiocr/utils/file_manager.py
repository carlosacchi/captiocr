"""
File and directory management utilities.
"""
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, List
import logging

from ..config.constants import (
    CAPTURES_DIR, CONFIG_DIR, LOGS_DIR, RESOURCES_DIR, TESSDATA_DIR,
    CAPTURE_FILE_PREFIX, PROCESSED_FILE_SUFFIX, TIMESTAMP_FORMAT
)


class FileManager:
    """Manage application files and directories."""

    # Class attributes for directories
    CAPTURES_DIR = CAPTURES_DIR
    CONFIG_DIR = CONFIG_DIR
    LOGS_DIR = LOGS_DIR
    RESOURCES_DIR = RESOURCES_DIR
    TESSDATA_DIR = TESSDATA_DIR
    
    def __init__(self):
        """Initialize file manager."""
        self.logger = logging.getLogger('CaptiOCR.FileManager')
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            CAPTURES_DIR,
            CONFIG_DIR,
            LOGS_DIR,
            RESOURCES_DIR,
            TESSDATA_DIR
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                self.logger.error(f"Failed to create directory {directory}: {e}")
    
    @staticmethod
    def open_directory(directory: Path) -> None:
        """
        Open a directory in the system file explorer.
        
        Args:
            directory: Path to directory to open
            
        Raises:
            OSError: If directory cannot be opened
        """
        if not directory.exists():
            raise OSError(f"Directory does not exist: {directory}")
        
        system = platform.system()
        
        if system == "Windows":
            os.startfile(str(directory))
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", str(directory)])
        else:  # Linux and other Unix-like
            subprocess.Popen(["xdg-open", str(directory)])
    
    @staticmethod
    def get_capture_files(processed_only: bool = False) -> List[Path]:
        """
        Get list of capture files.
        
        Args:
            processed_only: If True, return only processed files
            
        Returns:
            List of file paths
        """
        if not CAPTURES_DIR.exists():
            return []
        
        pattern = f"{CAPTURE_FILE_PREFIX}*"
        
        if processed_only:
            pattern += f"*{PROCESSED_FILE_SUFFIX}.txt"
        else:
            pattern += ".txt"
        
        files = list(CAPTURES_DIR.glob(pattern))
        
        # Exclude already processed files if not specifically requested
        if not processed_only:
            files = [f for f in files if PROCESSED_FILE_SUFFIX not in f.name]
        
        return sorted(files, reverse=True)
    
    @staticmethod
    def get_latest_capture_file() -> Optional[Path]:
        """
        Get the most recent capture file.
        
        Returns:
            Path to latest file or None if no files exist
        """
        files = FileManager.get_capture_files(processed_only=False)
        return files[0] if files else None
    
    @staticmethod
    def create_capture_filename(timestamp: str, custom_name: Optional[str] = None, 
                                processed: bool = False) -> str:
        """
        Create a standardized capture filename.
        
        Args:
            timestamp: Timestamp string
            custom_name: Optional custom name prefix
            processed: Whether this is a processed file
            
        Returns:
            Formatted filename
        """
        if custom_name:
            base_name = f"{custom_name}_{CAPTURE_FILE_PREFIX}{timestamp}"
        else:
            base_name = f"{CAPTURE_FILE_PREFIX}{timestamp}"
        
        if processed:
            base_name += PROCESSED_FILE_SUFFIX
        
        return f"{base_name}.txt"
    
    @staticmethod
    def get_resource_path(filename: str) -> Path:
        """
        Get path to a resource file.
        
        Args:
            filename: Resource filename
            
        Returns:
            Full path to resource
        """
        return RESOURCES_DIR / filename
    
    @staticmethod
    def clean_old_logs(keep_recent: int = 10) -> None:
        """
        Clean old log files, keeping only the most recent ones.
        
        Args:
            keep_recent: Number of recent logs to keep
        """
        if not LOGS_DIR.exists():
            return
        
        log_files = sorted(
            LOGS_DIR.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Delete older log files
        for log_file in log_files[keep_recent:]:
            try:
                log_file.unlink()
                logging.getLogger('CaptiOCR.FileManager').info(
                    f"Deleted old log file: {log_file.name}"
                )
            except Exception as e:
                logging.getLogger('CaptiOCR.FileManager').error(
                    f"Failed to delete log file {log_file}: {e}"
                )