"""Reciprocal rank fusion for outline rank and vector rank.

k=60 is the Elasticsearch, OpenSearch, and Azure AI Search default
(Cormack, Clarke, and Buettcher, SIGIR 2009). The two lists do not share
a score scale: outline position is a reading order, and the mindgraph
index returns Euclidean distance.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Dict, List

RRF_K = 60


def reciprocal_rank_fusion(rankings: List[List[str]], k: int = RRF_K) -> List[str]:
    """Fuse ranked key lists. Higher fused score comes first."""
    scores: Dict[str, float] = {}
    best_rank: Dict[str, int] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + (1.0 / (k + rank))
            previous = best_rank.get(key)
            if previous is None or rank < previous:
                best_rank[key] = rank
    return sorted(scores, key=lambda item: (-scores[item], best_rank[item], item))
