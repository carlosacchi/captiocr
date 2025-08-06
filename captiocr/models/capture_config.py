"""
Data models for capture configuration.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable
import logging

from ..config.constants import (
    DEFAULT_MIN_CAPTURE_INTERVAL,
    DEFAULT_MAX_CAPTURE_INTERVAL,
    MAX_SIMILAR_CAPTURES
)


@dataclass
class CaptureConfig:
    """Configuration for screen capture settings."""
    
    min_capture_interval: float = DEFAULT_MIN_CAPTURE_INTERVAL
    max_capture_interval: float = DEFAULT_MAX_CAPTURE_INTERVAL
    current_interval: float = DEFAULT_MIN_CAPTURE_INTERVAL
    max_similar_captures: int = MAX_SIMILAR_CAPTURES
    
    # Callbacks
    on_interval_change: Optional[Callable[[float], None]] = field(default=None, repr=False)
    
    # Logger
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger('CaptiOCR.CaptureConfig'), repr=False)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_intervals()
    
    def _validate_intervals(self) -> None:
        """Validate interval values."""
        if self.min_capture_interval >= self.max_capture_interval:
            raise ValueError("Minimum interval must be smaller than maximum interval")
        if self.min_capture_interval < 0.5:
            raise ValueError("Minimum interval cannot be less than 0.5 seconds")
        
        # Ensure current interval is within bounds
        self.current_interval = max(
            self.min_capture_interval,
            min(self.current_interval, self.max_capture_interval)
        )
    
    def set_intervals(self, min_interval: float, max_interval: float) -> None:
        """
        Set min and max intervals with validation.
        
        Args:
            min_interval: Minimum capture interval in seconds
            max_interval: Maximum capture interval in seconds
            
        Raises:
            ValueError: If intervals are invalid
        """
        old_min = self.min_capture_interval
        old_max = self.max_capture_interval
        
        self.min_capture_interval = min_interval
        self.max_capture_interval = max_interval
        
        try:
            self._validate_intervals()
        except ValueError:
            # Restore old values on validation failure
            self.min_capture_interval = old_min
            self.max_capture_interval = old_max
            raise
        
        self._logger.info(
            f"Capture interval settings updated: "
            f"Min: {old_min:.1f}s -> {min_interval:.1f}s, "
            f"Max: {old_max:.1f}s -> {max_interval:.1f}s"
        )
        
        # Reset current interval to minimum
        old_current = self.current_interval
        self.current_interval = self.min_capture_interval
        
        if old_current != self.current_interval:
            self._logger.info(
                f"Current capture interval reset: {old_current:.1f}s -> {self.current_interval:.1f}s"
            )
            self._notify_interval_change()
    
    def increase_interval(self) -> float:
        """
        Increase the current capture interval.
        
        Returns:
            New interval value
        """
        old_interval = self.current_interval
        self.current_interval = min(self.current_interval + 1.0, self.max_capture_interval)
        
        if old_interval != self.current_interval:
            self._logger.info(
                f"Increased capture interval: {old_interval:.1f}s -> {self.current_interval:.1f}s"
            )
            self._notify_interval_change()
        
        return self.current_interval
    
    def decrease_interval(self) -> float:
        """
        Decrease the current capture interval.
        
        Returns:
            New interval value
        """
        old_interval = self.current_interval
        self.current_interval = max(self.current_interval - 0.5, self.min_capture_interval)
        
        if old_interval != self.current_interval:
            self._logger.info(
                f"Decreased capture interval: {old_interval:.1f}s -> {self.current_interval:.1f}s"
            )
            self._notify_interval_change()
        
        return self.current_interval
    
    def reset_interval(self) -> float:
        """
        Reset the current capture interval to minimum.
        
        Returns:
            New interval value
        """
        old_interval = self.current_interval
        self.current_interval = self.min_capture_interval
        
        if old_interval != self.current_interval:
            self._logger.info(
                f"Reset capture interval: {old_interval:.1f}s -> {self.current_interval:.1f}s"
            )
            self._notify_interval_change()
        
        return self.current_interval
    
    def set_max_similar_captures(self, count: int) -> None:
        """
        Set the number of similar captures before increasing interval.
        
        Args:
            count: Number of similar captures threshold
        """
        if count < 1:
            raise ValueError("Max similar captures must be at least 1")
        
        old_count = self.max_similar_captures
        self.max_similar_captures = count
        
        if old_count != self.max_similar_captures:
            self._logger.info(
                f"Max similar captures changed: {old_count} -> {self.max_similar_captures}"
            )
    
    def _notify_interval_change(self) -> None:
        """Notify callback about interval change."""
        if callable(self.on_interval_change):
            try:
                self.on_interval_change(self.current_interval)
            except Exception as e:
                self._logger.error(f"Error in interval change callback: {e}")
    
    def to_dict(self) -> dict:
        """
        Convert settings to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'min_capture_interval': self.min_capture_interval,
            'max_capture_interval': self.max_capture_interval,
            'max_similar_captures': self.max_similar_captures
        }
    
    def from_dict(self, config_dict: dict) -> None:
        """
        Load settings from dictionary.
        
        Args:
            config_dict: Dictionary with configuration values
        """
        if 'min_capture_interval' in config_dict and 'max_capture_interval' in config_dict:
            self.set_intervals(
                config_dict['min_capture_interval'],
                config_dict['max_capture_interval']
            )
        
        if 'max_similar_captures' in config_dict:
            self.set_max_similar_captures(config_dict['max_similar_captures'])