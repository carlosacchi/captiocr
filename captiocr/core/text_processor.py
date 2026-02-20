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
    POST_PROCESS_SENTENCE_SIMILARITY,
    POST_PROCESS_NOVELTY_THRESHOLD,
    POST_PROCESS_MIN_SENTENCE_WORDS,
    POST_PROCESS_GLOBAL_WINDOW_SIZE
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
    
    # --- Aggressive Post-Processing (for processed files) ---

    # Common short words to never flag as OCR artifacts
    _REAL_SHORT_WORDS = {'I', 'a', 'A',
                         'OK', 'ok', 'Ok', 'IT', 'it', 'It', 'AM', 'am', 'PM', 'pm',
                         'NO', 'no', 'No', 'SO', 'so', 'So', 'OR', 'or', 'Or', 'UP',
                         'AT', 'at', 'At', 'IF', 'if', 'If', 'ON', 'on', 'On', 'AN',
                         'DO', 'do', 'Do', 'IN', 'in', 'In', 'TO', 'to', 'To', 'BY',
                         'OH', 'oh', 'Oh', 'HI', 'hi', 'Hi', 'US', 'us', 'GO', 'go',
                         # Technical acronyms commonly used in meetings
                         'PR', 'CI', 'CD', 'API', 'ADO', 'VM', 'DB', 'QA', 'UI', 'UX',
                         'HR', 'ID', 'IP', 'OS', 'ML', 'AI', 'AB', 'P1', 'P2', 'P3',
                         'P4', 'SLA', 'POC', 'MVP', 'UAT', 'DEV', 'OPS', 'GIT', 'NPR',
                         'ABA', 'SPN', 'AAD', 'URL', 'SSH', 'DNS', 'VPN', 'AWS', 'GCP',
                         # Domain / data acronyms
                         'CRM', 'ERP', 'SQL', 'ETL', 'CSV', 'EKG', 'DKG', 'XML', 'JSON',
                         'PDF', 'SDK', 'IOT', 'KPI', 'ROI', 'B2B', 'B2C', 'SAP', 'BI'}

    # Phrases that should never be filtered out, even if they appear low-novelty or duplicate-like.
    # Matched case-insensitively against sentence text.
    _PROTECTED_PHRASES = [
        # DevOps / workflow
        'close associated', 'close the pr', 'close pr', 'merge pr', 'complete pr',
        'pull request', 'checkbox', 'approval', 'approver', 'approve',
        'hotfix', 'rollback', 'revert', 'deploy', 'release',
        'production', 'incident', 'outage', 'blocker', 'critical',
        'service principal', 'pipeline', 'permission',
        # Domain / business
        'supply chain', 'software as a service', 'data source', 'data flow',
        'dashboard', 'blob storage', 'gold layer', 'silver layer', 'bronze layer',
        'canonical', 'architecture', 'integration', 'modular',
        'enterprise', 'knowledge graph', 'demand planning',
        'technology stack', 'third party', 'manufacturer',
    ]

    def _contains_protected_phrase(self, sentence: str) -> bool:
        """Check if the sentence contains any protected workflow phrase."""
        lower = sentence.lower()
        return any(phrase in lower for phrase in self._PROTECTED_PHRASES)

    @staticmethod
    def _is_gibberish_token(word: str) -> bool:
        """
        Detect if a token is likely OCR gibberish rather than a real word.

        Uses vowel ratio, unusual case patterns, and digit mixing to identify noise.
        Examples of gibberish: wveTvuv7g, wwvevud, VJevuvTJg, Vwuvuvwe
        """
        if len(word) < 4:
            return False

        letters_only = ''.join(c for c in word if c.isalpha())
        if not letters_only:
            return False

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

        # Remove leading OCR garbage (lines starting with dashes, equals, pipes, random symbols)
        text = re.sub(r'^[\s—–\-=_|+.*%&]+', '', text)

        # Remove runs of dashes, equals, underscores, pipes (2+ chars)
        text = re.sub(r'[—–\-=_|]{2,}', ' ', text)

        # Remove gibberish tokens word by word
        words = text.split()
        cleaned_words = []
        for word in words:
            # Strip punctuation for checking but keep original if valid
            stripped = word.strip('.,!?;:()[]{}')
            if stripped and len(stripped) <= 3 and stripped.isupper() and stripped not in self._REAL_SHORT_WORDS:
                continue  # Remove isolated uppercase 2-3 letter OCR noise (EE, BJ, etc.)
            if self._is_gibberish_token(stripped):
                continue  # Remove gibberish tokens
            cleaned_words.append(word)
        text = ' '.join(cleaned_words)

        # Remove stray percent signs not next to numbers
        text = re.sub(r'(?<!\d)\s*%\s*(?!\d)', ' ', text)

        # Remove isolated single characters that aren't common words (I, a, A)
        text = re.sub(r'(?<!\w)(?![IaA])[a-zA-Z](?!\w)', '', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    # Compiled speaker label patterns for reuse
    # The comma pattern requires 4+ char name components to avoid matching OCR garbage
    # like "OK, OK" or "Metal, Egg, PYLON" as speaker labels.
    _SPEAKER_LABEL_RE = re.compile(
        r'[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s*@\s*'              # FirstName LastName @
        r'|'
        r'[A-Z][a-zA-Z]{3,}(?:,\s*[A-Z][a-zA-Z]{3,})+(?:\s+\([^)]*\))?\s*'  # LastName, FirstName (qualifier)
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

        result = []
        for speaker, segment_text in segments:
            # Split on sentence-ending punctuation
            sub_sentences = re.split(r'(?<=[.!?])\s+', segment_text)
            for sent in sub_sentences:
                sent = sent.strip(' ,.')
                if sent and len(sent.split()) >= min_sentence_words:
                    if preserve_speakers and speaker:
                        result.append(f"[{speaker}] {sent}")
                    else:
                        result.append(sent)

        return result

    def _get_word_set(self, text: str) -> set:
        """Extract a set of normalized words from text for comparison."""
        words = text.lower().split()
        # Filter out very short words and common OCR noise
        return {w for w in words if len(w) > 2 or w in {'a', 'i', 'is', 'or', 'in', 'to', 'at', 'it', 'if', 'of', 'on'}}

    def _calculate_novelty_ratio(self, sentence: str, seen_words: set) -> float:
        """
        Calculate what fraction of content words in a sentence are novel (not seen before).

        Stop words are excluded from the calculation so that common everyday
        words don't penalize otherwise meaningful new sentences.

        Returns:
            Ratio from 0.0 (all content words seen) to 1.0 (all content words new).
            Returns 1.0 when the sentence has no content words (only stop words),
            so it falls through to the sentence-level dedup check instead.
        """
        words = self._get_word_set(sentence)
        if not words:
            return 0.0

        # Only evaluate content words (exclude stop words)
        content_words = words - self._stop_words
        if not content_words:
            # Sentence is all stop words — let sentence dedup handle it
            return 1.0

        new_content_words = content_words - seen_words
        return len(new_content_words) / len(content_words)

    def _is_duplicate_sentence(self, sentence: str, seen_sentences: deque,
                                similarity_threshold: float) -> bool:
        """
        Check if a sentence is a near-duplicate of any recently seen sentence.

        Uses both SequenceMatcher similarity and word-level containment check.
        For short sentences (< 8 words), requires both overlap AND similarity to match
        to avoid false positives on sentences that share common words but differ in meaning.
        """
        sent_lower = sentence.lower().strip()
        sent_words = set(sent_lower.split())
        is_short = len(sent_words) < 8

        for seen in seen_sentences:
            seen_lower = seen.lower().strip()
            seen_words = set(seen_lower.split())

            overlap = 0.0
            if sent_words and seen_words:
                overlap = len(sent_words & seen_words) / len(sent_words)

            similarity = difflib.SequenceMatcher(None, sent_lower, seen_lower).ratio()

            if is_short:
                # Short sentences: require BOTH high overlap AND high similarity
                if overlap >= 0.92 and similarity >= similarity_threshold:
                    return True
            else:
                # Longer sentences: either high overlap or high similarity is enough
                if overlap >= 0.92:
                    return True
                if similarity >= similarity_threshold:
                    return True

        return False

    def filter_duplicate_blocks_aggressive(self, text_blocks: List[Tuple[str, str]],
                                            sentence_similarity: float = POST_PROCESS_SENTENCE_SIMILARITY,
                                            novelty_threshold: float = POST_PROCESS_NOVELTY_THRESHOLD,
                                            global_window: int = POST_PROCESS_GLOBAL_WINDOW_SIZE,
                                            min_sentence_words: int = POST_PROCESS_MIN_SENTENCE_WORDS
                                            ) -> List[Tuple[str, str]]:
        """
        Aggressively filter duplicate content at the sentence level for post-processing.

        Unlike filter_duplicate_blocks (used for live capture), this method:
        - Removes OCR artifacts and noise
        - Splits each block into sentences (using speaker labels as delimiters)
        - Tracks ALL seen sentences globally with fuzzy matching
        - Applies a novelty ratio to filter sentences with mostly repeated words
        - Produces a cleaner, more readable transcription

        Args:
            text_blocks: List of (timestamp, text) tuples from raw capture
            sentence_similarity: Threshold for fuzzy sentence deduplication (0-1)
            novelty_threshold: Minimum ratio of new words to keep a sentence (0-1)
            global_window: Number of recent sentences to track for dedup
            min_sentence_words: Minimum words for a sentence to be kept

        Returns:
            List of (timestamp, text) tuples with aggressive deduplication applied
        """
        if not text_blocks:
            return []

        # Global tracking state
        seen_sentences = deque(maxlen=global_window)
        seen_words = set()
        result_blocks = []

        # Diagnostics counters
        stats = {
            'total_sentences': 0,
            'dropped_duplicate': 0,
            'dropped_low_novelty': 0,
            'dropped_artifact': 0,
            'kept_protected': 0,
            'kept_novel': 0,
        }

        for timestamp, text in text_blocks:
            # Step 1: Clean OCR artifacts
            cleaned = self._clean_ocr_artifacts(text)
            if not cleaned:
                stats['dropped_artifact'] += 1
                continue

            # Step 2: Split into sentences
            sentences = self._split_into_sentences(cleaned, min_sentence_words)
            if not sentences:
                stats['dropped_artifact'] += 1
                continue

            stats['total_sentences'] += len(sentences)

            # Step 3: Filter each sentence
            novel_sentences = []
            for sentence in sentences:
                # Protected phrases bypass duplicate and novelty filters
                is_protected = self._contains_protected_phrase(sentence)

                # Skip if it's a near-duplicate of a recently seen sentence
                if not is_protected and self._is_duplicate_sentence(
                        sentence, seen_sentences, sentence_similarity):
                    self.logger.debug(f"Post-process: duplicate sentence filtered: '{sentence[:60]}...'")
                    stats['dropped_duplicate'] += 1
                    continue

                # Check novelty ratio - are enough words in this sentence truly new?
                if not is_protected:
                    novelty = self._calculate_novelty_ratio(sentence, seen_words)
                    if novelty < novelty_threshold:
                        self.logger.debug(
                            f"Post-process: low novelty ({novelty:.2f}): '{sentence[:60]}...'"
                        )
                        stats['dropped_low_novelty'] += 1
                        continue

                if is_protected:
                    self.logger.debug(f"Post-process: protected phrase kept: '{sentence[:60]}...'")
                    stats['kept_protected'] += 1
                else:
                    stats['kept_novel'] += 1

                novel_sentences.append(sentence)
                seen_sentences.appendleft(sentence)
                seen_words.update(self._get_word_set(sentence))

            # Step 4: If any novel sentences remain, add as a result block
            if novel_sentences:
                combined_text = '. '.join(novel_sentences)
                # Ensure proper sentence ending
                if combined_text and not combined_text.endswith(('.', '!', '?')):
                    combined_text += '.'
                result_blocks.append((timestamp, combined_text))

        self.logger.info(
            f"Post-process: {len(text_blocks)} -> {len(result_blocks)} blocks "
            f"({len(text_blocks) - len(result_blocks)} blocks removed)"
        )
        self.logger.info(
            f"Post-process stats: {stats['total_sentences']} sentences evaluated, "
            f"{stats['dropped_duplicate']} duplicate, {stats['dropped_low_novelty']} low-novelty, "
            f"{stats['dropped_artifact']} artifact blocks, {stats['kept_protected']} protected"
        )

        # Store stats for external access (e.g., processed file header)
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