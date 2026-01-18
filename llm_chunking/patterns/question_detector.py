"""
Question detection for exercise books and Q&A documents.

Detects question boundaries using patterns:
- Numbered questions: "Question 1:", "Q1:", "1."
- Multiple choice: Questions with A), B), C), D)
- True/False: Questions with True/False options
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class QuestionDetector:
    """
    Detect questions using pattern matching.

    Fast pattern-based approach for exercise books.
    """

    # Question patterns
    PATTERNS = [
        # "Question 1:", "Q1:", "Problem 1:"
        r'(?:Question|Q|Problem|Exercise)\s*(\d+)[\.\):]\s*(.+?)(?=(?:Question|Q|Problem|Exercise)\s*\d+[\.\):]|$)',

        # Numbered questions: "1.", "2.", etc.
        r'^(\d+)[\.\)]\s+(.+?)(?=^\d+[\.\)]|$)',

        # Multiple choice (has A), B), C), D))
        r'(.+?)\n(?:[A-E]\)|\([A-E]\)).+?(?=\n\n|$)',

        # Quiz sections: "Quiz 1:", "Test 2:"
        r'(Quiz|Test|Exam)\s+(\d+)[\.\):]\s*(.+?)(?=(?:Quiz|Test|Exam)\s+\d+[\.\):]|$)',
    ]

    def __init__(self):
        """Initialize question detector."""
        self.patterns = [re.compile(p, re.MULTILINE | re.DOTALL) for p in self.PATTERNS]

    def detect_questions(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect questions using patterns.

        Args:
            text: Text to analyze

        Returns:
            List of question dicts with 'number', 'text', 'start_pos', 'end_pos'
        """
        questions = []
        seen_positions = set()

        for pattern in self.patterns:
            for match in pattern.finditer(text):
                start_pos = match.start()

                # Avoid duplicates
                if start_pos in seen_positions:
                    continue
                seen_positions.add(start_pos)

                question_text = match.group(0)
                question_number = match.group(1) if len(match.groups()) > 0 else None

                questions.append({
                    "number": question_number,
                    "text": question_text.strip(),
                    "start_pos": start_pos,
                    "end_pos": match.end(),
                    "type": self._classify_question_type(question_text)
                })

        # Sort by position
        questions.sort(key=lambda x: x["start_pos"])

        return questions

    def _classify_question_type(self, question_text: str) -> str:
        """
        Classify question type based on patterns.

        Args:
            question_text: Question text

        Returns:
            Question type: "multiple_choice", "true_false", "short_answer", "essay", "calculation"
        """
        question_lower = question_text.lower()

        # Multiple choice
        if re.search(r'[A-E]\)|\([A-E]\)', question_text):
            return "multiple_choice"

        # True/False
        if re.search(r'\b(True|False|T|F)[\.\):]', question_text, re.IGNORECASE):
            return "true_false"

        # Calculation
        if re.search(r'\b(calculate|compute|solve|derive|find)', question_lower):
            return "calculation"

        # Essay (long questions)
        if len(question_text) > 500:
            return "essay"

        # Short answer (default)
        return "short_answer"

    def extract_options(self, question_text: str) -> List[str]:
        """
        Extract multiple choice options.

        Args:
            question_text: Question text with options

        Returns:
            List of option texts
        """
        options = []

        # Match A), B), C), D) patterns
        option_pattern = r'([A-E])[\.\)]\s*(.+?)(?=[A-E][\.\)]|$)'
        for match in re.finditer(option_pattern, question_text, re.MULTILINE):
            option_text = match.group(2).strip()
            options.append(option_text)

        return options

    def detect_quiz_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect quiz/test sections.

        Args:
            text: Text to analyze

        Returns:
            List of quiz section dicts
        """
        quiz_pattern = r'(Quiz|Test|Exam)\s+(\d+)[\.\):]\s*(.+?)(?=(?:Quiz|Test|Exam)\s+\d+[\.\):]|$)'

        sections = []
        for match in re.finditer(quiz_pattern, text, re.MULTILINE | re.DOTALL):
            section_type = match.group(1)
            section_number = match.group(2)
            section_text = match.group(3)

            # Count questions in section
            questions = self.detect_questions(section_text)

            sections.append({
                "type": section_type,
                "number": section_number,
                "text": section_text,
                "start_pos": match.start(),
                "end_pos": match.end(),
                "question_count": len(questions),
            })

        return sections
