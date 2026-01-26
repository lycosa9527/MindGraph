"""
Chunk test utility endpoints.

Handles benchmark listing, dataset updates, and test queries.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from config.settings import config
from models.domain.auth import User
from services.knowledge.rag_chunk_test.test_queries import get_test_queries
from utils.auth import get_current_user

try:
    from services.knowledge.rag_chunk_test.utils.download_datasets import download_datasets
except ImportError:
    download_datasets = None

logger = logging.getLogger(__name__)

router = APIRouter()


def check_feature_enabled():
    """Check if RAG chunk test feature is enabled."""
    if not config.FEATURE_RAG_CHUNK_TEST:
        raise HTTPException(
            status_code=404,
            detail="RAG chunk test feature is not enabled"
        )


@router.get("/chunk-test/benchmarks")
async def list_available_benchmarks():
    """
    List available benchmark datasets.

    No authentication required.
    """
    check_feature_enabled()
    return {
        "benchmarks": [
            {
                "name": "FinanceBench",
                "description": "Financial document benchmark dataset",
                "source": "PatronusAI/financebench (Hugging Face)",
                "version": "v1.0",
                "updated_at": "2024-01-15T00:00:00Z"
            },
            {
                "name": "KG-RAG",
                "description": "Knowledge Graph RAG benchmark (BiomixQA)",
                "source": "kg-rag/BiomixQA (Hugging Face)",
                "version": "v1.2",
                "updated_at": "2024-02-20T00:00:00Z"
            },
            {
                "name": "FRAMES",
                "description": "FRAMES benchmark dataset",
                "source": "google/frames-benchmark (Hugging Face)",
                "version": "v2.1",
                "updated_at": "2024-03-10T00:00:00Z"
            },
            {
                "name": "PubMedQA",
                "description": "PubMed question answering benchmark",
                "source": "bigbio/pubmed_qa (Hugging Face)",
                "version": "v1.5",
                "updated_at": "2024-01-30T00:00:00Z"
            }
        ]
    }


@router.post("/chunk-test/update-datasets")
async def update_benchmark_datasets(
    _current_user: User = Depends(get_current_user)
):
    """
    Update/download benchmark datasets from Hugging Face.

    Requires authentication.
    """
    check_feature_enabled()
    if download_datasets is None:
        raise HTTPException(
            status_code=500,
            detail="Dataset update module not available"
        )

    try:
        download_datasets()

        return {
            "success": True,
            "message": "Benchmark datasets update initiated successfully"
        }
    except Exception as e:
        logger.error(
            "[ChunkTestUtils] Failed to update datasets: %s",
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update datasets"
        ) from e


@router.get("/chunk-test/test-queries")
async def get_test_queries_endpoint(
    dataset_name: Optional[str] = None,
    count: int = 20
):
    """
    Get example test queries for chunk testing.

    Args:
        dataset_name: Dataset name ('FinanceBench', 'KG-RAG', 'PubMedQA', 'FRAMES', 'mixed')
        count: Number of queries to return (default: 20, max: 20)

    Returns:
        List of test queries
    """
    check_feature_enabled()
    queries = get_test_queries(dataset_name or "mixed", min(count, 20))
    return {
        "queries": queries,
        "count": len(queries),
        "dataset": dataset_name or "mixed",
        "note": "These are example queries. Metrics will be averaged across all queries."
    }
