"""
Data models for capture configuration.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable
import logging

from ..config.constants import (
    DEFAULT_MIN_CAPTURE_INTERVAL,
    DEFAULT_MAX_CAPTURE_INTERVAL,
    MAX_SIMILAR_CAPTURES,
    DEFAULT_MIN_DELTA_WORDS,
    DEFAULT_RECENT_TEXTS_WINDOW_SIZE,
    DEFAULT_DELTA_BUFFER_THRESHOLD,
    DEFAULT_INCREMENTAL_THRESHOLD,
    POST_PROCESS_DEDUP_ENTER_THRESHOLD,
    POST_PROCESS_DEDUP_EXIT_THRESHOLD,
    POST_PROCESS_MIN_LENGTH_RATIO,
    POST_PROCESS_MIN_NEW_WORDS,
    POST_PROCESS_FRAME_CONSENSUS_WINDOW,
    POST_PROCESS_MIN_SENTENCE_WORDS
)


@dataclass
class CaptureConfig:
    """Configuration for screen capture settings."""

    min_capture_interval: float = DEFAULT_MIN_CAPTURE_INTERVAL
    max_capture_interval: float = DEFAULT_MAX_CAPTURE_INTERVAL
    current_interval: float = DEFAULT_MIN_CAPTURE_INTERVAL
    max_similar_captures: int = MAX_SIMILAR_CAPTURES

    # Delta extraction sensitivity parameters
    min_delta_words: int = DEFAULT_MIN_DELTA_WORDS
    recent_texts_window_size: int = DEFAULT_RECENT_TEXTS_WINDOW_SIZE
    delta_buffer_threshold: int = DEFAULT_DELTA_BUFFER_THRESHOLD
    incremental_threshold: float = DEFAULT_INCREMENTAL_THRESHOLD

    # Post-processing pipeline parameters
    post_process_dedup_enter: float = POST_PROCESS_DEDUP_ENTER_THRESHOLD
    post_process_dedup_exit: float = POST_PROCESS_DEDUP_EXIT_THRESHOLD
    post_process_min_length_ratio: float = POST_PROCESS_MIN_LENGTH_RATIO
    post_process_min_new_words: int = POST_PROCESS_MIN_NEW_WORDS
    post_process_frame_window: int = POST_PROCESS_FRAME_CONSENSUS_WINDOW
    post_process_min_sentence_words: int = POST_PROCESS_MIN_SENTENCE_WORDS

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
            'max_similar_captures': self.max_similar_captures,
            'min_delta_words': self.min_delta_words,
            'recent_texts_window_size': self.recent_texts_window_size,
            'delta_buffer_threshold': self.delta_buffer_threshold,
            'incremental_threshold': self.incremental_threshold,
            'post_process_dedup_enter': self.post_process_dedup_enter,
            'post_process_dedup_exit': self.post_process_dedup_exit,
            'post_process_min_length_ratio': self.post_process_min_length_ratio,
            'post_process_min_new_words': self.post_process_min_new_words,
            'post_process_frame_window': self.post_process_frame_window,
            'post_process_min_sentence_words': self.post_process_min_sentence_words
        }
    
    def from_dict(self, config_dict: dict) -> None:
        """
        Load settings from dictionary with validation.

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

        # Load and validate delta extraction sensitivity parameters
        if 'min_delta_words' in config_dict:
            value = config_dict['min_delta_words']
            if isinstance(value, int) and 1 <= value <= 100:
                self.min_delta_words = value
            else:
                self._logger.warning(f"Invalid min_delta_words value: {value}, using default")
                self.min_delta_words = DEFAULT_MIN_DELTA_WORDS

        if 'recent_texts_window_size' in config_dict:
            value = config_dict['recent_texts_window_size']
            if isinstance(value, int) and 1 <= value <= 50:
                self.recent_texts_window_size = value
            else:
                self._logger.warning(f"Invalid recent_texts_window_size value: {value}, using default")
                self.recent_texts_window_size = DEFAULT_RECENT_TEXTS_WINDOW_SIZE

        if 'delta_buffer_threshold' in config_dict:
            value = config_dict['delta_buffer_threshold']
            if isinstance(value, int) and 1 <= value <= 20:
                self.delta_buffer_threshold = value
            else:
                self._logger.warning(f"Invalid delta_buffer_threshold value: {value}, using default")
                self.delta_buffer_threshold = DEFAULT_DELTA_BUFFER_THRESHOLD

        if 'incremental_threshold' in config_dict:
            value = config_dict['incremental_threshold']
            if isinstance(value, (int, float)) and 0.0 <= value <= 1.0:
                self.incremental_threshold = float(value)
            else:
                self._logger.warning(f"Invalid incremental_threshold value: {value}, using default")
                self.incremental_threshold = DEFAULT_INCREMENTAL_THRESHOLD

        # Load and validate post-processing pipeline parameters
        if 'post_process_dedup_enter' in config_dict:
            value = config_dict['post_process_dedup_enter']
            if isinstance(value, (int, float)) and 0.50 <= value <= 0.95:
                self.post_process_dedup_enter = float(value)
            else:
                self._logger.warning(f"Invalid post_process_dedup_enter: {value}, using default")
                self.post_process_dedup_enter = POST_PROCESS_DEDUP_ENTER_THRESHOLD

        if 'post_process_dedup_exit' in config_dict:
            value = config_dict['post_process_dedup_exit']
            if isinstance(value, (int, float)) and 0.30 <= value <= 0.80:
                self.post_process_dedup_exit = float(value)
            else:
                self._logger.warning(f"Invalid post_process_dedup_exit: {value}, using default")
                self.post_process_dedup_exit = POST_PROCESS_DEDUP_EXIT_THRESHOLD

        # Enforce hysteresis gap: exit must be lower than enter
        if self.post_process_dedup_exit >= self.post_process_dedup_enter:
            self._logger.warning("dedup_exit >= dedup_enter, resetting to defaults")
            self.post_process_dedup_enter = POST_PROCESS_DEDUP_ENTER_THRESHOLD
            self.post_process_dedup_exit = POST_PROCESS_DEDUP_EXIT_THRESHOLD

        if 'post_process_min_length_ratio' in config_dict:
            value = config_dict['post_process_min_length_ratio']
            if isinstance(value, (int, float)) and 0.30 <= value <= 0.90:
                self.post_process_min_length_ratio = float(value)
            else:
                self._logger.warning(f"Invalid post_process_min_length_ratio: {value}, using default")
                self.post_process_min_length_ratio = POST_PROCESS_MIN_LENGTH_RATIO

        if 'post_process_min_new_words' in config_dict:
            value = config_dict['post_process_min_new_words']
            if isinstance(value, int) and 1 <= value <= 10:
                self.post_process_min_new_words = value
            else:
                self._logger.warning(f"Invalid post_process_min_new_words: {value}, using default")
                self.post_process_min_new_words = POST_PROCESS_MIN_NEW_WORDS

        if 'post_process_frame_window' in config_dict:
            value = config_dict['post_process_frame_window']
            if isinstance(value, int) and 2 <= value <= 5:
                self.post_process_frame_window = value
            else:
                self._logger.warning(f"Invalid post_process_frame_window: {value}, using default")
                self.post_process_frame_window = POST_PROCESS_FRAME_CONSENSUS_WINDOW

        if 'post_process_min_sentence_words' in config_dict:
            value = config_dict['post_process_min_sentence_words']
            if isinstance(value, int) and 1 <= value <= 10:
                self.post_process_min_sentence_words = value
            else:
                self._logger.warning(f"Invalid post_process_min_sentence_words: {value}, using default")
                self.post_process_min_sentence_words = POST_PROCESS_MIN_SENTENCE_WORDS