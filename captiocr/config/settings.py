"""
Application settings and preferences management.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from ..config.constants import CONFIG_DIR, TESSDATA_PREFIX
from ..models.capture_config import CaptureConfig


class Settings:
    """Manage application settings and preferences."""
    
    def __init__(self):
        """Initialize settings manager."""
        self.logger = logging.getLogger('CaptiOCR.Settings')
        self._ensure_config_dir()
        
        # Default settings
        self.language = "English"
        self.debug_enabled = False
        self.text_similarity_threshold = 0.8
        self.use_caption_mode = True  # Caption Mode is default
        self.custom_tessdata_path = ""
        
        # Monitor configuration
        self.monitors = {
            "primary": {"dpi": 96, "scale_factor": 1.0, "width": 1920, "height": 1080},
            "secondary": {"dpi": 96, "scale_factor": 1.0, "width": 0, "height": 0},
            "last_detected": None
        }
        
        # Capture configuration
        self.capture_config = CaptureConfig()
    
    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _sanitize_profile_name(self, profile_name: str) -> str:
        """
        Sanitize profile name to prevent path traversal attacks.

        Args:
            profile_name: User-provided profile name

        Returns:
            Sanitized profile name safe for filesystem use
        """
        import re
        # Remove any path separators and parent directory references
        sanitized = profile_name.replace('\\', '_').replace('/', '_').replace('..', '_')
        # Only allow alphanumeric, underscore, and hyphen
        sanitized = re.sub(r'[^\w\-]', '_', sanitized)
        # Ensure it's not empty
        if not sanitized or sanitized == '_':
            sanitized = 'default'
        return sanitized

    def get_profile_path(self, profile_name: str = "default") -> Path:
        """
        Get path to a settings profile file.

        Args:
            profile_name: Name of the profile

        Returns:
            Path to profile file
        """
        sanitized_name = self._sanitize_profile_name(profile_name)
        return CONFIG_DIR / f"{sanitized_name}_preferences.json"
    
    def update_monitor_config(self, monitor_manager) -> None:
        """
        Update monitor configuration from monitor manager.
        
        Args:
            monitor_manager: MonitorManager instance with detected monitors
        """
        try:
            primary_monitor = monitor_manager.get_primary_monitor()
            if primary_monitor:
                self.monitors["primary"] = {
                    "dpi": primary_monitor.dpi,
                    "scale_factor": primary_monitor.scale_factor,
                    "width": primary_monitor.width,
                    "height": primary_monitor.height
                }
                
            # Find secondary monitor (first non-primary)
            secondary_monitor = None
            for monitor in monitor_manager.monitors:
                if not monitor.primary:
                    secondary_monitor = monitor
                    break
                    
            if secondary_monitor:
                self.monitors["secondary"] = {
                    "dpi": secondary_monitor.dpi,
                    "scale_factor": secondary_monitor.scale_factor,
                    "width": secondary_monitor.width,
                    "height": secondary_monitor.height,
                    "x": secondary_monitor.x,
                    "y": secondary_monitor.y
                }
            else:
                # No secondary monitor
                self.monitors["secondary"] = {
                    "dpi": 96, "scale_factor": 1.0, 
                    "width": 0, "height": 0
                }
                
            self.monitors["last_detected"] = datetime.now().isoformat()
            
            self.logger.info(f"Monitor config updated: Primary={self.monitors['primary']}, "
                           f"Secondary={self.monitors['secondary']}")
            
        except Exception as e:
            self.logger.error(f"Error updating monitor config: {e}")
    
    def get_scale_factor_for_coordinates(self, x: int, y: int) -> float:
        """
        Get scale factor based on coordinates by checking monitor bounds.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Scale factor for the monitor containing these coordinates
        """
        # Check if coordinates are within secondary monitor bounds
        secondary = self.monitors["secondary"]
        if (secondary.get("width", 0) > 0 and secondary.get("height", 0) > 0):
            sec_x = secondary.get("x", 0)
            sec_y = secondary.get("y", 0)
            sec_width = secondary["width"]
            sec_height = secondary["height"]
            
            # Check if point is within secondary monitor bounds
            if (sec_x <= x < sec_x + sec_width and 
                sec_y <= y < sec_y + sec_height):
                self.logger.debug(f"Coordinates ({x}, {y}) on secondary monitor, scale={secondary['scale_factor']}")
                return secondary["scale_factor"]
        
        # Default to primary monitor
        self.logger.debug(f"Coordinates ({x}, {y}) on primary monitor, scale={self.monitors['primary']['scale_factor']}")
        return self.monitors["primary"]["scale_factor"]
    
    def save(self, profile_name: str = "default") -> bool:
        """
        Save current settings to a profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            True if successful, False otherwise
        """
        try:
            settings_dict = self.to_dict()
            settings_dict['profile_name'] = profile_name
            settings_dict['saved_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            profile_path = self.get_profile_path(profile_name)
            
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Settings saved to profile: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def load(self, profile_name: str = "default") -> bool:
        """
        Load settings from a profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            True if successful, False otherwise
        """
        try:
            profile_path = self.get_profile_path(profile_name)
            
            if not profile_path.exists():
                self.logger.warning(f"Profile not found: {profile_name}")
                return False
            
            with open(profile_path, 'r', encoding='utf-8') as f:
                settings_dict = json.load(f)
            
            self.from_dict(settings_dict)
            self.logger.info(f"Settings loaded from profile: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            return False
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        List all available settings profiles.
        
        Returns:
            List of profile information dictionaries
        """
        profiles = []
        
        for file_path in CONFIG_DIR.glob("*_preferences.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                profile_info = {
                    'name': data.get('profile_name', file_path.stem.replace('_preferences', '')),
                    'saved_date': data.get('saved_date', 'Unknown'),
                    'file_path': file_path
                }
                profiles.append(profile_info)
                
            except Exception as e:
                self.logger.warning(f"Error reading profile {file_path}: {e}")
        
        return sorted(profiles, key=lambda x: x['saved_date'], reverse=True)
    
    def save_last_config(self) -> bool:
        """
        Save current settings as last configuration.
        Used for automatic save on application close.
        
        Returns:
            True if successful, False otherwise
        """
        return self.save("lastconfig")
    
    def load_last_config(self) -> bool:
        """
        Load last configuration if available, fallback to default.
        Used for automatic load on application start.
        
        Returns:
            True if successful, False otherwise
        """
        # Try to load last config first
        if self.load("lastconfig"):
            self.logger.info("Loaded last configuration")
            return True
        
        # Fallback to default if last config doesn't exist
        if self.load("default"):
            self.logger.info("Loaded default configuration (last config not found)")
            return True
            
        self.logger.warning("No configuration files found, using built-in defaults")
        return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """
        Delete a settings profile.
        
        Args:
            profile_name: Name of the profile to delete
            
        Returns:
            True if successful, False otherwise
        """
        if profile_name == "default":
            self.logger.warning("Cannot delete default profile")
            return False
        
        try:
            profile_path = self.get_profile_path(profile_name)
            
            if profile_path.exists():
                profile_path.unlink()
                self.logger.info(f"Deleted profile: {profile_name}")
                return True
            else:
                self.logger.warning(f"Profile not found: {profile_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting profile: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert settings to dictionary.
        
        Returns:
            Dictionary representation of settings
        """
        return {
            'language': self.language,
            'debug_enabled': self.debug_enabled,
            'text_similarity_threshold': self.text_similarity_threshold,
            'use_caption_mode': self.use_caption_mode,
            'custom_tessdata_path': self.custom_tessdata_path,
            'monitors': self.monitors,
            **self.capture_config.to_dict()
        }
    
    def from_dict(self, settings_dict: Dict[str, Any]) -> None:
        """
        Load settings from dictionary.
        
        Args:
            settings_dict: Dictionary with settings values
        """
        # Load basic settings
        self.language = settings_dict.get('language', self.language)
        self.debug_enabled = settings_dict.get('debug_enabled', self.debug_enabled)
        self.text_similarity_threshold = settings_dict.get(
            'text_similarity_threshold', self.text_similarity_threshold
        )
        self.use_caption_mode = settings_dict.get('use_caption_mode', self.use_caption_mode)
        
        # Load custom tessdata path
        custom_path = settings_dict.get('custom_tessdata_path', '')
        if custom_path and os.path.isdir(custom_path):
            self.custom_tessdata_path = custom_path
            os.environ['TESSDATA_PREFIX'] = custom_path
            self.logger.info(f"Custom tessdata path set: {custom_path}")
        
        # Load monitor configuration
        if 'monitors' in settings_dict:
            self.monitors = settings_dict['monitors']
            self.logger.info(f"Loaded monitor config: {self.monitors}")
        
        # Load capture configuration
        self.capture_config.from_dict(settings_dict)
    
    def apply_debug_mode(self) -> None:
        """Apply debug mode settings to the application."""
        from ..utils.logger import LoggerSetup
        LoggerSetup.setup_debug_logging(self.debug_enabled)