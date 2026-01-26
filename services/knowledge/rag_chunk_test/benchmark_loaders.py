"""
Benchmark Dataset Loaders for RAG Chunk Testing
================================================

Loaders for benchmark datasets: FinanceBench, KG-RAG, FRAMES, PubMedQA.
Supports local files first, then falls back to Hugging Face.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
import csv
import json
import logging

try:
    from datasets import load_dataset
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False
    logging.warning("[BenchmarkLoaders] datasets library not installed. Hugging Face fallback disabled.")

try:
    from models.domain.knowledge_space import (
        ChunkTestDocument,
        ChunkTestDocumentChunk
    )
    HAS_CHUNK_TEST_MODELS = True
except ImportError:
    HAS_CHUNK_TEST_MODELS = False


logger = logging.getLogger(__name__)


class BenchmarkLoader(ABC):
    """Base class for benchmark dataset loaders."""

    def __init__(self, local_dir: Optional[str] = None):
        """
        Initialize loader.

        Args:
            local_dir: Local directory path (default: ./rag-test/{dataset_name}/)
        """
        self.dataset_name = self.get_dataset_name()
        if local_dir:
            self.local_dir = Path(local_dir)
        else:
            project_root = Path(__file__).parent.parent.parent.parent
            self.local_dir = project_root / "rag-test" / self.dataset_name.lower().replace("-", "_")
        self.local_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def get_dataset_name(self) -> str:
        """Return dataset identifier."""

    @abstractmethod
    def load_documents(self) -> List[Dict[str, Any]]:
        """
        Load documents from dataset.

        Returns:
            List of documents with format:
            [{"id": str, "text": str, "metadata": dict}]
        """

    @abstractmethod
    def load_queries(self) -> List[Dict[str, Any]]:
        """
        Load test queries from dataset.

        Returns:
            List of queries with format:
            [{"query": str, "expected_chunk_ids": List[int],
              "relevance_scores": Dict[int, float]}]
        """

    def _load_from_local(self, filename: str) -> Optional[Any]:
        """
        Try to load file from local directory.

        Args:
            filename: Filename to load

        Returns:
            Loaded data or None if not found
        """
        file_path = self.local_dir / filename
        if not file_path.exists():
            return None

        try:
            if filename.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif filename.endswith('.jsonl'):
                data = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        data.append(json.loads(line))
                return data
            elif filename.endswith('.csv'):
                data = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                return data
        except Exception as e:
            logger.warning(
                "[BenchmarkLoaders] Failed to load local file %s: %s",
                file_path,
                e
            )
        return None

    def _load_from_huggingface(self, dataset_path: str, config: Optional[str] = None) -> Optional[Any]:
        """
        Load dataset from Hugging Face.

        Args:
            dataset_path: Hugging Face dataset path
            config: Optional dataset configuration

        Returns:
            Dataset object or None if failed
        """
        if not HAS_DATASETS:
            logger.warning(
                "[BenchmarkLoaders] Cannot load from Hugging Face: datasets library not installed"
            )
            return None

        try:
            if config:
                return load_dataset(dataset_path, config)
            return load_dataset(dataset_path)
        except Exception as e:
            logger.error(
                "[BenchmarkLoaders] Failed to load dataset %s from Hugging Face: %s",
                dataset_path,
                e
            )
            return None


class FinanceBenchLoader(BenchmarkLoader):
    """Loader for FinanceBench dataset."""

    def get_dataset_name(self) -> str:
        return "FinanceBench"

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load FinanceBench documents."""
        # Try local first - check both JSON and JSONL
        local_data = self._load_from_local("documents.json")
        if not local_data:
            local_data = self._load_from_local("documents.jsonl")
        if local_data:
            logger.info("[FinanceBenchLoader] Loaded documents from local files")
            return self._normalize_documents(local_data)

        # Try Hugging Face
        dataset = self._load_from_huggingface("PatronusAI/financebench")
        if dataset:
            logger.info("[FinanceBenchLoader] Loaded documents from Hugging Face")
            return self._normalize_hf_dataset(dataset)

        raise ValueError("FinanceBench dataset not found locally or on Hugging Face")

    def load_queries(self) -> List[Dict[str, Any]]:
        """Load FinanceBench queries."""
        # Try local first - check both JSON and JSONL
        local_data = self._load_from_local("queries.json")
        if not local_data:
            local_data = self._load_from_local("queries.jsonl")
        if local_data:
            logger.info("[FinanceBenchLoader] Loaded queries from local files")
            return self._normalize_queries(local_data)

        # Try Hugging Face
        dataset = self._load_from_huggingface("PatronusAI/financebench")
        if dataset:
            logger.info("[FinanceBenchLoader] Loaded queries from Hugging Face")
            return self._normalize_hf_queries(dataset)

        raise ValueError("FinanceBench queries not found locally or on Hugging Face")

    def _normalize_documents(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize documents to common format."""
        documents = []
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    # FinanceBench format: extract evidence text as document content
                    evidence_texts = []
                    if "evidence" in item and isinstance(item["evidence"], list):
                        for ev in item["evidence"]:
                            if isinstance(ev, dict) and "evidence_text" in ev:
                                evidence_texts.append(ev["evidence_text"])

                    # Use evidence text as document content, or fallback to other fields
                    doc_text = (
                        "\n\n".join(evidence_texts)
                        if evidence_texts
                        else item.get("text", item.get("content", ""))
                    )

                    doc = {
                        "id": item.get("financebench_id", item.get("id", f"doc_{idx}")),
                        "text": doc_text,
                        "metadata": {
                            k: v for k, v in item.items()
                            if k not in [
                                "id", "financebench_id", "text", "content",
                                "evidence", "question", "answer"
                            ]
                        }
                    }
                    documents.append(doc)
        elif isinstance(data, dict):
            # Handle Hugging Face dataset format
            return self._normalize_hf_dataset(data)
        return documents

    def _normalize_queries(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize queries to common format."""
        queries = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    query = {
                        "query": item.get("query", item.get("question", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {})
                    }
                    if query["query"]:  # Only add non-empty queries
                        queries.append(query)
        elif isinstance(data, dict):
            return self._normalize_hf_queries(data)
        return queries

    def _normalize_hf_dataset(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to documents."""
        documents = []
        # Try different splits
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for idx, item in enumerate(split):
                    doc = {
                        "id": item.get("id", f"doc_{split_name}_{idx}"),
                        "text": item.get("text", item.get("content", item.get("document", ""))),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "content", "document"]}
                    }
                    documents.append(doc)
                break
        return documents

    def _normalize_hf_queries(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to queries."""
        queries = []
        # Try different splits
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for item in split:
                    query = {
                        "query": item.get("query", item.get("question", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {}),
                        "answer": item.get("answer", "")
                    }
                    if query["query"]:
                        queries.append(query)
                break
        return queries


class KGRAGLoader(BenchmarkLoader):
    """Loader for KG-RAG (BiomixQA) dataset."""

    def get_dataset_name(self) -> str:
        return "KG-RAG"

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load KG-RAG documents."""
        local_data = self._load_from_local("documents.json")
        if not local_data:
            local_data = self._load_from_local("documents.jsonl")
        if local_data:
            logger.info("[KGRAGLoader] Loaded documents from local files")
            return self._normalize_documents(local_data)

        dataset = self._load_from_huggingface("kg-rag/BiomixQA", "mcq")
        if dataset:
            logger.info("[KGRAGLoader] Loaded documents from Hugging Face")
            return self._normalize_hf_dataset(dataset)

        raise ValueError("KG-RAG dataset not found locally or on Hugging Face")

    def load_queries(self) -> List[Dict[str, Any]]:
        """Load KG-RAG queries."""
        local_data = self._load_from_local("queries.json")
        if not local_data:
            local_data = self._load_from_local("queries.jsonl")
        if local_data:
            logger.info("[KGRAGLoader] Loaded queries from local files")
            return self._normalize_queries(local_data)

        dataset = self._load_from_huggingface("kg-rag/BiomixQA", "mcq")
        if dataset:
            logger.info("[KGRAGLoader] Loaded queries from Hugging Face")
            return self._normalize_hf_queries(dataset)

        raise ValueError("KG-RAG queries not found locally or on Hugging Face")

    def _normalize_documents(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize documents to common format."""
        documents = []
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    doc = {
                        "id": item.get("id", f"doc_{idx}"),
                        "text": item.get("text", item.get("context", item.get("document", ""))),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "context", "document"]}
                    }
                    documents.append(doc)
        elif isinstance(data, dict):
            return self._normalize_hf_dataset(data)
        return documents

    def _normalize_queries(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize queries to common format."""
        queries = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    query = {
                        "query": item.get("query", item.get("question", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {})
                    }
                    if query["query"]:  # Only add non-empty queries
                        queries.append(query)
        elif isinstance(data, dict):
            return self._normalize_hf_queries(data)
        return queries

    def _normalize_hf_dataset(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to documents."""
        documents = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for idx, item in enumerate(split):
                    doc = {
                        "id": item.get("id", f"doc_{split_name}_{idx}"),
                        "text": item.get("context", item.get("text", item.get("document", ""))),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "context", "document"]}
                    }
                    documents.append(doc)
                break
        return documents

    def _normalize_hf_queries(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to queries."""
        queries = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for item in split:
                    query = {
                        "query": item.get("question", item.get("query", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {})
                    }
                    if query["query"]:
                        queries.append(query)
                break
        return queries


class FRAMESLoader(BenchmarkLoader):
    """Loader for FRAMES dataset."""

    def get_dataset_name(self) -> str:
        return "FRAMES"

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load FRAMES documents."""
        local_data = self._load_from_local("documents.json")
        if not local_data:
            local_data = self._load_from_local("documents.jsonl")
        if local_data:
            logger.info("[FRAMESLoader] Loaded documents from local files")
            return self._normalize_documents(local_data)

        dataset = self._load_from_huggingface("google/frames-benchmark")
        if dataset:
            logger.info("[FRAMESLoader] Loaded documents from Hugging Face")
            return self._normalize_hf_dataset(dataset)

        raise ValueError("FRAMES dataset not found locally or on Hugging Face")

    def load_queries(self) -> List[Dict[str, Any]]:
        """Load FRAMES queries."""
        local_data = self._load_from_local("queries.json")
        if not local_data:
            local_data = self._load_from_local("queries.jsonl")
        if local_data:
            logger.info("[FRAMESLoader] Loaded queries from local files")
            return self._normalize_queries(local_data)

        dataset = self._load_from_huggingface("google/frames-benchmark")
        if dataset:
            logger.info("[FRAMESLoader] Loaded queries from Hugging Face")
            return self._normalize_hf_queries(dataset)

        raise ValueError("FRAMES queries not found locally or on Hugging Face")

    def _normalize_documents(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize documents to common format."""
        documents = []
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    doc = {
                        "id": item.get("id", f"doc_{idx}"),
                        "text": item.get("text", item.get("content", "")),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "content"]}
                    }
                    documents.append(doc)
        elif isinstance(data, dict):
            return self._normalize_hf_dataset(data)
        return documents

    def _normalize_queries(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize queries to common format."""
        queries = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # FRAMES uses "Answer" field
                    answer = item.get("Answer", "")
                    query = {
                        "query": item.get("query", item.get("question", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {}),
                        "answer": answer
                    }
                    if query["query"]:  # Only add non-empty queries
                        queries.append(query)
        elif isinstance(data, dict):
            return self._normalize_hf_queries(data)
        return queries

    def _normalize_hf_dataset(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to documents."""
        documents = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for idx, item in enumerate(split):
                    doc = {
                        "id": item.get("id", f"doc_{split_name}_{idx}"),
                        "text": item.get("text", item.get("content", item.get("document", ""))),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "content", "document"]}
                    }
                    documents.append(doc)
                break
        return documents

    def _normalize_hf_queries(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to queries."""
        queries = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for item in split:
                    # FRAMES uses "Answer" field
                    answer = item.get("Answer", "")
                    query = {
                        "query": item.get("query", item.get("question", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {}),
                        "answer": answer
                    }
                    if query["query"]:
                        queries.append(query)
                break
        return queries


class PubMedQALoader(BenchmarkLoader):
    """Loader for PubMedQA dataset."""

    def get_dataset_name(self) -> str:
        return "PubMedQA"

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load PubMedQA documents."""
        local_data = self._load_from_local("documents.json")
        if not local_data:
            local_data = self._load_from_local("documents.jsonl")
        if local_data:
            logger.info("[PubMedQALoader] Loaded documents from local files")
            return self._normalize_documents(local_data)

        dataset = self._load_from_huggingface("bigbio/pubmed_qa", "pqa_labeled")
        if dataset:
            logger.info("[PubMedQALoader] Loaded documents from Hugging Face")
            return self._normalize_hf_dataset(dataset)

        raise ValueError("PubMedQA dataset not found locally or on Hugging Face")

    def load_queries(self) -> List[Dict[str, Any]]:
        """Load PubMedQA queries."""
        local_data = self._load_from_local("queries.json")
        if not local_data:
            local_data = self._load_from_local("queries.jsonl")
        if local_data:
            logger.info("[PubMedQALoader] Loaded queries from local files")
            return self._normalize_queries(local_data)

        dataset = self._load_from_huggingface("bigbio/pubmed_qa", "pqa_labeled")
        if dataset:
            logger.info("[PubMedQALoader] Loaded queries from Hugging Face")
            return self._normalize_hf_queries(dataset)

        raise ValueError("PubMedQA queries not found locally or on Hugging Face")

    def _normalize_documents(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize documents to common format."""
        documents = []
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    doc = {
                        "id": item.get("id", f"doc_{idx}"),
                        "text": item.get("context", item.get("text", "")),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "context"]}
                    }
                    documents.append(doc)
        elif isinstance(data, dict):
            return self._normalize_hf_dataset(data)
        return documents

    def _normalize_queries(self, data: Any) -> List[Dict[str, Any]]:
        """Normalize queries to common format."""
        queries = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # PubMedQA uses "final_decision" or "long_answer"
                    answer = item.get("final_decision", item.get("long_answer", ""))
                    query = {
                        "query": item.get("question", item.get("query", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {}),
                        "answer": answer
                    }
                    queries.append(query)
        elif isinstance(data, dict):
            return self._normalize_hf_queries(data)
        return queries

    def _normalize_hf_dataset(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to documents."""
        documents = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for idx, item in enumerate(split):
                    doc = {
                        "id": item.get("id", f"doc_{split_name}_{idx}"),
                        "text": item.get("context", item.get("text", "")),
                        "metadata": {k: v for k, v in item.items() if k not in ["id", "text", "context"]}
                    }
                    documents.append(doc)
                break
        return documents

    def _normalize_hf_queries(self, dataset: Any) -> List[Dict[str, Any]]:
        """Normalize Hugging Face dataset to queries."""
        queries = []
        for split_name in ["train", "test", "validation", "default"]:
            if hasattr(dataset, split_name) and dataset[split_name]:
                split = dataset[split_name]
                for item in split:
                    query = {
                        "query": item.get("question", item.get("query", "")),
                        "expected_chunk_ids": item.get("expected_chunk_ids", []),
                        "relevance_scores": item.get("relevance_scores", {})
                    }
                    if query["query"]:
                        queries.append(query)
                break
        return queries


class UserDocumentLoader(BenchmarkLoader):
    """Loader for user's uploaded documents."""

    def __init__(self, db, user_id: int, document_ids: List[int]):
        """
        Initialize user document loader.

        Args:
            db: Database session
            user_id: User ID
            document_ids: List of document IDs to load
        """
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.document_ids = document_ids

    def get_dataset_name(self) -> str:
        return "user_documents"

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load chunk test documents from database."""
        if not HAS_CHUNK_TEST_MODELS:
            raise ImportError(
                "Chunk test document models not available. "
                "Cannot load user documents."
            )

        documents = []
        for doc_id in self.document_ids:
            doc = self.db.query(ChunkTestDocument).filter(
                ChunkTestDocument.id == doc_id,
                ChunkTestDocument.user_id == self.user_id
            ).first()

            if not doc:
                logger.warning(
                    "[UserDocumentLoader] Document %s not found or access denied",
                    doc_id
                )
                continue

            # Extract original text from file (not from chunks)
            # This ensures we get the original document text, not reconstructed from chunks
            # which may have been processed with different chunking methods
            from services.knowledge.document_processor import get_document_processor
            from services.knowledge.document_cleaner import get_document_cleaner

            processor = get_document_processor()
            cleaner = get_document_cleaner()

            # Extract text from file
            if doc.file_type == 'application/pdf':
                text, _ = processor.extract_text_with_pages(doc.file_path, doc.file_type)
            else:
                text = processor.extract_text(doc.file_path, doc.file_type)

            # Ensure text is string
            if isinstance(text, list):
                text = "\n".join(str(item) for item in text)
            if not isinstance(text, str):
                text = str(text) if text else ""

            # Clean text (same as ChunkTestDocumentService)
            full_text = cleaner.clean(
                text,
                remove_extra_spaces=True,
                remove_urls_emails=False
            )

            # Get chunk count for metadata (optional, for reference)
            chunks = self.db.query(ChunkTestDocumentChunk).filter(
                ChunkTestDocumentChunk.document_id == doc_id
            ).count()

            documents.append({
                "id": f"user_doc_{doc_id}",
                "text": full_text,
                "metadata": {
                    "document_id": doc_id,
                    "file_name": doc.file_name,
                    "file_type": doc.file_type,
                    "chunk_count": len(chunks)
                }
            })

        logger.info(
            "[UserDocumentLoader] Loaded %s documents for user %s",
            len(documents),
            self.user_id
        )
        return documents

    def load_queries(self) -> List[Dict[str, Any]]:
        """
        Load queries for user documents.

        Note: User documents don't have predefined queries.
        Returns empty list - queries should be provided separately.
        """
        return []


def get_benchmark_loader(dataset_name: str, **kwargs) -> BenchmarkLoader:
    """
    Get benchmark loader by name.

    Args:
        dataset_name: Dataset name ('FinanceBench', 'KG-RAG', 'FRAMES', 'PubMedQA')
        **kwargs: Additional arguments for loader

    Returns:
        BenchmarkLoader instance
    """
    loaders = {
        "FinanceBench": FinanceBenchLoader,
        "KG-RAG": KGRAGLoader,
        "FRAMES": FRAMESLoader,
        "PubMedQA": PubMedQALoader,
    }

    loader_class = loaders.get(dataset_name)
    if not loader_class:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    return loader_class(**kwargs)
