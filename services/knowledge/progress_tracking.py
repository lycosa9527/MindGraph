"""
Progress tracking utilities for chunk test components.

Standardizes progress tracking format across ChunkTestDocument and ChunkTestResult.
"""
import re
from typing import Optional, Tuple


def format_progress_string(stage: str, method: Optional[str] = None) -> str:
    """
    Format progress string in standardized format: "stage (method)" or "stage".
    
    Args:
        stage: Current processing stage (e.g., 'chunking', 'embedding', 'indexing')
        method: Optional chunking method name (e.g., 'semchunk', 'spacy')
    
    Returns:
        Formatted progress string, e.g., "chunking (semchunk)" or "chunking"
    """
    if method:
        return f"{stage} ({method})"
    return stage


def parse_progress_string(progress: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Parse progress string to extract stage and method.
    
    Args:
        progress: Progress string in format "stage (method)" or "stage"
    
    Returns:
        Tuple of (stage, method) where method may be None
    """
    if not progress:
        return ("", None)

    # Match format: "stage (method)" e.g., "chunking (semchunk)"
    match = re.match(r"^(\w+)\s*\((\w+)\)$", progress)
    if match:
        return (match.group(1), match.group(2))

    # Fallback: simple stage name
    return (progress, None)


def get_progress_percent(
    stage: str,
    method_index: Optional[int] = None,
    total_methods: Optional[int] = None,
    stage_base: int = 0,
    sub_stage_progress: Optional[int] = None
) -> int:
    """
    Calculate progress percentage based on stage and method.
    
    Args:
        stage: Current stage name
        method_index: Current method index (0-based)
        total_methods: Total number of methods
        stage_base: Base percentage for this stage (default: 0)
        sub_stage_progress: Optional sub-stage progress (0-100) for stages like retrieval
    
    Returns:
        Progress percentage (0-100)
    """
    # Stage-based progress mapping for document processing workflow
    stage_progress = {
        "pending": 0,
        "queued": 0,
        "starting": 5,
        "extracting": 10,
        "cleaning": 10,
        "chunking": 15,
        "embedding": 60,
        "indexing": 75,
        "retrieval": 50,  # Base for RAG test retrieval phase
        "evaluation": 80,
        "completed": 100,
        "failed": 0,
        "cancelled": 0,
    }

    # Get base progress for stage
    base = stage_progress.get(stage, stage_base)

    # If method info provided, calculate method-specific progress
    if method_index is not None and total_methods is not None and total_methods > 0:
        # Method progress is distributed across the method processing range
        # For document processing workflow:
        #   - Chunking: 15-60% (45% range for 5 methods = 9% per method)
        #   - Embedding: 60-75% (15% range)
        #   - Indexing: 75-90% (15% range)
        # For RAG chunk test workflow:
        #   - Chunking: 0-50% (50% range)
        #   - Retrieval: 50-80% (30% range, includes embedding/indexing internally)

        if stage == "chunking":
            # Chunking: 15% + (method_index / total_methods) * 45% for doc processing
            # Or 0% + (method_index / total_methods) * 50% for RAG test
            # Use doc processing range by default
            method_progress = int(15 + (method_index / total_methods) * 45)
            return min(method_progress, 60)
        elif stage == "embedding":
            # Embedding: 60% + (method_index / total_methods) * 15%
            method_progress = int(60 + (method_index / total_methods) * 15)
            return min(method_progress, 75)
        elif stage == "indexing":
            # Indexing: 75% + (method_index / total_methods) * 15%
            method_progress = int(75 + (method_index / total_methods) * 15)
            return min(method_progress, 90)
        elif stage == "retrieval":
            # Retrieval phase: 50-80% for RAG test
            # If sub_stage_progress provided, interpolate within retrieval range
            if sub_stage_progress is not None:
                # Sub-stages: embedding (0-33%), indexing (33-66%), retrieval (66-100%)
                retrieval_base = 50
                retrieval_range = 30  # 50-80%
                if sub_stage_progress < 33:
                    # Embedding sub-stage: 50-60%
                    sub_base = retrieval_base
                    sub_range = retrieval_range / 3
                    return int(sub_base + (sub_stage_progress / 33) * sub_range)
                elif sub_stage_progress < 66:
                    # Indexing sub-stage: 60-70%
                    sub_base = retrieval_base + retrieval_range / 3
                    sub_range = retrieval_range / 3
                    return int(sub_base + ((sub_stage_progress - 33) / 33) * sub_range)
                else:
                    # Retrieval sub-stage: 70-80%
                    sub_base = retrieval_base + 2 * retrieval_range / 3
                    sub_range = retrieval_range / 3
                    return int(sub_base + ((sub_stage_progress - 66) / 34) * sub_range)
            else:
                # No sub-stage info, use base
                return base

    # Handle sub-stage progress for non-method stages
    if sub_stage_progress is not None and stage == "retrieval":
        retrieval_base = 50
        retrieval_range = 30
        return int(retrieval_base + (sub_stage_progress / 100) * retrieval_range)

    return base


def get_stage_display_name(stage: str, is_zh: bool = False) -> str:
    """
    Get localized display name for a stage.
    
    Args:
        stage: Stage name
        is_zh: Whether to return Chinese translation
    
    Returns:
        Display name for the stage
    """
    labels = {
        "queued": ("Queued", "排队中"),
        "extracting": ("Extracting", "提取文本"),
        "cleaning": ("Cleaning", "清理文本"),
        "chunking": ("Chunking", "分块处理"),
        "embedding": ("Embedding", "生成向量"),
        "indexing": ("Indexing", "建立索引"),
        "starting": ("Starting", "开始处理"),
        "retrieval": ("Retrieval", "检索测试"),
        "evaluation": ("Evaluation", "评估分析"),
        "completed": ("Completed", "已完成"),
        "failed": ("Failed", "失败"),
        "cancelled": ("Cancelled", "已取消"),
        "pending": ("Pending", "等待中"),
    }

    label_pair = labels.get(stage, (stage, stage))
    return label_pair[1] if is_zh else label_pair[0]


def get_method_display_name(method: str) -> str:
    """
    Get display name for a chunking method.
    
    Args:
        method: Method name (e.g., 'semchunk', 'spacy')
    
    Returns:
        Display name (e.g., 'SemChunk', 'spaCy')
    """
    method_names = {
        "semchunk": "SemChunk",
        "spacy": "spaCy",
        "chonkie": "Chonkie",
        "langchain": "LangChain",
        "mindchunk": "MindChunk",
    }
    return method_names.get(method, method.capitalize())


def validate_progress(
    current_progress: int,
    previous_progress: Optional[int] = None,
    stage: Optional[str] = None
) -> Tuple[int, bool]:
    """
    Validate progress to ensure it never decreases and is within valid range.
    
    Args:
        current_progress: Current progress percentage (0-100)
        previous_progress: Previous progress percentage (optional)
        stage: Current stage name (optional, for logging)
    
    Returns:
        Tuple of (validated_progress, is_valid)
    """
    # Ensure progress is within valid range
    validated_progress = max(0, min(100, current_progress))
    
    # Check if progress decreased (invalid)
    is_valid = True
    if previous_progress is not None and validated_progress < previous_progress:
        is_valid = False
        # Log warning but don't fail - use previous progress
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "[ProgressTracking] Progress decreased from %s%% to %s%% (stage=%s). "
            "Using previous progress value.",
            previous_progress, validated_progress, stage
        )
        validated_progress = previous_progress
    
    return validated_progress, is_valid


def ensure_completion_progress(
    current_progress: int,
    expected_completion: int = 100
) -> int:
    """
    Ensure progress reaches completion value.
    
    Args:
        current_progress: Current progress percentage
        expected_completion: Expected completion percentage (default: 100)
    
    Returns:
        Progress percentage, ensuring it reaches expected_completion
    """
    if current_progress >= expected_completion:
        return expected_completion
    return max(current_progress, expected_completion)
