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
    
    def __init__(self, similarity_threshold: float = TEXT_SIMILARITY_THRESHOLD):
        """
        Initialize text processor.
        
        Args:
            similarity_threshold: Threshold for text similarity (0-1)
        """
        self.similarity_threshold = similarity_threshold
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
    
    def has_significant_new_content(self, new_text: str, previous_text: str,
                                    threshold: Optional[float] = None) -> bool:
        """
        Determine if new text contains significant new content.
        
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
                                similarity_threshold: float = 0.75) -> List[Tuple[str, str]]:
        """
        Filter out duplicate text blocks (like original CaptiOCR_old.py).
        
        Args:
            text_blocks: List of (timestamp, text) tuples
            similarity_threshold: Threshold for considering blocks as duplicates
            
        Returns:
            Filtered list of unique blocks
        """
        if not text_blocks:
            return []
        
        # Keep the first block (like original)
        unique_blocks = [text_blocks[0]]
        
        # Filter out blocks with duplicate content (like original)
        for i in range(1, len(text_blocks)):
            timestamp, text = text_blocks[i]
            current_text = f"{timestamp} {text}"  # Include timestamp like original
            is_unique = True
            
            # Compare with last 3 unique blocks (like original)
            for prev_timestamp, prev_text in unique_blocks[-3:]:
                prev_full_text = f"{prev_timestamp} {prev_text}"
                
                # If similarity is too high, skip this block (like original)
                if self.calculate_similarity(current_text, prev_full_text) > similarity_threshold:
                    is_unique = False
                    self.logger.debug(f"Filtered duplicate block at {timestamp} (similarity > {similarity_threshold})")
                    break
            
            if is_unique:
                unique_blocks.append((timestamp, text))
        
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