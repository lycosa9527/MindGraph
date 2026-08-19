"""Timing sink for Kitty five-map live runs (LLM vs action dispatch)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class CaseTiming:
    """One live case: total loop, LLM chat_raw, and dispatch_loop_tool."""

    slug: str
    action: str
    total_ms: float
    llm_ms: float
    dispatch_ms: float
    dispatch_n: int
    tool: str
    reason: str


@dataclass
class TimingSink:
    """Collect per-case timings and render a summary table."""

    cases: List[CaseTiming] = field(default_factory=list)

    def add(self, row: CaseTiming) -> None:
        """Append one recorded case."""
        self.cases.append(row)

    def by_action(self) -> Dict[str, List[CaseTiming]]:
        """Group recorded cases by library action name."""
        grouped: Dict[str, List[CaseTiming]] = {}
        for row in self.cases:
            grouped.setdefault(row.action, []).append(row)
        return grouped


def _ms_stats(values: List[float]) -> Tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ordered = sorted(values)
    avg = sum(values) / len(values)
    mid = ordered[len(ordered) // 2]
    return avg, mid, ordered[-1]


def format_summary(sink: TimingSink) -> str:
    """Human-readable LLM vs action-dispatch table."""
    if not sink.cases:
        return "no timings recorded"
    lines = [
        "",
        "Kitty five-map live timings",
        "dispatch = after the model picked a tool (identity + add/delete/auto-complete trigger).",
        "Canvas verify / auto-complete generation are mocked in this suite.",
        "",
        f"{'case':<42} {'total':>8} {'llm':>8} {'dispatch':>10} {'n':>3}",
    ]
    for row in sink.cases:
        case = f"{row.slug}/{row.action}"
        lines.append(
            f"{case:<42} {row.total_ms / 1000:7.2f}s {row.llm_ms / 1000:7.2f}s "
            f"{row.dispatch_ms:9.1f}ms {row.dispatch_n:3d}"
        )
    lines.extend(
        [
            "",
            "By action (dispatch only — not LLM)",
            f"{'action':<24} {'n':>3} {'avg':>10} {'p50':>10} {'max':>10}",
        ]
    )
    for action, rows in sink.by_action().items():
        avg, p50, max_ms = _ms_stats([row.dispatch_ms for row in rows])
        lines.append(f"{action:<24} {len(rows):3d} {avg:9.1f}ms {p50:9.1f}ms {max_ms:9.1f}ms")
    llm_vals = [row.llm_ms for row in sink.cases]
    disp_vals = [row.dispatch_ms for row in sink.cases]
    llm_avg, _, llm_max = _ms_stats(llm_vals)
    disp_avg, _, disp_max = _ms_stats(disp_vals)
    lines.extend(
        [
            "",
            f"LLM chat_raw  avg={llm_avg / 1000:.2f}s  max={llm_max / 1000:.2f}s  n={len(llm_vals)}",
            f"dispatch      avg={disp_avg:.1f}ms  max={disp_max:.1f}ms  n={len(disp_vals)}",
            "",
        ]
    )
    return "\n".join(lines)


def write_timing_json(sink: TimingSink, path: Path) -> None:
    """Write the same timings as JSON for later inspection."""
    payload: Dict[str, Any] = {
        "note": (
            "dispatch_ms is identity resolve + Bus/WS/clarify after the model "
            "picked a tool. Canvas apply and auto-complete generation are mocked."
        ),
        "cases": [
            {
                "slug": row.slug,
                "action": row.action,
                "total_ms": round(row.total_ms, 2),
                "llm_ms": round(row.llm_ms, 2),
                "dispatch_ms": round(row.dispatch_ms, 2),
                "dispatch_n": row.dispatch_n,
                "tool": row.tool,
                "reason": row.reason,
            }
            for row in sink.cases
        ],
        "by_action_dispatch_ms": {},
    }
    by_action: Dict[str, Any] = {}
    for action, rows in sink.by_action().items():
        avg, p50, max_ms = _ms_stats([row.dispatch_ms for row in rows])
        by_action[action] = {
            "n": len(rows),
            "avg_ms": round(avg, 2),
            "p50_ms": round(p50, 2),
            "max_ms": round(max_ms, 2),
        }
    payload["by_action_dispatch_ms"] = by_action
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
