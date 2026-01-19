"""
Script to organize RAG test datasets into rag-test folder structure.

Author: lycosa9527
Made by: MindSpring Team
"""
import json
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
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


def organize_datasets():
    """Organize datasets into rag-test folder structure."""
    project_root = _get_project_root()

    # Create rag-test folder structure
    rag_test_dir = project_root / "rag-test"
    financebench_dir = rag_test_dir / "financebench"
    kg_rag_dir = rag_test_dir / "kg-rag"

    financebench_dir.mkdir(parents=True, exist_ok=True)
    kg_rag_dir.mkdir(parents=True, exist_ok=True)

    # Move FinanceBench
    financebench_file = project_root / "financebench_merged.jsonl"
    if financebench_file.exists():
        logger.info("Found financebench_merged.jsonl")

        # Check file size and line count
        line_count = sum(1 for _ in open(financebench_file, 'r', encoding='utf-8'))
        file_size = financebench_file.stat().st_size / (1024 * 1024)  # MB

        logger.info("FinanceBench: %s lines, %.2f MB", line_count, file_size)

        # Read first line to check format
        with open(financebench_file, 'r', encoding='utf-8') as f:
            first_line = json.loads(f.readline())
            sample_keys = list(first_line.keys())[:10]
            logger.info("FinanceBench format check - keys: %s", sample_keys)

        # Move to rag-test/financebench/
        dest_file = financebench_dir / "documents.jsonl"
        shutil.move(str(financebench_file), str(dest_file))
        logger.info("Moved FinanceBench to %s", dest_file)

        # Extract queries from FinanceBench format
        queries = []
        with open(dest_file, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                query_data = {
                    "query": item.get("question", ""),
                    "expected_chunk_ids": [],  # Will need to be determined from evidence
                    "relevance_scores": {}
                }
                if query_data["query"]:
                    queries.append(query_data)

        # Save queries
        queries_file = financebench_dir / "queries.json"
        with open(queries_file, 'w', encoding='utf-8') as f:
            json.dump(queries, f, indent=2, ensure_ascii=False)
        logger.info("Extracted %s queries from FinanceBench", len(queries))

    else:
        logger.warning("financebench_merged.jsonl not found in root")

    # Check KG-RAG-datasets-main folder
    kg_rag_source = project_root / "KG-RAG-datasets-main"
    if kg_rag_source.exists():
        logger.info("Found KG-RAG-datasets-main folder")
        logger.info("Note: This appears to be Docugami's KG-RAG datasets, not BiomixQA")
        logger.info("BiomixQA should be downloaded from Hugging Face: kg-rag/BiomixQA")

        # Check if there's any usable data
        readme_file = kg_rag_source / "README.md"
        if readme_file.exists():
            logger.info("KG-RAG-datasets-main contains multiple sub-datasets:")
            logger.info("  - SEC 10-Q")
            logger.info("  - NTSB Aviation Reports")
            logger.info("  - NIH Clinical Trial Protocols")
            logger.info("  - US Federal Agency Reports")
            logger.info("These are different from BiomixQA dataset")

    logger.info("\nDataset organization complete!")
    logger.info("Next steps:")
    logger.info("1. FinanceBench is ready in rag-test/financebench/")
    logger.info("2. For KG-RAG (BiomixQA), download from Hugging Face:")
    logger.info("   datasets.load_dataset('kg-rag/BiomixQA', 'mcq')")
    logger.info("   datasets.load_dataset('kg-rag/BiomixQA', 'true_false')")


if __name__ == "__main__":
    organize_datasets()
