"""
Script to download all RAG benchmark datasets from Hugging Face.

Author: lycosa9527
Made by: MindSpring Team
"""
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from datasets import load_dataset
    HAS_DATASETS = True
    _LOAD_DATASET_FUNC: Optional[Callable[..., Any]] = load_dataset
except ImportError:
    HAS_DATASETS = False
    _LOAD_DATASET_FUNC = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _get_project_root() -> Path:
    """
    Get project root directory.

    Calculates from benchmark_loaders.py location for consistency.
    """
    # Go up from utils/ to rag_chunk_test/, then use same calculation as benchmark_loaders.py
    rag_chunk_test_dir = Path(__file__).parent.parent
    project_root = rag_chunk_test_dir.parent.parent.parent
    return project_root


def download_datasets():
    """Download all benchmark datasets from Hugging Face."""
    if not HAS_DATASETS:
        logger.error("datasets library not installed. Run: pip install datasets>=2.14.0")
        return

    project_root = _get_project_root()
    rag_test_dir = project_root / "rag-test"
    rag_test_dir.mkdir(parents=True, exist_ok=True)

    datasets_to_download = [
        {
            "name": "FinanceBench",
            "hf_path": "PatronusAI/financebench",
            "config": None,
            "folder": "financebench"
        },
        {
            "name": "KG-RAG (BiomixQA MCQ)",
            "hf_path": "kg-rag/BiomixQA",
            "config": "mcq",
            "folder": "kg-rag"
        },
        {
            "name": "KG-RAG (BiomixQA True/False)",
            "hf_path": "kg-rag/BiomixQA",
            "config": "true_false",
            "folder": "kg-rag"
        },
        {
            "name": "FRAMES",
            "hf_path": "google/frames-benchmark",
            "config": None,
            "folder": "frames"
        },
        {
            "name": "PubMedQA",
            "hf_path": "qiaojin/PubMedQA",
            "config": "pqa_labeled",
            "folder": "pubmedqa"
        }
    ]

    for dataset_info in datasets_to_download:
        logger.info("\n%s", "=" * 60)
        logger.info("Downloading: %s", dataset_info['name'])
        logger.info("HF Path: %s", dataset_info['hf_path'])
        if dataset_info['config']:
            logger.info("Config: %s", dataset_info['config'])
        logger.info("%s", "=" * 60)

        try:
            # Download dataset
            if not HAS_DATASETS or _LOAD_DATASET_FUNC is None:
                logger.error("load_dataset is not available")
                continue
            if dataset_info['config']:
                dataset = _LOAD_DATASET_FUNC(dataset_info['hf_path'], dataset_info['config'])
            else:
                dataset = _LOAD_DATASET_FUNC(dataset_info['hf_path'])

            # Create folder
            dataset_folder = rag_test_dir / dataset_info['folder']
            dataset_folder.mkdir(parents=True, exist_ok=True)

            # Convert to list format and save
            documents = []
            queries = []

            # Process dataset splits - Hugging Face datasets use dict-like access
            for split_name in ["train", "test", "validation", "default"]:
                if split_name in dataset and len(dataset[split_name]) > 0:
                    split_len = len(dataset[split_name])
                    logger.info("Processing split: %s (%s items)", split_name, split_len)
                    split = dataset[split_name]

                    # Get sample to understand structure
                    if len(split) > 0:
                        sample = split[0]
                        sample_keys = (
                            list(sample.keys())
                            if isinstance(sample, dict)
                            else 'N/A'
                        )
                        logger.info("Sample keys: %s", sample_keys)

                    for idx, item_raw in enumerate(split):
                        # Type guard: Hugging Face dataset items are dictionaries
                        if not isinstance(item_raw, dict):
                            logger.warning(
                                "Skipping non-dict item at index %s in %s",
                                idx,
                                split_name
                            )
                            continue

                        item: Dict[str, Any] = item_raw

                        # Extract document based on dataset-specific format
                        default_id = f"{split_name}_{idx}"
                        doc_id = item.get(
                            "id",
                            item.get("financebench_id", item.get("pubid", default_id))
                        )

                        # Dataset-specific document extraction
                        doc_text = ""
                        if dataset_info['name'] == "FinanceBench":
                            # FinanceBench: extract evidence text
                            if "evidence" in item and isinstance(item["evidence"], list):
                                evidence_texts = []
                                for ev in item["evidence"]:
                                    if isinstance(ev, dict) and "evidence_text" in ev:
                                        evidence_texts.append(ev["evidence_text"])
                                doc_text = (
                                    "\n\n".join(evidence_texts)
                                    if evidence_texts
                                    else ""
                                )
                        elif dataset_info['name'].startswith("KG-RAG"):
                            # KG-RAG BiomixQA: 'text' field contains context
                            doc_text = item.get("text", "")
                        elif dataset_info['name'] == "FRAMES":
                            # FRAMES: Answer field contains document content
                            doc_text = item.get("Answer", "")
                        elif dataset_info['name'] == "PubMedQA":
                            # PubMedQA: 'context' field contains document
                            context = item.get("context", "")
                            if isinstance(context, dict):
                                contexts_list = context.get("contexts", [""])
                                doc_text = (
                                    contexts_list[0]
                                    if isinstance(contexts_list, list) and contexts_list
                                    else str(context)
                                )
                            else:
                                doc_text = str(context) if context else ""
                        else:
                            # Generic: try common field names
                            doc_text = item.get(
                                "text",
                                item.get(
                                    "content",
                                    item.get(
                                        "context",
                                        item.get(
                                            "document",
                                            item.get("long_answer", "")
                                        )
                                    )
                                )
                            )

                        # Ensure doc_text is a string
                        if isinstance(doc_text, dict):
                            doc_text = str(doc_text)
                        elif not isinstance(doc_text, str):
                            doc_text = str(doc_text) if doc_text else ""

                        if doc_text and doc_text.strip():
                            # Build metadata excluding text fields
                            exclude_fields = [
                                "id", "financebench_id", "pubid", "text",
                                "content", "context", "document",
                                "long_answer", "evidence", "question",
                                "query", "answer", "Answer",
                                "Prompt", "option_A", "option_B",
                                "option_C", "option_D", "option_E",
                                "correct_answer", "final_decision"
                            ]
                            documents.append({
                                "id": doc_id,
                                "text": doc_text,
                                "metadata": {
                                    k: v for k, v in item.items()
                                    if k not in exclude_fields
                                }
                            })

                        # Extract query based on dataset format
                        query_text = ""
                        if dataset_info['name'] == "FinanceBench":
                            query_text = item.get("question", "")
                        elif dataset_info['name'].startswith("KG-RAG"):
                            # KG-RAG: create question from options
                            text = item.get("text", "")
                            options = [
                                item.get(f"option_{chr(65+i)}", "")
                                for i in range(5)
                            ]  # A-E
                            correct = item.get("correct_answer", "")
                            options_str = " | ".join([
                                f"{chr(65+i)}: {opt}"
                                for i, opt in enumerate(options)
                                if opt
                            ])
                            query_text = (
                                f"{text} Options: {options_str} Correct: {correct}"
                            )
                        elif dataset_info['name'] == "FRAMES":
                            query_text = item.get("Prompt", "")
                        elif dataset_info['name'] == "PubMedQA":
                            query_text = item.get("question", "")
                        else:
                            query_text = item.get(
                                "question",
                                item.get("query", "")
                            )

                        if query_text and query_text.strip():
                            queries.append({
                                "query": query_text,
                                "expected_chunk_ids": item.get(
                                    "expected_chunk_ids",
                                    []
                                ),
                                "relevance_scores": item.get(
                                    "relevance_scores",
                                    {}
                                )
                            })

                    break  # Process first available split

            # Save documents
            if documents:
                docs_file = dataset_folder / "documents.json"
                with open(docs_file, 'w', encoding='utf-8') as f:
                    json.dump(documents, f, indent=2, ensure_ascii=False)
                logger.info(
                    "✓ Saved %s documents to %s",
                    len(documents),
                    docs_file
                )

            # Save queries
            if queries:
                queries_file = dataset_folder / "queries.json"
                with open(queries_file, 'w', encoding='utf-8') as f:
                    json.dump(queries, f, indent=2, ensure_ascii=False)
                logger.info(
                    "✓ Saved %s queries to %s",
                    len(queries),
                    queries_file
                )

            if not documents and not queries:
                logger.warning(
                    "⚠ No documents or queries extracted from %s",
                    dataset_info['name']
                )
                dataset_keys = (
                    list(dataset.keys())
                    if hasattr(dataset, 'keys')
                    else 'N/A'
                )
                logger.info("Dataset structure: %s", dataset_keys)

                # Try to inspect actual structure
                for split_name in ["train", "test", "validation", "default"]:
                    if (hasattr(dataset, split_name) and
                            dataset[split_name] and
                            len(dataset[split_name]) > 0):
                        sample = dataset[split_name][0]
                        logger.info("Sample from %s split:", split_name)
                        sample_keys = (
                            list(sample.keys())
                            if isinstance(sample, dict)
                            else 'N/A'
                        )
                        logger.info("  Keys: %s", sample_keys)
                        if isinstance(sample, dict):
                            for key, value in list(sample.items())[:5]:
                                value_preview = (
                                    str(value)[:100]
                                    if value
                                    else "None"
                                )
                                logger.info("  %s: %s...", key, value_preview)
                        break

        except Exception as e:
            logger.error(
                "✗ Failed to download %s: %s",
                dataset_info['name'],
                e,
                exc_info=True
            )
            continue

    logger.info("\n%s", "=" * 60)
    logger.info("Dataset download complete!")
    logger.info("%s", "=" * 60)


if __name__ == "__main__":
    download_datasets()
