"""
Text processing and analysis utilities.
"""
import re
import difflib
from typing import List, Optional, Tuple
from collections import deque
import logging

from ..config.constants import (
    TEXT_SIMILARITY_THRESHOLD,
    MIN_TEXT_LENGTH
)


class TextProcessor:
    """Process and analyze OCR text results."""

    def __init__(self, similarity_threshold: float = TEXT_SIMILARITY_THRESHOLD,
                 incremental_threshold: Optional[float] = None):
        """
        Initialize text processor.

        Args:
            similarity_threshold: Threshold for text similarity (0-1)
            incremental_threshold: Threshold for incremental detection (0-1), defaults to 0.7
        """
        self.similarity_threshold = similarity_threshold
        self.incremental_threshold = incremental_threshold if incremental_threshold is not None else 0.7
        self.logger = logging.getLogger('CaptiOCR.TextProcessor')
        
        # Compile regex patterns for efficiency
        self._short_word_pattern = re.compile(r'\b[a-zA-Z]{1,2}\b')
        self._special_char_pattern = re.compile(r'[^\w\s.,!?():\-]')
        self._whitespace_pattern = re.compile(r'\s+')
        self._sentence_pattern = re.compile(r'[.!?]+')
    
    def clean_text(self, text: str) -> str:
        """
        Clean OCR text to remove noise and improve readability.
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # TEMPORARILY DISABLED - TOO AGGRESSIVE CLEANING
        # Remove single letters and very short fragments  
        # text = self._short_word_pattern.sub('', text)
        
        # Remove weird Unicode or special characters - BE MORE SELECTIVE
        # text = self._special_char_pattern.sub('', text)
        
        # Only remove truly problematic characters, keep dashes and common symbols
        text = re.sub(r'[^\w\s.,!?():\-—–|/\\&%$#@*+="<>]', '', text)
        
        # Normalize whitespace
        text = self._whitespace_pattern.sub(' ', text)
        
        return text.strip()
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity ratio (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def _normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text for comparison by removing OCR noise and artifacts.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Remove special characters and OCR artifacts at the beginning
        text = re.sub(r'^[^\w\s]+\s*', '', text)

        # Remove isolated very short tokens (likely OCR errors)
        words = text.split()
        # Keep words longer than 2 chars, or common short words
        common_short_words = {'a', 'i', 'is', 'or', 'in', 'to', 'at', 'it', 'if', 'of', 'on'}
        words = [w for w in words if len(w) > 2 or w.lower() in common_short_words]

        return ' '.join(words)

    def extract_new_content(self, new_text: str, previous_texts: List[str],
                           min_delta_words: int = 5) -> Optional[str]:
        """
        Extract only the new/incremental content from new_text.

        This method handles incremental subtitle accumulation by identifying
        the common prefix and extracting only the delta (new words).
        Compares against multiple previous texts to catch A-B-A redundancy patterns.

        Args:
            new_text: New text to analyze
            previous_texts: List of previous texts to compare against (newest first)
            min_delta_words: Minimum number of words for delta to be significant

        Returns:
            The delta (new content only), or None if no significant new content
        """
        # Clean the new text
        new_text = self.clean_text(new_text)

        # Check if text is too short after cleaning
        if len(new_text) < MIN_TEXT_LENGTH:
            self.logger.debug(f"Text too short after cleaning: {len(new_text)} chars")
            return None

        # If no previous text, return all content
        if not previous_texts or not previous_texts[0]:
            return new_text

        # Normalize new text
        new_normalized = self._normalize_for_comparison(new_text)
        new_words = new_normalized.split()

        # Try to find best match among previous texts (to catch A-B-A patterns)
        best_match_idx = 0
        best_common_prefix = 0

        for idx, prev_text in enumerate(previous_texts):
            if not prev_text:
                continue

            prev_normalized = self._normalize_for_comparison(prev_text)
            prev_words = prev_normalized.split()

            # Find common prefix length (word-level)
            common_prefix_len = 0
            for i in range(min(len(prev_words), len(new_words))):
                if prev_words[i] == new_words[i]:
                    common_prefix_len = i + 1
                else:
                    break

            # Track best matching previous text
            if common_prefix_len > best_common_prefix:
                best_common_prefix = common_prefix_len
                best_match_idx = idx

        # Use best matching previous text for delta extraction
        if previous_texts[best_match_idx]:
            prev_normalized = self._normalize_for_comparison(previous_texts[best_match_idx])
            prev_words = prev_normalized.split()

            # If more than incremental_threshold of previous text is present as prefix in new text
            # This indicates incremental accumulation (subtitles scenario)
            if prev_words and best_common_prefix > len(prev_words) * self.incremental_threshold:
                delta_words = new_words[best_common_prefix:]

                # Need at least min_delta_words new words to be significant
                if len(delta_words) >= min_delta_words:
                    delta = ' '.join(delta_words)
                    self.logger.debug(
                        f"Extracted delta: '{delta}' "
                        f"(common prefix: {best_common_prefix}/{len(prev_words)} words, "
                        f"matched against block -{best_match_idx})"
                    )
                    return delta
                else:
                    self.logger.debug(
                        f"Delta too small: {len(delta_words)} words "
                        f"(minimum: {min_delta_words}, "
                        f"common prefix: {best_common_prefix}/{len(prev_words)})"
                    )
                    return None

        # Texts are different - check if this is completely new content
        # Compare against most recent text
        prev_normalized = self._normalize_for_comparison(previous_texts[0])
        similarity = self.calculate_similarity(prev_normalized, new_normalized)
        self.logger.debug(
            f"Texts not incremental. Similarity: {similarity:.2f} "
            f"(threshold: {self.similarity_threshold})"
        )

        if similarity < self.similarity_threshold:
            # Completely new content
            return new_text
        else:
            # Too similar but not incremental - likely duplicate with noise
            return None

    def has_significant_new_content(self, new_text: str, previous_text: str,
                                    threshold: Optional[float] = None) -> bool:
        """
        Determine if new text contains significant new content.

        DEPRECATED: Use extract_new_content() instead for better duplicate handling.
        This method is kept for backward compatibility.

        Args:
            new_text: New text to evaluate
            previous_text: Previous text for comparison
            threshold: Custom similarity threshold (optional)

        Returns:
            True if text has significant new content
        """
        # Use provided threshold or default
        threshold = threshold or self.similarity_threshold

        # Clean the new text
        new_text = self.clean_text(new_text)

        # Check if text is too short after cleaning
        if len(new_text) < MIN_TEXT_LENGTH:
            self.logger.debug(f"Text too short after cleaning: {len(new_text)} chars")
            return False

        # If no previous text, always accept
        if not previous_text:
            return True

        # Calculate similarity
        similarity = self.calculate_similarity(new_text, previous_text)
        self.logger.debug(f"Text similarity: {similarity:.2f} (threshold: {threshold})")

        # Return True if text is different enough
        return similarity < threshold
    
    def extract_sentences(self, text: str) -> List[str]:
        """
        Extract sentences from text.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        if not text:
            return []
        
        # Split by sentence delimiters
        sentences = []
        for part in self._sentence_pattern.split(text):
            part = part.strip()
            if part:
                sentences.append(part)
        
        return sentences
    
    def filter_duplicate_blocks(self, text_blocks: List[Tuple[str, str]],
                                similarity_threshold: float = 0.75,
                                min_delta_words: int = 5,
                                window_size: int = 5,
                                buffer_threshold: int = 3) -> List[Tuple[str, str]]:
        """
        Filter duplicate text blocks and extract only new content.

        This method uses delta extraction to handle incremental subtitle accumulation,
        preserving only the new content when blocks overlap. Compares against a window
        of recent blocks to catch A-B-A redundancy patterns.

        Args:
            text_blocks: List of (timestamp, text) tuples
            similarity_threshold: Kept for backward compatibility, not used in new implementation
            min_delta_words: Minimum words for significant delta
            window_size: Number of previous texts to compare against
            buffer_threshold: Number of fragments before flushing buffer

        Returns:
            List of (timestamp, text) tuples with duplicates removed and deltas extracted
        """
        if not text_blocks:
            return []

        # Keep the first block
        unique_blocks = [text_blocks[0]]

        # Keep window of recent texts for comparison
        recent_texts = deque([text_blocks[0][1]], maxlen=window_size)

        # Buffer for small deltas
        delta_buffer = []

        # Process subsequent blocks
        for i in range(1, len(text_blocks)):
            timestamp, text = text_blocks[i]

            # Try to extract delta from the new text
            delta = self.extract_new_content(text, list(recent_texts), min_delta_words=min_delta_words)

            if delta:
                word_count = len(delta.split())

                # If delta is small, add to buffer
                if word_count < min_delta_words:
                    delta_buffer.append(delta)
                    self.logger.debug(
                        f"Block at {timestamp}: added to buffer ({word_count} words)"
                    )
                else:
                    # Flush buffer if it has content
                    content_to_save = delta
                    if delta_buffer:
                        buffered_content = ' '.join(delta_buffer)
                        content_to_save = f"{buffered_content} {delta}"
                        delta_buffer.clear()

                    unique_blocks.append((timestamp, content_to_save))
                    self.logger.debug(
                        f"Block at {timestamp}: extracted delta ({len(content_to_save)} chars)"
                    )

                # Always update recent_texts window
                recent_texts.appendleft(text)
            else:
                # No new content - check if we should flush buffer
                if len(delta_buffer) >= buffer_threshold:
                    buffered_content = ' '.join(delta_buffer)
                    unique_blocks.append((timestamp, buffered_content))
                    delta_buffer.clear()
                    self.logger.debug(
                        f"Block at {timestamp}: flushed buffer "
                        f"({len(buffered_content)} chars)"
                    )
                else:
                    self.logger.debug(
                        f"Block at {timestamp}: filtered as duplicate/no significant delta"
                    )

        # Flush any remaining buffer at the end
        if delta_buffer:
            buffered_content = ' '.join(delta_buffer)
            # Use last timestamp
            last_timestamp = text_blocks[-1][0]
            unique_blocks.append((last_timestamp, buffered_content))
            self.logger.debug(f"Final buffer flush: {len(buffered_content)} chars")

        self.logger.info(
            f"Filtered blocks: {len(text_blocks)} -> {len(unique_blocks)} "
            f"({len(text_blocks) - len(unique_blocks)} duplicates removed)"
        )

        return unique_blocks
    
    def truncate_for_display(self, text: str, max_chars: int = 50, max_lines: int = 2) -> str:
        """
        Truncate text for UI display.
        
        Args:
            text: Text to truncate
            max_chars: Maximum number of characters
            max_lines: Maximum number of lines
            
        Returns:
            Truncated text with ellipsis if needed
        """
        if not text:
            return ""
        
        # Split into lines and limit
        lines = text.split('\n')
        if len(lines) > max_lines:
            text = '\n'.join(lines[:max_lines]) + "..."
        
        # Also limit total characters
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        return text