"""
Screen capture functionality.
"""
import time
import threading
from typing import Optional, Tuple, Callable
from collections import deque
from datetime import datetime
import logging

try:
    from PIL import ImageGrab
    import keyboard
except ImportError as e:
    logging.error(f"Required package not found: {e}")
    raise

from .ocr import OCRProcessor
from .text_processor import TextProcessor
from ..models.capture_config import CaptureConfig
from ..utils.file_manager import FileManager
from ..config.constants import TIMESTAMP_FORMAT
from ..config.constants import CAPTURES_DIR


class ScreenCapture:
    """Handle screen capture and OCR processing."""
    
    def __init__(self, ocr_processor: OCRProcessor, text_processor: TextProcessor,
                capture_config: CaptureConfig):
        """
        Initialize screen capture.
        
        Args:
            ocr_processor: OCR processor instance
            text_processor: Text processor instance
            capture_config: Capture configuration
        """
        self.ocr_processor = ocr_processor
        self.text_processor = text_processor
        self.capture_config = capture_config
        self.logger = logging.getLogger('CaptiOCR.ScreenCapture')
        
        # Capture state
        self.capture_area: Optional[Tuple[int, int, int, int]] = None
        self.capture_thread: Optional[threading.Thread] = None
        self.capture_stop_flag = False
        self.stop_event = threading.Event()
        
        # File management
        self.file_manager = FileManager()
        self.current_capture_timestamp: Optional[str] = None
        self.output_file_path: Optional[str] = None
        
        # Text history
        self.text_history = deque(maxlen=5)
        
        # Callbacks
        self.on_text_captured: Optional[Callable[[str], None]] = None
        self.on_status_update: Optional[Callable[[str], None]] = None
    
    def set_capture_area(self, area: Tuple[int, int, int, int]) -> None:
        """
        Set the screen area to capture.
        
        Args:
            area: Tuple of (x1, y1, x2, y2) coordinates
        """
        self.capture_area = area
        self.logger.info(f"Capture area set to: {area}")
    
    def start_capture(self, language: str = "eng", caption_mode: bool = False) -> bool:
        """
        Start the capture process.
        
        Args:
            language: Language code for OCR
            caption_mode: Whether to use caption-optimized settings
            
        Returns:
            True if capture started successfully
        """
        if not self.capture_area:
            self.logger.error("No capture area set")
            return False
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.logger.warning("Capture already in progress")
            return False
        
        # Reset state
        self.capture_stop_flag = False
        self.stop_event.clear()
        self.text_history.clear()
        
        # Create output file
        self.current_capture_timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        filename = self.file_manager.create_capture_filename(self.current_capture_timestamp)
        self.output_file_path = CAPTURES_DIR / filename
        
        # Write header
        with open(self.output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Caption capture started: {datetime.now()}\n")
            f.write(f"Language: {language}\n")
            f.write(f"Caption mode: {caption_mode}\n\n")
        
        # Start capture thread
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(language, caption_mode),
            daemon=True
        )
        self.capture_thread.start()
        
        self.logger.info(f"Capture started with language: {language}")
        return True
    
    def stop_capture(self) -> Optional[str]:
        """
        Stop the capture process.
        
        Returns:
            Path to the captured file or None
        """
        self.logger.info("Stopping capture...")
        
        # Set stop flags
        self.capture_stop_flag = True
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
            if self.capture_thread.is_alive():
                self.logger.warning("Capture thread did not terminate in time")
        
        self.capture_thread = None
        
        # Return the output file path
        return str(self.output_file_path) if self.output_file_path else None
    
    def _capture_loop(self, language: str, caption_mode: bool) -> None:
        """
        Main capture loop running in a separate thread.
        
        Args:
            language: Language code for OCR
            caption_mode: Whether to use caption-optimized settings
        """
        try:
            last_text = ""
            similar_captures_count = 0
            capture_interval = self.capture_config.reset_interval()
            
            # Start keyboard monitoring thread
            stop_key_thread = threading.Thread(
                target=self._monitor_stop_key,
                daemon=True
            )
            stop_key_thread.start()
            
            while not self.capture_stop_flag:
                try:
                    # Capture screenshot
                    screenshot = ImageGrab.grab(bbox=self.capture_area)
                    
                    # Optimize image if needed
                    screenshot = self.ocr_processor.optimize_image_for_ocr(screenshot)
                    
                    # Perform OCR
                    raw_text = self.ocr_processor.process_image(
                        screenshot, language, caption_mode
                    )
                    self.logger.debug(f"Raw OCR result (length: {len(raw_text)}): '{raw_text[:100]}...'")
                    
                    # Clean text
                    text = self.text_processor.clean_text(raw_text)
                    self.logger.debug(f"Cleaned text (length: {len(text)}): '{text[:100]}...'")
                    
                    # Check for significant new content
                    has_new_content = self.text_processor.has_significant_new_content(text, last_text)
                    self.logger.debug(f"Has significant new content: {has_new_content} (similarity threshold: {self.text_processor.similarity_threshold})")
                    
                    if text and has_new_content:
                        # Save to file
                        with open(self.output_file_path, 'a', encoding='utf-8') as f:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            f.write(f"[{timestamp}] {text}\n")
                        
                        # Update state
                        last_text = text
                        self.text_history.append(text)
                        similar_captures_count = 0
                        capture_interval = self.capture_config.reset_interval()
                        
                        # Notify callbacks
                        if self.on_text_captured:
                            self.on_text_captured(text)
                        
                        self.logger.debug(f"Captured text: {text[:50]}...")
                    else:
                        # Adjust interval for repeated content
                        similar_captures_count += 1
                        if similar_captures_count > self.capture_config.max_similar_captures:
                            capture_interval = self.capture_config.increase_interval()
                    
                    # Sleep based on current interval
                    time.sleep(capture_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in capture iteration: {e}")
                    time.sleep(1)  # Sleep on error to avoid rapid loops
            
            self.logger.info("Capture loop ended")
            
        except Exception as e:
            self.logger.error(f"Critical error in capture loop: {e}")
            if self.on_status_update:
                self.on_status_update(f"Capture error: {str(e)}")
    
    def _monitor_stop_key(self) -> None:
        """Monitor for stop key press (Ctrl+Q)."""
        try:
            while not self.stop_event.is_set():
                if keyboard.is_pressed('ctrl+q'):
                    self.logger.info("Stop key pressed (Ctrl+Q)")
                    self.capture_stop_flag = True
                    break
                time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error monitoring stop key: {e}")
    
    def process_capture_file(self, filepath: str, custom_name: Optional[str] = None) -> Optional[str]:
        """
        Post-process a capture file to remove duplicates.
        
        Args:
            filepath: Path to the capture file
            custom_name: Optional custom name for the processed file
            
        Returns:
            Path to the processed file or None
        """
        try:
            self.logger.info(f"Processing capture file: {filepath}")
            
            # Read the file
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Extract timestamp blocks
            blocks = []
            current_block = []
            timestamp_pattern = r'^\[\d{2}:\d{2}:\d{2}\]'
            
            import re
            for line in lines:
                if re.match(timestamp_pattern, line):
                    if current_block:
                        blocks.append(current_block)
                    current_block = [line]
                elif current_block:
                    current_block.append(line)
            
            if current_block:
                blocks.append(current_block)
            
            # Filter duplicates
            if not blocks:
                self.logger.warning("No text blocks found in capture file")
                return None
            
            # Convert blocks to (timestamp, text) tuples
            text_blocks = []
            for block in blocks:
                if block:
                    timestamp = block[0].split(']')[0] + ']'
                    text = ''.join(block).replace(timestamp, '').strip()
                    text_blocks.append((timestamp, text))
            
            # Filter duplicates
            unique_blocks = self.text_processor.filter_duplicate_blocks(text_blocks)
            
            # Create processed filename
            timestamp = self.current_capture_timestamp or datetime.now().strftime(TIMESTAMP_FORMAT)
            processed_filename = self.file_manager.create_capture_filename(
                timestamp, custom_name, processed=True
            )
            processed_filepath = self.file_manager.CAPTURES_DIR / processed_filename
            
            # Write processed content
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                for timestamp, text in unique_blocks:
                    f.write(f"{timestamp} {text}\n")
            
            self.logger.info(
                f"Processed file saved: {processed_filepath} "
                f"({len(blocks)} -> {len(unique_blocks)} blocks)"
            )
            
            return str(processed_filepath)
            
        except Exception as e:
            self.logger.error(f"Error processing capture file: {e}")
            return None