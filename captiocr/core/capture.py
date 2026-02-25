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
except ImportError as e:
    logging.error(f"Required package not found: {e}")
    raise

from .ocr import OCRProcessor
from .text_processor import TextProcessor
from ..models.capture_config import CaptureConfig
from ..utils.file_manager import FileManager
from ..config.constants import TIMESTAMP_FORMAT, APP_VERSION
from ..config.constants import CAPTURES_DIR, MONITOR_DISCONNECTION_CHECK_INTERVAL


class ScreenCapture:
    """Handle screen capture and OCR processing."""
    
    def __init__(self, ocr_processor: OCRProcessor, text_processor: TextProcessor,
                capture_config: CaptureConfig, monitor_manager=None):
        """
        Initialize screen capture.
        
        Args:
            ocr_processor: OCR processor instance
            text_processor: Text processor instance
            capture_config: Capture configuration
            monitor_manager: Optional monitor manager for multi-monitor support
        """
        self.ocr_processor = ocr_processor
        self.text_processor = text_processor
        self.capture_config = capture_config
        self.monitor_manager = monitor_manager
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
        
        # Monitor validation
        self.last_monitor_check = 0.0
        self.monitor_check_failures = 0
        
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
        
        # Write header with full runtime parameters for audit/A/B comparison
        with open(self.output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Caption capture started: {datetime.now()}\n")
            f.write(f"Language: {language}\n")
            f.write(f"Caption mode: {caption_mode}\n")
            f.write(f"Version: {APP_VERSION}\n")
            f.write(f"Similarity threshold: {self.text_processor.similarity_threshold}\n")
            f.write(f"Min capture interval: {self.capture_config.min_capture_interval:.1f}s\n")
            f.write(f"Max capture interval: {self.capture_config.max_capture_interval:.1f}s\n")
            f.write(f"Clean text mode: raw\n\n")
        
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
            self.logger.debug("Waiting for capture thread to finish...")
            self.capture_thread.join(timeout=5.0)
            if self.capture_thread.is_alive():
                self.logger.warning("Capture thread did not terminate in time - file may be incomplete")

        self.capture_thread = None

        # Ensure output file is fully written before returning
        import time
        if self.output_file_path and self.output_file_path.exists():
            time.sleep(0.5)  # Brief delay to ensure file is flushed to disk
            self.logger.info(f"Capture stopped successfully, file: {self.output_file_path}")

        # Return the output file path
        return str(self.output_file_path) if self.output_file_path else None
    
    def _capture_loop(self, language: str, caption_mode: bool) -> None:
        """
        Main capture loop running in a separate thread.

        Recall-first strategy: write the full OCR text whenever it differs enough
        from the previous capture. No delta extraction, no buffering. All smart
        deduplication happens in post-processing, not here.

        Args:
            language: Language code for OCR
            caption_mode: Whether to use caption-optimized settings
        """
        # Live capture metrics
        metrics = {
            'total_ocr_frames': 0,
            'written_frames': 0,
            'dropped_similarity': 0,
            'dropped_empty': 0,
            'dropped_ui_artifact': 0,
        }

        try:
            last_text = ""
            similar_captures_count = 0
            capture_interval = self.capture_config.reset_interval()

            # Wait for selection overlay to fully disappear before first OCR
            self.stop_event.wait(timeout=0.5)
            if self.capture_stop_flag:
                return

            while not self.capture_stop_flag:
                try:
                    # Validate capture area (check for monitor disconnection)
                    if not self._validate_capture_area():
                        self.logger.warning("Capture area no longer valid, stopping capture")
                        self.capture_stop_flag = True
                        break

                    # Capture screenshot
                    x1, y1, x2, y2 = self.capture_area

                    # Check if we need multi-monitor capture
                    needs_multi_monitor_capture = False

                    if self.monitor_manager and self.monitor_manager.has_multi_monitor():
                        # For multi-monitor setups, always use all_screens=True
                        needs_multi_monitor_capture = True
                        self.logger.debug(
                            f"Multi-monitor setup detected, using all_screens=True for: {self.capture_area}"
                        )
                    elif x1 < 0 or y1 < 0:
                        # Legacy fallback for negative coordinates
                        needs_multi_monitor_capture = True
                        self.logger.debug(
                            f"Negative coordinates detected, using all_screens=True for: {self.capture_area}"
                        )

                    if needs_multi_monitor_capture:
                        try:
                            screenshot = ImageGrab.grab(bbox=self.capture_area, all_screens=True)
                            self.logger.debug("Successfully captured with all_screens=True")
                        except Exception as e:
                            self.logger.error(f"Failed to capture with all_screens=True: {e}")
                            try:
                                full_screenshot = ImageGrab.grab(all_screens=True)
                                if self.monitor_manager:
                                    vx, vy, vw, vh = self.monitor_manager.get_virtual_screen_bounds()
                                    rel_x1 = x1 - vx
                                    rel_y1 = y1 - vy
                                    rel_x2 = x2 - vx
                                    rel_y2 = y2 - vy
                                    screenshot = full_screenshot.crop((rel_x1, rel_y1, rel_x2, rel_y2))
                                    self.logger.debug(
                                        f"Cropped from full screenshot: {rel_x1},{rel_y1},{rel_x2},{rel_y2}"
                                    )
                                else:
                                    raise Exception("No monitor manager available for coordinate conversion")
                            except Exception as e2:
                                self.logger.error(f"All capture methods failed: {e2}")
                                continue
                    else:
                        # Single monitor setup - standard capture
                        self.logger.debug(
                            f"Single monitor setup, using standard capture for: {self.capture_area}"
                        )
                        screenshot = ImageGrab.grab(bbox=self.capture_area)

                    # Optimize image if needed
                    screenshot = self.ocr_processor.optimize_image_for_ocr(screenshot)

                    # Perform OCR
                    raw_text = self.ocr_processor.process_image(screenshot, language, caption_mode)
                    self.logger.debug(f"Raw OCR result (length: {len(raw_text)}): '{raw_text[:100]}...'")
                    metrics['total_ocr_frames'] += 1

                    # Dual-path: raw for file output, normalized for comparison
                    raw_cleaned = self.text_processor.clean_text_raw(raw_text)
                    normalized = self.text_processor.clean_text(raw_text)

                    if not raw_cleaned or not raw_cleaned.strip():
                        metrics['dropped_empty'] += 1
                        continue

                    # Skip UI overlay artifacts (Press ESC, Click and drag, etc.)
                    if self.text_processor._is_ui_artifact(raw_cleaned):
                        self.logger.debug("Skipped UI artifact frame")
                        metrics['dropped_ui_artifact'] += 1
                        continue

                    # Write full raw text if normalized version is meaningfully different
                    if self.text_processor.has_significant_new_content(normalized, last_text):
                        with open(self.output_file_path, 'a', encoding='utf-8') as f:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            f.write(f"[{timestamp}] {raw_cleaned}\n")

                        last_text = normalized
                        self.text_history.append(raw_cleaned)
                        similar_captures_count = 0
                        capture_interval = self.capture_config.reset_interval()
                        metrics['written_frames'] += 1

                        if self.on_text_captured:
                            self.on_text_captured(raw_cleaned)

                        self.logger.debug(f"Captured: {raw_cleaned[:80]}...")
                    else:
                        # No significant change — slow down polling if screen is static
                        similar_captures_count += 1
                        metrics['dropped_similarity'] += 1
                        if similar_captures_count > self.capture_config.max_similar_captures:
                            capture_interval = self.capture_config.increase_interval()

                    # Sleep based on current interval, wake immediately on stop signal
                    self.stop_event.wait(timeout=capture_interval)

                except Exception as e:
                    self.logger.error(f"Error in capture iteration: {e}")
                    self.stop_event.wait(timeout=1)

            self.logger.info(
                f"Capture loop ended. Metrics: "
                f"total_ocr={metrics['total_ocr_frames']}, "
                f"written={metrics['written_frames']}, "
                f"dropped_similarity={metrics['dropped_similarity']}, "
                f"dropped_empty={metrics['dropped_empty']}, "
                f"dropped_ui_artifact={metrics['dropped_ui_artifact']}"
            )

        except Exception as e:
            self.logger.error(f"Critical error in capture loop: {e}")
            if self.on_status_update:
                self.on_status_update(f"Capture error: {str(e)}")
    
    
    def _validate_capture_area(self) -> bool:
        """
        Validate that the capture area is still valid (monitor not disconnected).
        
        Returns:
            True if capture area is still valid
        """
        if not self.monitor_manager or not self.capture_area:
            return True  # No validation possible or needed
        
        current_time = time.time()
        
        # Only check periodically to avoid performance impact
        if current_time - self.last_monitor_check < MONITOR_DISCONNECTION_CHECK_INTERVAL:
            return True
        
        self.last_monitor_check = current_time
        
        try:
            # Check if capture area is still valid
            is_valid = self.monitor_manager.validate_capture_area(self.capture_area)
            
            if is_valid:
                self.monitor_check_failures = 0
                return True
            else:
                self.monitor_check_failures += 1
                self.logger.warning(
                    f"Capture area validation failed (attempt {self.monitor_check_failures})"
                )
                
                # Allow a few failures before stopping (monitor might be temporarily unavailable)
                if self.monitor_check_failures >= 3:
                    self.logger.error("Monitor appears to be disconnected, stopping capture")
                    if self.on_status_update:
                        self.on_status_update("Monitor disconnected - stopping capture")
                    return False
                
                return True
        
        except Exception as e:
            self.logger.error(f"Error validating capture area: {e}")
            return True  # Continue on error to avoid disruption
    
    def _extract_capture_metadata(self, lines: list) -> dict:
        """
        Extract metadata from the raw capture file header.

        Args:
            lines: All lines from the raw capture file

        Returns:
            Dictionary with metadata fields (capture_started, language, caption_mode, version)
        """
        metadata = {}
        for line in lines:
            line = line.strip()
            if line.startswith("Caption capture started:"):
                metadata['capture_started'] = line.split(":", 1)[1].strip()
            elif line.startswith("Language:"):
                metadata['language'] = line.split(":", 1)[1].strip()
            elif line.startswith("Caption mode:"):
                metadata['caption_mode'] = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                metadata['capture_version'] = line.split(":", 1)[1].strip()
            # Stop parsing header after first timestamp block
            if line.startswith('[') and len(line) > 1 and line[1:3].isdigit():
                break
        return metadata

    def process_capture_file(self, filepath: str, custom_name: Optional[str] = None) -> Optional[str]:
        """
        Post-process a capture file with aggressive deduplication.

        Uses sentence-level deduplication, OCR artifact removal, and novelty ratio
        filtering to produce a clean transcription from the raw capture file.
        The processed file includes a metadata header with version and capture info.

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

            # Extract metadata from raw file header
            metadata = self._extract_capture_metadata(lines)

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

            # Recall-first post-processing pipeline
            unique_blocks = self.text_processor.filter_duplicate_blocks_aggressive(
                text_blocks,
                dedup_enter=self.capture_config.post_process_dedup_enter,
                dedup_exit=self.capture_config.post_process_dedup_exit,
                min_length_ratio=self.capture_config.post_process_min_length_ratio,
                min_new_words=self.capture_config.post_process_min_new_words,
                frame_window=self.capture_config.post_process_frame_window,
                min_sentence_words=self.capture_config.post_process_min_sentence_words
            )

            # Create processed filename
            timestamp = self.current_capture_timestamp or datetime.now().strftime(TIMESTAMP_FORMAT)
            processed_filename = self.file_manager.create_capture_filename(
                timestamp, custom_name, processed=True
            )
            processed_filepath = self.file_manager.CAPTURES_DIR / processed_filename

            # Write processed content with metadata header
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                # Write metadata header
                f.write(f"CaptiOCR Processed Transcription\n")
                f.write(f"Version: {APP_VERSION}\n")
                if metadata.get('capture_started'):
                    f.write(f"Capture started: {metadata['capture_started']}\n")
                f.write(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if metadata.get('language'):
                    f.write(f"Language: {metadata['language']}\n")
                f.write(f"Original blocks: {len(text_blocks)}\n")
                f.write(f"Processed blocks: {len(unique_blocks)}\n")

                # Write processing diagnostics if available
                stats = getattr(self.text_processor, '_last_post_process_stats', None)
                if stats:
                    f.write(f"\n--- Processing Diagnostics ---\n")
                    f.write(f"Total frames: {stats['total_frames']}\n")
                    f.write(f"Chunks emitted: {stats['chunks_emitted']}\n")
                    f.write(f"Dropped (UI artifact): {stats['dropped_ui_artifact']}\n")
                    f.write(f"Dropped (OCR artifact): {stats['dropped_ocr_artifact']}\n")
                    f.write(f"Dropped (no consensus): {stats['dropped_no_consensus']}\n")
                    f.write(f"Dropped (no-downgrade): {stats['dropped_no_downgrade']}\n")
                    f.write(f"Dropped (hysteresis dedup): {stats['dropped_hysteresis_dedup']}\n")
                    f.write(f"Dropped (empty after overlap): {stats['dropped_empty_novel']}\n")
                    f.write(f"Merges performed: {stats['merges_performed']}\n")
                    f.write(f"Speaker names repaired: {stats.get('speaker_names_repaired', 0)}\n")
                    f.write(f"Possible drops detected: {stats['possible_drops_detected']}\n")

                f.write(f"\n{'=' * 60}\n\n")

                # Write processed content
                for ts, text in unique_blocks:
                    f.write(f"{ts} {text}\n")

            self.logger.info(
                f"Processed file saved: {processed_filepath} "
                f"({len(text_blocks)} -> {len(unique_blocks)} blocks)"
            )

            return str(processed_filepath)

        except Exception as e:
            self.logger.error(f"Error processing capture file: {e}")
            return None