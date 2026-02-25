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
    MIN_TEXT_LENGTH,
    POST_PROCESS_DEDUP_ENTER_THRESHOLD,
    POST_PROCESS_DEDUP_EXIT_THRESHOLD,
    POST_PROCESS_MIN_LENGTH_RATIO,
    POST_PROCESS_MIN_NEW_WORDS,
    POST_PROCESS_FRAME_CONSENSUS_WINDOW,
    POST_PROCESS_MIN_SENTENCE_WORDS
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

        # Short semantic responses that bypass similarity check in live capture
        # These are brief replies that should never be dropped even if the frame is >85% similar
        self._short_semantic_responses = frozenset({
            'yes', 'no', 'yeah', 'yep', 'nope', 'sure', 'ok', 'okay',
            'right', 'exactly', 'agreed', 'correct', 'definitely',
            'thanks', 'thank', 'hello', 'hi', 'bye', 'goodbye',
        })

        # Common stop words excluded from novelty ratio calculation
        self._stop_words = frozenset({
            'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it', 'they', 'them',
            'a', 'an', 'the', 'this', 'that', 'these', 'those',
            'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'can', 'may', 'might', 'shall', 'must',
            'not', 'no', 'nor', 'so', 'if', 'or', 'and', 'but', 'yet',
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'out',
            'about', 'into', 'over', 'after', 'before', 'between', 'under', 'again',
            'then', 'here', 'there', 'when', 'where', 'how', 'what', 'which', 'who',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some', 'any',
            'just', 'also', 'very', 'too', 'only', 'own', 'same', 'than', 'now',
            'its', 'his', 'her', 'their', 'our', 'us',
            'dont', 'didnt', 'doesnt', 'isnt', 'arent', 'wasnt', 'werent',
            'wont', 'wouldnt', 'couldnt', 'shouldnt', 'cant', 'cannot',
        })
    
    def clean_text_raw(self, text: str) -> str:
        """
        Minimal cleaning for raw capture files.

        Only removes control characters and normalizes whitespace.
        Preserves all OCR content faithfully — no symbol stripping, no filtering.
        Used by the live capture loop before writing to the raw file.

        Args:
            text: Raw OCR text

        Returns:
            Lightly cleaned text
        """
        if not text:
            return ""

        # Remove control characters (except newline/tab) and null bytes
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Normalize newlines to spaces (raw file is one line per capture)
        text = text.replace('\n', ' ').replace('\r', ' ')

        # Normalize whitespace
        text = self._whitespace_pattern.sub(' ', text)

        return text.strip()

    def clean_text(self, text: str) -> str:
        """
        Clean OCR text for post-processing and display.

        Removes problematic Unicode characters and normalizes whitespace.
        Used by post-processing pipeline and UI display — NOT by live capture.

        Args:
            text: Raw OCR text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Only remove truly problematic characters, keep dashes and common symbols
        text = re.sub(r'[^\w\s.,!?():\-\u2014\u2013|/\\&%$#@*+="<>\']', '', text)

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

                # Return delta even if small — caller's buffer logic handles accumulation
                if delta_words:
                    delta = ' '.join(delta_words)
                    self.logger.debug(
                        f"Extracted delta: '{delta}' "
                        f"({len(delta_words)} words, "
                        f"common prefix: {best_common_prefix}/{len(prev_words)} words, "
                        f"matched against block -{best_match_idx})"
                    )
                    return delta
                else:
                    self.logger.debug(
                        f"No delta words after prefix match "
                        f"(common prefix: {best_common_prefix}/{len(prev_words)})"
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
        Determine if new text contains significant new content compared to the previous capture.

        Used by the live capture loop (recall-first strategy): write the full OCR text
        whenever it differs enough from the last written capture. No delta extraction,
        no minimum length filter — short utterances are preserved faithfully.

        Args:
            new_text: New text to evaluate (already cleaned by caller)
            previous_text: Previous text for comparison
            threshold: Custom similarity threshold (optional)

        Returns:
            True if text has significant new content
        """
        # Use provided threshold or default
        threshold = threshold or self.similarity_threshold

        # Accept any non-empty text (recall-first: never drop at source)
        if not new_text or not new_text.strip():
            return False

        # If no previous text, always accept
        if not previous_text:
            return True

        # Calculate similarity
        similarity = self.calculate_similarity(new_text, previous_text)
        self.logger.debug(f"Text similarity: {similarity:.2f} (threshold: {threshold})")

        if similarity < threshold:
            return True

        # Bypass: accept even high-similarity frames if they contain new short semantic content
        # This catches brief replies (yes/no/ok/sure) appended to a rolling caption window
        new_words = set(new_text.lower().split())
        prev_words = set(previous_text.lower().split())
        novel_words = new_words - prev_words
        if novel_words & self._short_semantic_responses:
            self.logger.debug(f"Similarity bypass: novel short response detected: {novel_words & self._short_semantic_responses}")
            return True

        return False

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
    
    # --- Post-Processing (for processed files) ---

    @staticmethod
    def _is_gibberish_token(word: str) -> bool:
        """
        Detect if a token is likely OCR gibberish rather than a real word.

        Uses vowel ratio, unusual case patterns, and digit mixing to identify noise.
        Examples of gibberish: wveTvuv7g, wwvevud, VJevuvTJg, Vwuvuvwe
        """
        if len(word) < 4:
            return False

        # All-uppercase short words are almost always acronyms, not gibberish
        if word.isupper() and len(word) <= 6:
            return False

        letters_only = ''.join(c for c in word if c.isalpha())
        if not letters_only:
            return False

        # Check for repetitive character patterns (e.g., "eee", "SSSeSSeSeeeaeeSSSSS")
        if len(letters_only) >= 3:
            unique_chars = len(set(letters_only.lower()))
            char_ratio = unique_chars / len(letters_only)
            if len(letters_only) >= 5 and char_ratio < 0.30:
                return True
            if re.search(r'(.)\1{2,}', letters_only, re.IGNORECASE):
                return True

        # Check for unusual mixed case (lowercase-uppercase-lowercase within word body)
        has_mixed_case = bool(re.search(r'[a-z][A-Z][a-z]', word))

        # Check for digits mixed with letters (like "wveTvuv7g")
        has_mixed_digits = bool(re.search(r'[a-zA-Z]\d[a-zA-Z]', word)) or \
                          bool(re.search(r'\d[a-zA-Z]\d', word))

        # Check vowel ratio - English words typically have >= 25% vowels
        vowels = sum(1 for c in letters_only.lower() if c in 'aeiou')
        vowel_ratio = vowels / len(letters_only) if letters_only else 0

        # Count consecutive consonants (max run)
        max_consonant_run = 0
        current_run = 0
        for c in letters_only.lower():
            if c not in 'aeiou':
                current_run += 1
                max_consonant_run = max(max_consonant_run, current_run)
            else:
                current_run = 0

        # Flag as gibberish if: mixed case oddities OR very low vowels OR extreme consonant runs
        if has_mixed_case and has_mixed_digits:
            return True
        if has_mixed_case and vowel_ratio < 0.3:
            return True
        if len(letters_only) >= 5 and vowel_ratio < 0.15:
            return True
        if max_consonant_run >= 4 and vowel_ratio < 0.25:
            return True

        return False

    def _clean_ocr_artifacts(self, text: str) -> str:
        """Remove OCR artifacts and noise from text while preserving meaningful content."""
        if not text:
            return ""

        # Normalize pipe to I when used as a letter (common OCR misread: "| think" → "I think")
        # Replace pipe at word boundaries: start of word, standalone, or before lowercase
        text = re.sub(r'\|(?=\s)', 'I', text)   # "| " → "I "
        text = re.sub(r'(?<=\s)\|', 'I', text)  # " |" → " I"
        text = re.sub(r'^\|', 'I', text)         # Start of text

        # Remove leading OCR garbage (lines starting with dashes, equals, random symbols)
        text = re.sub(r'^[\s\u2014\u2013\-=_+.*%&]+', '', text)

        # Remove runs of dashes, equals, underscores (2+ chars)
        text = re.sub(r'[\u2014\u2013\-=_]{2,}', ' ', text)

        # Remove gibberish tokens word by word
        words = text.split()
        cleaned_words = []
        for word in words:
            # Strip punctuation for checking but keep original if valid
            stripped = word.strip('.,!?;:()[]{}')
            if self._is_gibberish_token(stripped):
                continue
            cleaned_words.append(word)
        text = ' '.join(cleaned_words)

        # Remove stray percent signs not next to numbers
        text = re.sub(r'(?<!\d)\s*%\s*(?!\d)', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    # Compiled speaker label patterns for reuse
    # The @ pattern is the primary speaker delimiter in Teams/Zoom/Meet captions.
    # The comma pattern requires a parenthetical qualifier to avoid false positives
    # like "Yeah, Marcos" being matched as a speaker label.
    _SPEAKER_LABEL_RE = re.compile(
        r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s*@\s*'              # FirstName LastName @
        r'|'
        r'[A-Z][a-zA-Z]{2,}(?:,\s*[A-Z][a-zA-Z]{2,})+(?:\s+\([^)]*\))\s*'  # LastName, FirstName (qualifier) — required
    )

    def _split_into_sentences(self, text: str,
                              min_sentence_words: int = POST_PROCESS_MIN_SENTENCE_WORDS,
                              preserve_speakers: bool = True) -> List[str]:
        """
        Split text into sentence-like segments based on speaker labels and punctuation.

        In caption OCR, "sentences" are often delimited by speaker labels rather than
        punctuation. This method handles both cases.
        Speaker labels require either "@" or "(qualifier)" to avoid matching normal words.

        Args:
            text: Text to split
            min_sentence_words: Minimum words for a sentence to be kept
            preserve_speakers: If True, prefix sentences with the most recent speaker label
        """
        if not text:
            return []

        # Find all speaker labels and their positions
        labels = list(self._SPEAKER_LABEL_RE.finditer(text))

        # Build list of (speaker_name, speech_text) pairs
        segments = []
        current_speaker = ""
        prev_end = 0

        for match in labels:
            # Text before this label belongs to previous speaker
            speech = text[prev_end:match.start()].strip()
            if speech:
                segments.append((current_speaker, speech))
            # Extract speaker name (strip trailing @ and whitespace)
            current_speaker = match.group().rstrip('@ ').strip()
            prev_end = match.end()

        # Remaining text after last label
        speech = text[prev_end:].strip()
        if speech:
            segments.append((current_speaker, speech))

        # Short meaningful responses that should be preserved even below min_sentence_words
        short_meaningful = {'yes', 'no', 'sure', 'ok', 'okay', 'right', 'exactly',
                            'agreed', 'correct', 'thanks', 'hello', 'hi', 'bye'}

        result = []
        for speaker, segment_text in segments:
            # Split on sentence-ending punctuation
            sub_sentences = re.split(r'(?<=[.!?])\s+', segment_text)
            for sent in sub_sentences:
                sent = sent.strip(' ,.')
                if not sent:
                    continue
                word_count = len(sent.split())
                is_meaningful_short = sent.lower().strip('.,!?') in short_meaningful
                if word_count >= min_sentence_words or is_meaningful_short:
                    if preserve_speakers and speaker:
                        result.append(f"[{speaker}] {sent}")
                    else:
                        result.append(sent)

        return result

    # UI overlay artifact patterns (CaptiOCR's own overlay text that OCR reads back)
    _UI_ARTIFACT_RE = re.compile(
        r'Press\s+ESC|Click\s+and\s+drag|select\s+capture|ESC\s+to\s+cancel',
        re.IGNORECASE
    )

    def _is_ui_artifact(self, text: str) -> bool:
        """Check if text contains UI overlay artifacts from the capture tool itself."""
        return bool(self._UI_ARTIFACT_RE.search(text))

    def _build_speaker_name_cache(self, text_blocks: List[Tuple[str, str]]) -> dict:
        """
        Build a cache of full speaker names and OCR-mangled variants from all text blocks.

        Scans for speaker labels with qualifiers (e.g. "LastName, FirstName (external)")
        and builds a lookup from truncated/mangled variants to full names.

        Returns:
            Dict mapping variant strings to their correct full speaker labels.
        """
        # Find all full speaker labels (those with qualifiers like "(external)")
        full_names = set()
        qualified_pattern = re.compile(
            r'([A-Z][a-zA-Z]{2,}(?:,\s*[A-Z][a-zA-Z]{2,})+(?:\s+\([^)]*\)))'
        )
        at_pattern = re.compile(
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s*@'
        )

        for _, text in text_blocks:
            for match in qualified_pattern.finditer(text):
                full_names.add(match.group(1).strip())
            for match in at_pattern.finditer(text):
                full_names.add(match.group(1).strip())

        if not full_names:
            return {}

        repair_map = {}

        for full_name in full_names:
            # 1. Truncation prefixes (e.g. "Zorn, Chri" from "Zorn, Christian (external)")
            for length in range(6, len(full_name)):
                prefix = full_name[:length]
                if prefix not in repair_map or len(full_name) > len(repair_map[prefix]):
                    repair_map[prefix] = full_name

        # 2. Find OCR-mangled variants via fuzzy match against all speaker-like patterns
        # Look for "Word, Word" patterns that are close to a known name but not exact
        mangled_pattern = re.compile(r'[A-Z][a-zA-Z]{1,}(?:,\s*[A-Z][a-zA-Z]{1,})+')
        all_variants = set()
        for _, text in text_blocks:
            for match in mangled_pattern.finditer(text):
                variant = match.group().strip()
                if variant not in full_names:
                    all_variants.add(variant)

        for variant in all_variants:
            best_match = None
            best_ratio = 0.0
            for full_name in full_names:
                # Compare the base name part (before qualifier)
                full_base = full_name.split('(')[0].strip()
                ratio = difflib.SequenceMatcher(None, variant, full_base).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = full_name
            # Accept fuzzy matches above 0.75 similarity (catches "Zom" → "Zorn", "Goa" → "Goa,")
            if best_match and best_ratio >= 0.75:
                repair_map[variant] = best_match

        self.logger.debug(
            f"Speaker name cache: {len(full_names)} full names, "
            f"{len(repair_map)} repair entries (prefixes + fuzzy)"
        )
        return repair_map

    def _repair_speaker_names(self, text: str, repair_map: dict) -> str:
        """
        Repair truncated and OCR-mangled speaker names in text.

        Replaces variants like "Zorn, Chri", "Zom, Christian", "Goa, Ashok" with
        the correct full name from the cache.
        """
        if not repair_map or not text:
            return text

        # Sort by variant length descending to match longest first (avoids partial replacements)
        for variant in sorted(repair_map, key=len, reverse=True):
            if variant in text and repair_map[variant] not in text:
                text = text.replace(variant, repair_map[variant])

        return text

    def _find_overlap_boundary(self, prev_text: str, new_text: str) -> Tuple[int, int]:
        """
        Find the shared prefix and suffix boundaries between two texts at word level.

        Returns:
            Tuple of (prefix_end_idx, suffix_start_idx) as word indices into new_text.
            The novel content is new_words[prefix_end_idx:suffix_start_idx].
        """
        prev_words = prev_text.lower().split()
        new_words = new_text.lower().split()

        # Find shared prefix length
        prefix_len = 0
        for i in range(min(len(prev_words), len(new_words))):
            if prev_words[i] == new_words[i]:
                prefix_len = i + 1
            else:
                break

        # Find shared suffix length (avoid overlapping with prefix)
        suffix_len = 0
        max_suffix = min(len(prev_words), len(new_words)) - prefix_len
        for i in range(1, max_suffix + 1):
            if prev_words[-i] == new_words[-i]:
                suffix_len = i
            else:
                break

        suffix_start = len(new_words) - suffix_len if suffix_len > 0 else len(new_words)
        return prefix_len, suffix_start

    def _frame_consensus(self, frames: List[str], min_agreement: int = 2) -> Optional[str]:
        """
        Check if content has consensus across a window of frames.

        A chunk is considered stable if its content (by word set overlap) appears
        in at least min_agreement out of the provided frames.

        Args:
            frames: List of text content from consecutive frames
            min_agreement: Minimum number of frames that must agree

        Returns:
            The consensus text (from the longest agreeing frame), or None if no consensus.
        """
        if len(frames) < min_agreement:
            return None

        candidate = frames[-1]
        candidate_words = set(candidate.lower().split())

        if not candidate_words:
            return None

        agreeing_frames = []
        for frame in frames:
            frame_words = set(frame.lower().split())
            if not frame_words:
                continue
            overlap = len(candidate_words & frame_words) / max(len(candidate_words), len(frame_words))
            if overlap >= 0.50:
                agreeing_frames.append(frame)

        if len(agreeing_frames) >= min_agreement:
            return max(agreeing_frames, key=len)

        return None

    def _get_word_set(self, text: str) -> set:
        """Extract a set of normalized words from text for comparison."""
        words = text.lower().split()
        # Filter out very short words and common OCR noise
        return {w for w in words if len(w) > 2 or w in {'a', 'i', 'is', 'or', 'in', 'to', 'at', 'it', 'if', 'of', 'on'}}

    def filter_duplicate_blocks_aggressive(self, text_blocks: List[Tuple[str, str]],
                                            dedup_enter: float = POST_PROCESS_DEDUP_ENTER_THRESHOLD,
                                            dedup_exit: float = POST_PROCESS_DEDUP_EXIT_THRESHOLD,
                                            min_length_ratio: float = POST_PROCESS_MIN_LENGTH_RATIO,
                                            min_new_words: int = POST_PROCESS_MIN_NEW_WORDS,
                                            frame_window: int = POST_PROCESS_FRAME_CONSENSUS_WINDOW,
                                            min_sentence_words: int = POST_PROCESS_MIN_SENTENCE_WORDS
                                            ) -> List[Tuple[str, str]]:
        """
        Recall-first post-processing pipeline for raw capture files.

        Processes raw OCR frames through a multi-stage pipeline:
        1. UI artifact filter — remove CaptiOCR overlay text
        2. OCR artifact cleaning — pipe normalization, gibberish removal
        3. Frame consensus — emit only when content is stable across frames
        4. No-downgrade rule — skip transient short frames
        5. Hysteresis dedup — suppress repetition with enter/exit thresholds
        6. Prefix/suffix overlap dedup — emit only the novel portion
        7. Sentence splitting — structure the output

        Args:
            text_blocks: List of (timestamp, text) tuples from raw capture
            dedup_enter: Similarity threshold to enter dedup mode
            dedup_exit: Similarity threshold to exit dedup mode
            min_length_ratio: No-downgrade rule: min ratio of new vs previous length
            min_new_words: No-downgrade rule: min new words to accept a shorter frame
            frame_window: Number of consecutive frames for consensus check
            global_window: Number of recent sentences to track
            min_sentence_words: Minimum words for a sentence to be kept

        Returns:
            List of (timestamp, text) tuples with deduplication applied
        """
        if not text_blocks:
            return []

        # Build speaker name cache for repairing truncated names
        speaker_repair_map = self._build_speaker_name_cache(text_blocks)

        result_blocks = []
        frame_buffer = deque(maxlen=frame_window)
        ts_buffer = deque(maxlen=frame_window)
        prev_emitted_text = ""
        in_dedup_mode = False

        stats = {
            'speaker_names_repaired': 0,
            'total_frames': len(text_blocks),
            'dropped_ui_artifact': 0,
            'dropped_ocr_artifact': 0,
            'dropped_no_consensus': 0,
            'dropped_no_downgrade': 0,
            'dropped_hysteresis_dedup': 0,
            'dropped_empty_novel': 0,
            'merges_performed': 0,
            'chunks_emitted': 0,
            'possible_drops_detected': 0,
        }

        for timestamp, text in text_blocks:
            # Step 1: UI artifact filter
            if self._is_ui_artifact(text):
                stats['dropped_ui_artifact'] += 1
                continue

            # Step 2: Clean OCR artifacts (inline gibberish removal + pipe normalization)
            cleaned = self._clean_ocr_artifacts(text)
            if not cleaned or len(cleaned.split()) < 1:
                stats['dropped_ocr_artifact'] += 1
                continue

            # Step 2b: Line-level gibberish check — drop frames where too much was garbage
            # If cleaning removed >50% of words, the original was mostly gibberish
            original_word_count = len(text.split())
            cleaned_word_count = len(cleaned.split())
            if original_word_count > 5 and cleaned_word_count / original_word_count < 0.50:
                stats['dropped_ocr_artifact'] += 1
                self.logger.debug(
                    f"Dropped gibberish-heavy frame: {cleaned_word_count}/{original_word_count} "
                    f"words survived cleaning"
                )
                continue

            # Step 2c: Repair truncated speaker names
            if speaker_repair_map:
                repaired = self._repair_speaker_names(cleaned, speaker_repair_map)
                if repaired != cleaned:
                    stats['speaker_names_repaired'] += 1
                    cleaned = repaired

            # Step 3: Frame consensus
            frame_buffer.append(cleaned)
            ts_buffer.append(timestamp)
            consensus = self._frame_consensus(list(frame_buffer))
            if consensus is None:
                stats['dropped_no_consensus'] += 1
                continue

            # Step 4: No-downgrade rule
            if prev_emitted_text:
                length_ratio = len(consensus) / max(len(prev_emitted_text), 1)
                if length_ratio < min_length_ratio:
                    prev_words = set(prev_emitted_text.lower().split())
                    new_words_set = set(consensus.lower().split()) - prev_words
                    if len(new_words_set) < min_new_words:
                        stats['dropped_no_downgrade'] += 1
                        continue

            # Step 5: Hysteresis dedup
            if prev_emitted_text:
                similarity = self.calculate_similarity(consensus, prev_emitted_text)
                if not in_dedup_mode and similarity >= dedup_enter:
                    in_dedup_mode = True
                    stats['dropped_hysteresis_dedup'] += 1
                    continue
                elif in_dedup_mode and similarity > dedup_exit:
                    stats['dropped_hysteresis_dedup'] += 1
                    continue
                elif in_dedup_mode and similarity <= dedup_exit:
                    in_dedup_mode = False

            # Step 6: Prefix/suffix overlap dedup
            novel_text = consensus
            if prev_emitted_text:
                prefix_end, suffix_start = self._find_overlap_boundary(prev_emitted_text, consensus)
                original_words = consensus.split()
                novel_words = original_words[prefix_end:suffix_start]
                if novel_words:
                    novel_text = ' '.join(novel_words)
                    if prefix_end > 0 or suffix_start < len(original_words):
                        stats['merges_performed'] += 1
                else:
                    stats['dropped_empty_novel'] += 1
                    continue

            # Step 7: Sentence splitting
            sentences = self._split_into_sentences(novel_text, min_sentence_words)
            if not sentences:
                if len(novel_text.split()) >= min_sentence_words:
                    sentences = [novel_text]
                else:
                    stats['dropped_empty_novel'] += 1
                    continue

            # Step 8: Emit
            combined = '. '.join(sentences)
            if combined and not combined.endswith(('.', '!', '?')):
                combined += '.'
            result_blocks.append((timestamp, combined))
            prev_emitted_text = consensus
            stats['chunks_emitted'] += 1

        # Detect possible drops: gaps > 30s with dissimilar content
        for i in range(1, len(result_blocks)):
            prev_ts = result_blocks[i - 1][0]
            curr_ts = result_blocks[i][0]
            try:
                from datetime import datetime
                fmt = '[%H:%M:%S]'
                t1 = datetime.strptime(prev_ts, fmt)
                t2 = datetime.strptime(curr_ts, fmt)
                gap = (t2 - t1).total_seconds()
                if gap > 30:
                    sim = self.calculate_similarity(result_blocks[i - 1][1], result_blocks[i][1])
                    if sim < 0.3:
                        stats['possible_drops_detected'] += 1
            except (ValueError, TypeError):
                pass

        self.logger.info(
            f"Post-process: {stats['total_frames']} frames -> {stats['chunks_emitted']} chunks. "
            f"Dropped: {stats['dropped_ui_artifact']} UI, {stats['dropped_ocr_artifact']} OCR, "
            f"{stats['dropped_no_consensus']} no-consensus, {stats['dropped_no_downgrade']} no-downgrade, "
            f"{stats['dropped_hysteresis_dedup']} hysteresis, {stats['dropped_empty_novel']} empty-novel. "
            f"Merges: {stats['merges_performed']}. Speaker repairs: {stats['speaker_names_repaired']}. "
            f"Possible drops: {stats['possible_drops_detected']}."
        )

        self._last_post_process_stats = stats

        return result_blocks

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