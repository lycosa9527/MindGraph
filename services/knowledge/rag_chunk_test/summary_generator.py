"""
Summary Generator for RAG Chunk Test Service
==============================================

Module for generating summary reports from chunking comparison results.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any


class SummaryGenerator:
    """Generator for summary reports from comparison results."""

    def generate_summary(
        self,
        chunk_stats: Dict[str, Any],
        retrieval_comparison: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate summary of comparison results.

        Args:
            chunk_stats: Chunk statistics for each mode
            retrieval_comparison: Retrieval comparison results

        Returns:
            Summary dictionary with winners and recommendations
        """
        summary = {
            "chunking_winner": "tie",
            "retrieval_winner": "tie",
            "recommendations": []
        }

        # Get modes from chunk_stats
        modes = [k for k in chunk_stats.keys() if k != "comparison"]
        if len(modes) < 2:
            return summary

        # Determine chunking winner
        mode_a_count = chunk_stats.get(modes[0], {}).get("count", 0)
        mode_b_count = chunk_stats.get(modes[1], {}).get("count", 0)
        if mode_b_count > mode_a_count:
            summary["chunking_winner"] = modes[1]
            summary["recommendations"].append(
                f"{modes[1]} produces more chunks, potentially better granularity"
            )
        elif mode_a_count > mode_b_count:
            summary["chunking_winner"] = modes[0]
            summary["recommendations"].append(
                f"{modes[0]} produces fewer chunks, potentially more efficient"
            )

        # Determine retrieval winner
        if "average" in retrieval_comparison:
            avg = retrieval_comparison["average"]
            if "comparison" in avg and "winner" in avg.get("comparison", {}):
                summary["retrieval_winner"] = avg["comparison"]["winner"]
            elif modes[0] in avg and modes[1] in avg:
                # Compare average metrics
                score_a = (
                    avg[modes[0]].get("precision", 0) * 0.3 +
                    avg[modes[0]].get("recall", 0) * 0.3 +
                    avg[modes[0]].get("mrr", 0) * 0.2 +
                    avg[modes[0]].get("ndcg", 0) * 0.2
                )
                score_b = (
                    avg[modes[1]].get("precision", 0) * 0.3 +
                    avg[modes[1]].get("recall", 0) * 0.3 +
                    avg[modes[1]].get("mrr", 0) * 0.2 +
                    avg[modes[1]].get("ndcg", 0) * 0.2
                )
                if score_b > score_a:
                    summary["retrieval_winner"] = modes[1]
                elif score_a > score_b:
                    summary["retrieval_winner"] = modes[0]

        # Add recommendations
        if summary["retrieval_winner"] != "tie":
            summary["recommendations"].append(
                f"{summary['retrieval_winner']} shows better retrieval performance"
            )

        return summary
