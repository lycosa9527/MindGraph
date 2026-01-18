"""
Data models for LLM-based semantic chunking.

Defines chunk structures for different chunking strategies:
- General: Flat chunks
- Parent-Child: Hierarchical chunks
- Q&A: Question-answer pairs
- Teaching: Enhanced chunks for educational content
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional



@dataclass
class Chunk:
    """
    Base chunk model representing a text segment.

    Compatible with existing ChunkingService.Chunk model.
    """
    text: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: Optional[int] = None

    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count is None and self.text:
            # Will be set by TokenCounter if needed
            pass


@dataclass
class ChildChunk(Chunk):
    """Child chunk in a parent-child hierarchy."""
    parent_id: Optional[str] = None
    parent_text: Optional[str] = None
    parent_index: Optional[int] = None


@dataclass
class ParentChunk:
    """
    Parent chunk containing multiple child chunks.

    Only child chunks are embedded; parent provides context.
    """
    text: str
    start_char: int
    end_char: int
    chunk_index: int
    children: List[ChildChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: Optional[int] = None

    def add_child(self, child: ChildChunk):
        """Add a child chunk."""
        child.parent_id = f"parent_{self.chunk_index}"
        child.parent_text = self.text
        child.parent_index = self.chunk_index
        self.children.append(child)

    @property
    def child_count(self) -> int:
        """Get number of child chunks."""
        return len(self.children)


@dataclass
class QAChunk(Chunk):
    """
    Question-answer pair chunk.

    Used for FAQ documents and Q&A structures.
    """
    question: str = ""
    answer: str = ""
    qa_index: Optional[int] = field(default=None)

    def __post_init__(self):
        """Set text to combined Q&A format."""
        if not self.text and self.question:
            self.text = f"Q: {self.question}\nA: {self.answer}"
        # Ensure token_count is set if not provided
        if self.token_count is None and self.text:
            pass  # Will be set by TokenCounter if needed


@dataclass
class CodeBlock:
    """Represents a code block in a chunk."""
    code: str
    language: Optional[str] = None
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None
    explanation: Optional[str] = None


@dataclass
class Formula:
    """Represents a mathematical formula in a chunk."""
    formula: str
    format: str = "latex"  # latex, mathml, plain
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


@dataclass
class TeachingChunk(Chunk):
    """
    Enhanced chunk for teaching materials.

    Includes educational metadata and relationships.
    """
    content_type: str = "theory"  # "theory", "example", "exercise", "summary", "code", "formula"
    learning_objectives: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)

    # Hierarchical relationships
    parent_section: Optional[str] = field(default=None)
    parent_lesson: Optional[str] = field(default=None)
    parent_module: Optional[str] = field(default=None)

    # Links to related content
    related_theory_chunks: List[int] = field(default_factory=list)
    related_example_chunks: List[int] = field(default_factory=list)
    related_exercise_chunks: List[int] = field(default_factory=list)

    # Educational metadata
    difficulty_level: Optional[str] = field(default=None)  # "beginner", "intermediate", "advanced"
    estimated_time: Optional[int] = field(default=None)  # Minutes
    assessment_type: Optional[str] = field(default=None)  # "quiz", "assignment", "project"

    # Special content
    code_block: Optional[CodeBlock] = field(default=None)
    formula: Optional[Formula] = field(default=None)


@dataclass
class ExerciseChunk(Chunk):
    """
    Chunk for individual exercise/question.

    Used for exercise books and question collections.
    """
    question_type: str = "short_answer"  # "multiple_choice", "short_answer", "essay", "calculation", "true_false"
    question_number: Optional[int] = field(default=None)
    quiz_section: Optional[str] = field(default=None)  # "Quiz 1", "Test 2", etc.

    # Question components (for multiple choice)
    question_text: Optional[str] = field(default=None)  # Just the question
    options: List[str] = field(default_factory=list)  # A), B), C), D) options
    correct_answer: Optional[str] = field(default=None)  # If available

    # Answer/solution (if included)
    answer: Optional[str] = field(default=None)
    solution: Optional[str] = field(default=None)

    # Metadata
    difficulty_level: Optional[str] = field(default=None)
    topic: Optional[str] = field(default=None)  # Extracted topic
    estimated_time: Optional[int] = field(default=None)  # Minutes


@dataclass
class DocumentStructure:
    """
    Detected document structure from sampling.

    Cached and reused for full document chunking.
    """
    document_id: str
    structure_type: str  # "general", "parent_child", "qa"
    toc: List[Dict[str, Any]] = field(default_factory=list)
    chunking_rules: Dict[str, Any] = field(default_factory=dict)
    document_type: Optional[str] = None  # "book", "article", "faq", "exercise_book", etc.
    detected_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching."""
        return {
            "document_id": self.document_id,
            "structure_type": self.structure_type,
            "toc": self.toc,
            "chunking_rules": self.chunking_rules,
            "document_type": self.document_type,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentStructure":
        """Create from dictionary (from cache)."""
        return cls(
            document_id=data["document_id"],
            structure_type=data["structure_type"],
            toc=data.get("toc", []),
            chunking_rules=data.get("chunking_rules", {}),
            document_type=data.get("document_type"),
            detected_at=data.get("detected_at"),
        )
