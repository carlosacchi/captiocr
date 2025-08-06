"""
Centralized application information loader.
All app metadata is loaded from external configuration files.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


class AppInfo:
    """Singleton class to manage application information."""
    
    _instance = None
    _info: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_info()
        return cls._instance
    
    def _load_info(self):
        """Load application info from configuration files."""
        # Try to find configuration files
        base_paths = [
            Path(__file__).parent.parent.parent,  # Project root
            Path(__file__).parent.parent,          # captiocr directory
            Path(os.getcwd()),                     # Current directory
        ]
        
        # First try JSON format
        for base_path in base_paths:
            json_path = base_path / "app_info.json"
            if json_path.exists():
                self._load_from_json(json_path)
                return
        
        # Fallback to version.txt format
        for base_path in base_paths:
            txt_path = base_path / "version.txt"
            if txt_path.exists():
                self._load_from_txt(txt_path)
                return
        
        # Ultimate fallback
        self._set_defaults()
    
    def _load_from_json(self, path: Path):
        """Load info from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._info = json.load(f)
            print(f"Loaded app info from: {path}")
        except Exception as e:
            print(f"Error loading JSON config: {e}")
            self._set_defaults()
    
    def _load_from_txt(self, path: Path):
        """Load info from version.txt format."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            # Initialize with defaults
            self._info = {
                'version': 'unknown',
                'date': '',
                'app_name': 'CaptiOCR',
                'author': 'Unknown',
                'email': '',
                'url': '',
            }
            
            # Parse based on line position and content
            for i, line in enumerate(lines):
                if i == 0:  # Version
                    self._info['version'] = line
                elif i == 1:  # Date
                    self._info['date'] = line
                elif i == 2:  # App name
                    self._info['app_name'] = line
                elif line.startswith('Author:'):
                    self._info['author'] = line.replace('Author:', '').strip()
                elif line.startswith('Website:'):
                    self._info['url'] = line.replace('Website:', '').strip()
                elif line.startswith('Email:'):
                    self._info['email'] = line.replace('Email:', '').strip()
            
            print(f"Loaded app info from: {path}")
            print(f"Parsed: {self._info}")
        except Exception as e:
            print(f"Error loading TXT config: {e}")
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default values if no config found."""
        self._info = {
            'version': 'v0.0.1',
            'date': 'unknown',
            'app_name': 'CaptiOCR',
            'author': 'Unknown',
            'email': '',
            'url': '',
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._info.get(key, default)
    
    @property
    def version(self) -> str:
        return self._info.get('version', 'unknown')
    
    @property
    def date(self) -> str:
        return self._info.get('date', '')
    
    @property
    def app_name(self) -> str:
        return self._info.get('app_name', 'CaptiOCR')
    
    @property
    def author(self) -> str:
        return self._info.get('author', 'Unknown')
    
    @property
    def email(self) -> str:
        return self._info.get('email', '')
    
    @property
    def url(self) -> str:
        return self._info.get('url', '')
    
    @property
    def version_string(self) -> str:
        """Get formatted version string with date."""
        if self.date:
            return f"{self.version} ({self.date})"
        return self.version
    
    def reload(self):
        """Reload configuration from files."""
        self._load_info()


# Global instance
app_info = AppInfo()