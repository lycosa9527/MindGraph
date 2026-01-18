"""
Pattern-based boundary detection for fast chunking.

Uses heuristic rules and regex patterns to identify boundaries:
- Paragraph breaks (\n\n)
- Sentence endings (. ! ? 。！？)
- Heading markers (# ## ### or numbered)
- TOC-guided boundaries
"""

import re
import logging
from typing import List, Dict, Tuple, Optional, Any, Callable, Literal
from itertools import accumulate
from bisect import bisect_left

logger = logging.getLogger(__name__)


class PatternMatcher:
    """
    Pattern-based boundary detection.

    Fast, rule-based approach that handles 80% of boundaries
    without LLM calls.
    """

    # Sentence ending patterns
    SENTENCE_ENDINGS = [
        r'[。！？]\s+',  # Chinese punctuation
        r'[.!?]\s+',     # English punctuation
    ]

    # Paragraph break pattern
    PARAGRAPH_BREAK = r'\n\n+'

    # Heading patterns
    MARKDOWN_HEADING = r'^(#{1,6})\s+(.+)$'
    NUMBERED_HEADING = r'^(\d+(?:\.\d+)*)\s+(.+)$'

    # Phase 2: Separator priority list (from Dify and semchunk)
    # Priority: newlines > tabs > whitespace > punctuation
    SEPARATORS = ["\n\n", "\n", "。", ". ", "！", "？", "! ", "? ", "; ", "；", " ", ""]

    # Non-whitespace semantic splitters (from semchunk)
    NON_WHITESPACE_SPLITTERS = [".", "?", "!", "*", ";", ",", "(", ")", "[", "]",
                                """, """, "'", "'", "'", '"', "`", ":", "—", "…",
                                "/", "\\", "–", "&", "-", "。", "！", "？", "；"]

    def __init__(
        self,
        token_counter: Optional[Callable[[str], int]] = None,
        fixed_separator: Optional[str] = "\n\n"
    ):
        """
        Initialize pattern matcher.

        Args:
            token_counter: Optional token counter function for length caching
        """
        self.sentence_pattern = re.compile('|'.join(self.SENTENCE_ENDINGS))
        self.paragraph_pattern = re.compile(self.PARAGRAPH_BREAK)
        self.markdown_heading_pattern = re.compile(self.MARKDOWN_HEADING, re.MULTILINE)
        self.numbered_heading_pattern = re.compile(self.NUMBERED_HEADING, re.MULTILINE)
        self.token_counter = token_counter
        self.fixed_separator = fixed_separator

    def split_by_paragraphs(self, text: str) -> List[str]:
        """
        Split text by paragraph breaks.

        Args:
            text: Text to split

        Returns:
            List of paragraphs
        """
        paragraphs = self.paragraph_pattern.split(text)
        # Clean up empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs

    def _select_best_splitter(self, text: str) -> Tuple[str, bool]:
        """
        Phase 2: Select most semantically meaningful splitter (from semchunk).

        Priority: newlines > tabs > whitespace > punctuation

        Args:
            text: Text to analyze

        Returns:
            Tuple of (splitter, is_whitespace)
        """

        # Priority 1: Largest sequence of newlines/carriage returns
        if "\n" in text or "\r" in text:
            newlines = re.findall(r"[\r\n]+", text)
            if newlines:
                return max(newlines, key=len), True

        # Priority 2: Largest sequence of tabs
        if "\t" in text:
            tabs = re.findall(r"\t+", text)
            if tabs:
                return max(tabs, key=len), True

        # Priority 3: Largest sequence of whitespace
        if re.search(r"\s", text):
            whitespaces = re.findall(r"\s+", text)
            if whitespaces:
                splitter = max(whitespaces, key=len)
                # Handle whitespace preceded by punctuation (from semchunk)
                if len(splitter) == 1:
                    for punct in self.NON_WHITESPACE_SPLITTERS:
                        escaped = re.escape(punct)
                        match = re.search(rf'{escaped}(\s)', text)
                        if match:
                            return match.group(1), True
                return splitter, True

        # Priority 4: Semantic punctuation
        for punct in self.NON_WHITESPACE_SPLITTERS:
            if punct in text:
                return punct, False

        # Fallback: empty string (character-level)
        return "", False

    def split_by_sentences(
        self,
        text: str,
        include_delim: Optional[Literal["prev", "next"]] = "prev",
        min_characters_per_sentence: int = 12
    ) -> List[str]:
        """
        Split text by sentence endings (Phase 2: Enhanced with delimiter inclusion).

        Supports both English and Chinese punctuation.

        Args:
            text: Text to split
            include_delim: Whether to include delimiter with previous or next sentence
            min_characters_per_sentence: Minimum characters per sentence

        Returns:
            List of sentences
        """
        # Phase 2: Use hierarchical splitter selection
        splitter, is_whitespace = self._select_best_splitter(text)

        # Phase 2: Enhanced delimiter handling (from chonkie)
        sep = "✄"  # Temporary separator
        if splitter:
            if include_delim == "prev":
                text = text.replace(splitter, splitter + sep)
            elif include_delim == "next":
                text = text.replace(splitter, sep + splitter)
            else:
                text = text.replace(splitter, sep)

        # Initial split
        splits = [s for s in text.split(sep) if s != ""]

        # Phase 2: Combine short splits with previous sentence (from chonkie)
        current = ""
        sentences = []
        for s in splits:
            if len(s) < min_characters_per_sentence:
                current += s
            elif current:
                current += s
                sentences.append(current)
                current = ""
            else:
                sentences.append(s)

            # If current sentence is long enough, add it
            if len(current) >= min_characters_per_sentence:
                sentences.append(current)
                current = ""

        # Add remaining current
        if current:
            sentences.append(current)

        return [s.strip() for s in sentences if s.strip()]

    def detect_headings(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect headings using patterns.

        Supports:
        - Markdown: # Heading, ## Heading, ### Heading
        - Numbered: 1. Heading, 1.1 Heading, 1.1.1 Heading

        Args:
            text: Text to analyze

        Returns:
            List of heading dicts with 'level', 'title', 'position'
        """
        headings = []

        # Detect markdown headings
        for match in self.markdown_heading_pattern.finditer(text):
            level = len(match.group(1))  # # = 1, ## = 2, ### = 3
            title = match.group(2).strip()
            headings.append({
                "level": level,
                "title": title,
                "position": match.start(),
                "type": "markdown"
            })

        # Detect numbered headings
        for match in self.numbered_heading_pattern.finditer(text):
            number = match.group(1)  # "1", "1.1", "1.1.1"
            level = number.count('.') + 1
            title = match.group(2).strip()
            headings.append({
                "level": level,
                "title": title,
                "position": match.start(),
                "type": "numbered",
                "number": number
            })

        # Sort by position
        headings.sort(key=lambda x: x["position"])

        return headings

    def _merge_splits_with_binary_search(
        self,
        splits: List[str],
        cum_lens: List[int],
        chunk_size: int,
        splitter: str,
        token_counter: Callable[[str], int],
        start: int,
        high: int
    ) -> Tuple[int, str]:
        """
        Phase 2: Merge splits using binary search (from semchunk).

        Uses adaptive token-to-character ratio and binary search for efficiency.
        """
        average = 0.2  # Initial estimate
        low = start
        offset = cum_lens[start]
        target = offset + (chunk_size * average)

        while low < high:
            i = bisect_left(cum_lens, target, lo=low, hi=high)
            midpoint = min(i, high - 1)

            merged_text = splitter.join(splits[start:midpoint])
            tokens = token_counter(merged_text)

            local_cum = cum_lens[midpoint] - offset

            if local_cum and tokens > 0:
                average = local_cum / tokens
                target = offset + (chunk_size * average)

            if tokens > chunk_size:
                high = midpoint
            else:
                low = midpoint + 1

        end = low - 1
        return end, splitter.join(splits[start:end])

    def _chunk_recursive(
        self,
        text: str,
        chunk_size: int,
        token_counter: Callable[[str], int],
        separators: Optional[List[str]] = None,
        _recursion_depth: int = 0,
        _start: int = 0
    ) -> Tuple[List[str], List[Tuple[int, int]]]:
        """
        Phase 2: Recursively chunk text (from semchunk).

        Handles oversized splits by recursively chunking them.
        """
        if separators is None:
            separators = self.SEPARATORS

        # Select best separator
        splitter, splitter_is_whitespace = self._select_best_splitter(text)

        # Split text
        if splitter:
            if splitter == " ":
                splits = re.split(r" +", text)
            else:
                splits = text.split(splitter)
                splits = [s for s in splits if s and s not in {"", "\n"}]
        else:
            splits = list(text)

        splitter_len = len(splitter)
        split_lens = [len(split) for split in splits]
        cum_lens = list(accumulate(split_lens, initial=0))
        split_starts = list(accumulate([0] + [split_len + splitter_len for split_len in split_lens]))
        split_starts = [start + _start for start in split_starts]

        chunks = []
        offsets = []
        skips = set()

        for i, (split, split_start) in enumerate(zip(splits, split_starts)):
            if i in skips:
                continue

            split_tokens = token_counter(split)

            # If split exceeds chunk size, recursively chunk it
            if split_tokens > chunk_size:
                # Find next separator for recursion
                remaining_separators = separators[separators.index(splitter) + 1:] if splitter in separators else separators[1:]
                sub_chunks, sub_offsets = self._chunk_recursive(
                    split,
                    chunk_size,
                    token_counter,
                    remaining_separators,
                    _recursion_depth + 1,
                    split_start
                )
                chunks.extend(sub_chunks)
                offsets.extend(sub_offsets)
            else:
                # Merge with subsequent splits using binary search
                end_idx, merged_chunk = self._merge_splits_with_binary_search(
                    splits, cum_lens, chunk_size, splitter, token_counter, i, len(splits) + 1
                )

                skips.update(range(i + 1, end_idx))
                chunks.append(merged_chunk)

                split_end = split_starts[end_idx] - splitter_len
                offsets.append((split_start, split_end))

        return chunks, offsets

    def find_boundaries(
        self,
        text: str,
        max_tokens: int = 500,
        prefer_paragraphs: bool = True,
        token_counter: Optional[Callable[[str], int]] = None,
        fixed_separator: Optional[str] = None
    ) -> List[Tuple[int, int]]:
        """
        Find chunk boundaries using patterns (Phase 2: Enhanced with fixed separator, binary search, recursive chunking).

        Args:
            text: Text to analyze
            max_tokens: Maximum tokens per chunk (approximate)
            prefer_paragraphs: If True, prefer paragraph boundaries
            token_counter: Optional token counter for length caching
            fixed_separator: Optional fixed separator to use first (Phase 2: from Dify)

        Returns:
            List of (start_pos, end_pos) tuples
        """
        # Use provided token_counter or instance token_counter
        counter = token_counter or self.token_counter
        if not counter:
            # Fallback: use character-based estimation
            def counter(t):
                return len(t) // 4

        # Phase 2: Fixed separator first strategy (from Dify)
        fixed_sep = fixed_separator or self.fixed_separator
        if fixed_sep and fixed_sep in text:
            # Split by fixed separator first
            chunks = text.split(fixed_sep)
            chunk_lengths = [counter(c) for c in chunks]

            boundaries = []
            current_pos = 0

            for chunk, length in zip(chunks, chunk_lengths):
                chunk_start = current_pos
                chunk_end = current_pos + len(chunk)

                if length > max_tokens:
                    # Phase 2: Recursively chunk oversized chunks
                    sub_chunks, sub_offsets = self._chunk_recursive(
                        chunk, max_tokens, counter, _start=chunk_start
                    )
                    boundaries.extend(sub_offsets)
                else:
                    boundaries.append((chunk_start, chunk_end))

                current_pos = chunk_end + len(fixed_sep)

            return boundaries

        # Fallback to original logic with enhancements
        boundaries = []

        if prefer_paragraphs:
            # Use paragraph boundaries first
            paragraphs = self.split_by_paragraphs(text)

            # Phase 1: Pre-compute token counts for all paragraphs (length caching)
            paragraph_lengths = [counter(p) for p in paragraphs]

            # Phase 2: Pre-calculate positions using accumulate
            current_pos = 0
            paragraph_positions = []
            for paragraph in paragraphs:
                pos = text.find(paragraph, current_pos)
                if pos == -1:
                    pos = current_pos
                paragraph_positions.append(pos)
                current_pos = pos + len(paragraph)

            # Phase 2: Use cumulative lengths and binary search for merging
            list(accumulate([len(p) for p in paragraphs], initial=0))

            # Use cached lengths to determine boundaries
            for i, (paragraph, length, start_pos) in enumerate(zip(paragraphs, paragraph_lengths, paragraph_positions)):
                if length > max_tokens:
                    # Recursively chunk oversized paragraph
                    sub_chunks, sub_offsets = self._chunk_recursive(
                        paragraph, max_tokens, counter, _start=start_pos
                    )
                    boundaries.extend(sub_offsets)
                else:
                    end_pos = start_pos + len(paragraph)
                    boundaries.append((start_pos, end_pos))
        else:
            # Use sentence boundaries
            sentences = self.split_by_sentences(text)

            # Phase 1: Pre-compute token counts for all sentences (length caching)
            sentence_lengths = [counter(s) for s in sentences]

            # Phase 2: Pre-calculate positions
            current_pos = 0
            sentence_positions = []
            for sentence in sentences:
                pos = text.find(sentence, current_pos)
                if pos == -1:
                    pos = current_pos
                sentence_positions.append(pos)
                current_pos = pos + len(sentence)

            # Use cached lengths
            for sentence, length, start_pos in zip(sentences, sentence_lengths, sentence_positions):
                if length > max_tokens:
                    # Recursively chunk oversized sentence
                    sub_chunks, sub_offsets = self._chunk_recursive(
                        sentence, max_tokens, counter, _start=start_pos
                    )
                    boundaries.extend(sub_offsets)
                else:
                    end_pos = start_pos + len(sentence)
                    boundaries.append((start_pos, end_pos))

        return boundaries

    def is_boundary_clear(
        self,
        text: str,
        start_pos: int,
        end_pos: int
    ) -> bool:
        """
        Check if boundary is clear (doesn't split mid-sentence/concept).

        Args:
            text: Full text
            start_pos: Start position
            end_pos: End position

        Returns:
            True if boundary is clear
        """
        chunk_text = text[start_pos:end_pos]

        # Check if starts/ends at sentence boundary
        if start_pos > 0:
            prev_char = text[start_pos - 1]
            if prev_char not in ['\n', '。', '！', '？', '.', '!', '?']:
                # Doesn't start at sentence boundary
                return False

        if end_pos < len(text):
            next_char = text[end_pos] if end_pos < len(text) else ''
            if next_char not in ['\n', '。', '！', '？', '.', '!', '?', ' ']:
                # Doesn't end at sentence boundary
                return False

        # Check for mid-word splits (basic check)
        if chunk_text and chunk_text[-1].isalnum():
            # Ends with alphanumeric - might be mid-word
            if end_pos < len(text) and text[end_pos].isalnum():
                return False

        return True
