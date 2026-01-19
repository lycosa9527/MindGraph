"""
Test Queries for RAG Chunk Testing
===================================

Provides example test queries for different benchmark datasets.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any


# FinanceBench Example Queries (Financial Domain)
FINANCEBENCH_QUERIES = [
    "What is the current market capitalization of Apple Inc?",
    "How does inflation affect stock market performance?",
    "What are the key differences between stocks and bonds?",
    "Explain the concept of compound interest in investment.",
    "What factors influence foreign exchange rates?",
    "How do central banks control monetary policy?",
    "What is the difference between a bull market and a bear market?",
    "How does diversification reduce investment risk?",
    "What are the main types of financial derivatives?",
    "Explain the role of credit rating agencies in financial markets.",
    "How do interest rates affect bond prices?",
    "What is the efficient market hypothesis?",
    "How does leverage work in trading?",
    "What are the key components of a balance sheet?",
    "Explain the concept of market liquidity.",
    "How do dividends affect stock valuation?",
    "What is the difference between active and passive investing?",
    "How do economic indicators predict market trends?",
    "What role do hedge funds play in financial markets?",
    "Explain the concept of portfolio optimization."
]

# KG-RAG / BiomixQA Example Queries (Biomedical Domain)
BIOMEDICAL_QUERIES = [
    "What is the mechanism of action of aspirin?",
    "How does insulin regulate blood glucose levels?",
    "What are the symptoms of diabetes mellitus?",
    "Explain the process of DNA replication.",
    "How do antibiotics work against bacterial infections?",
    "What is the role of mitochondria in cellular respiration?",
    "How does the immune system respond to viral infections?",
    "What are the causes of hypertension?",
    "Explain the process of protein synthesis.",
    "How do vaccines provide immunity?",
    "What is the difference between benign and malignant tumors?",
    "How does the nervous system transmit signals?",
    "What are the risk factors for cardiovascular disease?",
    "Explain the process of photosynthesis.",
    "How do hormones regulate body functions?",
    "What is the role of enzymes in metabolism?",
    "How does the respiratory system exchange gases?",
    "What are the stages of cell division?",
    "How do neurotransmitters affect brain function?",
    "What is the mechanism of gene expression?"
]

# PubMedQA Example Queries (Medical Research Domain)
MEDICAL_RESEARCH_QUERIES = [
    "What are the latest treatments for Alzheimer's disease?",
    "How effective is chemotherapy for cancer treatment?",
    "What is the relationship between exercise and cardiovascular health?",
    "What are the side effects of statin medications?",
    "How does sleep deprivation affect cognitive function?",
    "What is the evidence for the effectiveness of COVID-19 vaccines?",
    "How do genetic mutations cause disease?",
    "What are the risk factors for developing osteoporosis?",
    "How does stress impact mental health?",
    "What is the role of inflammation in chronic diseases?",
    "How do antidepressants work in the brain?",
    "What are the benefits and risks of hormone replacement therapy?",
    "How does diet affect metabolic syndrome?",
    "What is the mechanism of action of ACE inhibitors?",
    "How do probiotics affect gut health?",
    "What are the long-term effects of smoking on health?",
    "How does aging affect the immune system?",
    "What is the relationship between obesity and diabetes?",
    "How do environmental factors influence disease development?",
    "What are the current guidelines for hypertension management?"
]

# FRAMES Example Queries (General Knowledge)
GENERAL_QUERIES = [
    "What are the main causes of climate change?",
    "How does machine learning differ from traditional programming?",
    "What is the history of the internet?",
    "Explain the theory of evolution.",
    "How do renewable energy sources work?",
    "What are the principles of quantum mechanics?",
    "How does the human brain process language?",
    "What is the structure of the solar system?",
    "How do computers process information?",
    "What are the key events of World War II?",
    "How does photosynthesis convert light into energy?",
    "What is the role of government in economic policy?",
    "How do social media algorithms work?",
    "What are the fundamental forces of nature?",
    "How does the water cycle work?",
    "What is the impact of artificial intelligence on society?",
    "How do earthquakes occur?",
    "What are the principles of democracy?",
    "How does the human digestive system work?",
    "What is the significance of the Renaissance period?"
]


def get_test_queries(dataset_name: str = "mixed", count: int = 20) -> List[str]:
    """
    Get test queries for evaluation.

    Args:
        dataset_name: Dataset name ('FinanceBench', 'KG-RAG', 'PubMedQA', 'FRAMES', 'mixed')
        count: Number of queries to return (default: 20)

    Returns:
        List of test query strings
    """
    if dataset_name == "FinanceBench":
        queries = FINANCEBENCH_QUERIES
    elif dataset_name == "KG-RAG" or dataset_name.startswith("KG-RAG"):
        queries = BIOMEDICAL_QUERIES
    elif dataset_name == "PubMedQA":
        queries = MEDICAL_RESEARCH_QUERIES
    elif dataset_name == "FRAMES":
        queries = GENERAL_QUERIES
    else:
        # Mixed: combine queries from all domains
        queries = (
            FINANCEBENCH_QUERIES[:5] +
            BIOMEDICAL_QUERIES[:5] +
            MEDICAL_RESEARCH_QUERIES[:5] +
            GENERAL_QUERIES[:5]
        )

    return queries[:count]


def get_test_queries_with_metadata(
    dataset_name: str = "mixed",
    count: int = 20
) -> List[Dict[str, Any]]:
    """
    Get test queries with metadata format for benchmark testing.

    Args:
        dataset_name: Dataset name
        count: Number of queries to return

    Returns:
        List of query dictionaries with format:
        [{"query": str, "expected_chunk_ids": [], "relevance_scores": {}, "answer": ""}]
    """
    queries = get_test_queries(dataset_name, count)
    return [
        {
            "query": q,
            "expected_chunk_ids": [],
            "relevance_scores": {},
            "answer": ""
        }
        for q in queries
    ]
