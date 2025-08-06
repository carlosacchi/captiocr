"""
Logging configuration and utilities.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.constants import LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT


class LoggerSetup:
    """Configure and manage application logging."""
    
    _instance: Optional['LoggerSetup'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'LoggerSetup':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize logger setup."""
        if self._logger is None:
            self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Set up the logging configuration."""
        # Create logs directory if it doesn't exist
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create timestamp for log filename
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_filename = f"captiocr_{timestamp}.log"
        log_filepath = LOGS_DIR / log_filename
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Get logger instance
        self._logger = logging.getLogger('CaptiOCR')
        
        # Log initialization message WITHOUT using app_info here
        self._logger.info(f"Logging initialized. Log file: {log_filepath}")
    
    @classmethod
    def get_logger(cls, name: str = 'CaptiOCR') -> logging.Logger:
        """
        Get a logger instance.
        
        Args:
            name: Logger name
            
        Returns:
            Logger instance
        """
        instance = cls()
        return logging.getLogger(name)
    
    @classmethod
    def setup_debug_logging(cls, enabled: bool = True) -> None:
        """
        Enable or disable debug logging.
        
        Args:
            enabled: Whether to enable debug logging
        """
        logger = cls.get_logger()
        if enabled:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        else:
            logger.setLevel(logging.INFO)
            logger.info("Debug logging disabled")


def get_logger(name: str = 'CaptiOCR') -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return LoggerSetup.get_logger(name)


def log_exception(logger: logging.Logger, exception: Exception, 
                  message: str = "An error occurred") -> None:
    """
    Log an exception with traceback.
    
    Args:
        logger: Logger instance
        exception: Exception to log
        message: Additional context message
    """
    logger.error(f"{message}: {str(exception)}", exc_info=True)