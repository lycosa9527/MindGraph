"""Pure aggregations for school feature-usage cards.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Sequence

from services.admin.school_feature_usage_catalog import (
    CAPACITY_AMPLE,
    CAPACITY_IDLE,
    CAPACITY_NORMAL,
    CAPACITY_TENSE,
    CONCENTRATION_SHARE_MIN,
    FEATURE_USAGE_MODULE_KEYS,
    PASS_RATE_AMPLE_MIN,
    PASS_RATE_TENSE_MAX,
    SLOW_DURATION_FLOOR_BY_MODULE,
    SLOW_DURATION_FLOOR_SECONDS,
    TOP_RANK_LIMIT,
    resolve_feature_module,
    resolve_token_module,
)
from services.admin.school_feature_usage_types import (
    BottleneckSlots,
    CapacityKey,
    ConclusionSlots,
    FeatureUsageJudgement,
    ModuleUsageRow,
    RankedModule,
    TokenProcessBucket,
    UsageBucket,
)
from services.admin.school_user_activity_types import SeriesPoint

_MONTHS = 12


def _round_one(value: float) -> float:
    return round(value, 1)


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _percentile(values: Sequence[int], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = (len(ordered) - 1) * ratio
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    fraction = index - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def _capacity(
    uses: int,
    pass_rate: float,
    median_uses: float,
    token_calls: int,
) -> CapacityKey:
    if uses == 0 and token_calls == 0:
        return CAPACITY_IDLE
    if uses == 0:
        return CAPACITY_NORMAL
    if uses >= median_uses and pass_rate < PASS_RATE_TENSE_MAX:
        return CAPACITY_TENSE
    if pass_rate >= PASS_RATE_AMPLE_MIN:
        return CAPACITY_AMPLE
    return CAPACITY_NORMAL


def _rollup_token_buckets(
    token_buckets: Sequence[TokenProcessBucket],
) -> dict[str, tuple[int, int, float, int]]:
    """Sum token_usage slices by catalog module. Unknown request types are dropped."""
    rolled: dict[str, list[float]] = {key: [0.0, 0.0, 0.0, 0.0] for key in FEATURE_USAGE_MODULE_KEYS}
    for bucket in token_buckets:
        module = resolve_token_module(bucket["request_type"], bucket["endpoint_path"])
        if module is None:
            continue
        rolled[module][0] += max(int(bucket["calls"]), 0)
        rolled[module][1] += max(int(bucket["failures"]), 0)
        rolled[module][2] += max(float(bucket["duration_sum"]), 0.0)
        rolled[module][3] += max(int(bucket["duration_count"]), 0)
    return {key: (int(vals[0]), int(vals[1]), vals[2], int(vals[3])) for key, vals in rolled.items()}


def _process_rates(
    use_count: int,
    done: int,
    token_calls: int,
    token_failures: int,
    duration_sum: float,
    duration_count: int,
) -> tuple[float, float | None, float | None]:
    """Usage pass rate stays on events; fail rate and duration come from token_usage."""
    pass_rate = _round_one((done / use_count) * 100) if use_count else 0.0
    if token_calls > 0:
        failures = min(token_failures, token_calls)
        fail_rate = _round_one((failures / token_calls) * 100)
    else:
        fail_rate = None
    duration = _round_one(duration_sum / duration_count) if duration_count else None
    return pass_rate, fail_rate, duration


def build_module_rows(
    buckets: Sequence[UsageBucket],
    year: int,
    token_buckets: Sequence[TokenProcessBucket] | None = None,
) -> list[ModuleUsageRow]:
    """Roll usage and token buckets into one row per catalog module."""
    visits: dict[str, set[int]] = {key: set() for key in FEATURE_USAGE_MODULE_KEYS}
    uses: dict[str, int] = {key: 0 for key in FEATURE_USAGE_MODULE_KEYS}
    completed: dict[str, int] = {key: 0 for key in FEATURE_USAGE_MODULE_KEYS}
    monthly: dict[str, dict[str, int]] = {
        key: {f"{year:04d}-{month:02d}": 0 for month in range(1, _MONTHS + 1)} for key in FEATURE_USAGE_MODULE_KEYS
    }
    token_by_module = _rollup_token_buckets(token_buckets or [])

    for bucket in buckets:
        module = resolve_feature_module(bucket["action"], bucket["title"], bucket["source"])
        if module is None:
            continue
        count = max(int(bucket["count"]), 0)
        visits[module].add(int(bucket["user_id"]))
        uses[module] += count
        if bucket["success"]:
            completed[module] += count
        month_key = bucket["month"]
        if month_key in monthly[module]:
            monthly[module][month_key] += count

    nonzero = [uses[key] for key in FEATURE_USAGE_MODULE_KEYS if uses[key] > 0]
    median_uses = _median(nonzero)
    rows: list[ModuleUsageRow] = []
    for key in FEATURE_USAGE_MODULE_KEYS:
        visit_count = len(visits[key])
        use_count = uses[key]
        done = completed[key]
        ops = _round_one(use_count / visit_count) if visit_count else 0.0
        token_calls, token_failures, duration_sum, duration_count = token_by_module[key]
        rate, fail_rate, duration = _process_rates(
            use_count,
            done,
            token_calls,
            token_failures,
            duration_sum,
            duration_count,
        )
        series: list[SeriesPoint] = [
            {"date": f"{year:04d}-{month:02d}", "value": monthly[key][f"{year:04d}-{month:02d}"]}
            for month in range(1, _MONTHS + 1)
        ]
        rows.append(
            {
                "key": key,
                "visits": visit_count,
                "uses": use_count,
                "ops_per_visitor": ops,
                "completed": done,
                "pass_rate": rate,
                "fail_rate": fail_rate,
                "avg_duration_seconds": duration,
                "capacity": _capacity(use_count, rate, median_uses, token_calls),
                "monthly_uses": series,
            }
        )
    rows.sort(key=lambda row: (row["uses"] == 0, -row["uses"], row["key"]))
    return rows


def _usage_rate(visits: int, enrolled: int) -> float | None:
    if enrolled <= 0:
        return None
    return _round_one((visits / enrolled) * 100)


def build_judgement(modules: Sequence[ModuleUsageRow], enrolled: int) -> FeatureUsageJudgement:
    """Build 研判 lists and template slots from module rows."""
    if enrolled <= 0:
        ranked = sorted(modules, key=lambda row: (-row["visits"], -row["uses"], row["key"]))
    else:
        ranked = sorted(
            modules,
            key=lambda row: (
                -(row["visits"] / enrolled),
                -row["visits"],
                row["key"],
            ),
        )
    visited = [row for row in ranked if row["visits"] > 0]
    top5: list[RankedModule] = [
        {
            "key": row["key"],
            "visits": row["visits"],
            "uses": row["uses"],
            "usage_rate": _usage_rate(row["visits"], enrolled),
        }
        for row in visited[:TOP_RANK_LIMIT]
    ]

    nonzero = [row for row in modules if row["uses"] > 0]
    high: list[str] = []
    low: list[str] = []
    if len(nonzero) >= 2:
        median_uses = _median([row["uses"] for row in nonzero])
        p25 = _percentile([row["uses"] for row in nonzero], 0.25)
        high = [row["key"] for row in nonzero if row["uses"] > median_uses]
        low = [row["key"] for row in nonzero if row["uses"] < p25]
    idle = [row["key"] for row in modules if row["uses"] == 0]

    tense = [row["key"] for row in modules if row["capacity"] == CAPACITY_TENSE]
    nonzero_rates = [row["pass_rate"] for row in nonzero]
    uniformly_high = bool(nonzero_rates) and min(nonzero_rates) >= PASS_RATE_TENSE_MAX
    lowest_pass_keys: list[str] = []
    if nonzero and not uniformly_high:
        min_rate = min(row["pass_rate"] for row in nonzero)
        lowest_pass_keys = [row["key"] for row in nonzero if row["pass_rate"] == min_rate]
    timed = [row for row in modules if row["avg_duration_seconds"] is not None]
    slow_keys: list[str] = []
    if len(timed) >= 2:
        median_duration = _median([row["avg_duration_seconds"] or 0.0 for row in timed])
        slow_keys = [
            row["key"]
            for row in timed
            if (row["avg_duration_seconds"] or 0.0) > median_duration
            and (row["avg_duration_seconds"] or 0.0)
            >= SLOW_DURATION_FLOOR_BY_MODULE.get(row["key"], SLOW_DURATION_FLOOR_SECONDS)
        ]
    no_bottleneck = not tense and (not nonzero or uniformly_high) and not slow_keys

    total_uses = sum(row["uses"] for row in modules)
    top_uses = max((row["uses"] for row in modules), default=0)
    concentrated = bool(total_uses) and (top_uses / total_uses) >= CONCENTRATION_SHARE_MIN

    bottleneck: BottleneckSlots = {
        "lowest_pass_keys": lowest_pass_keys,
        "tense_keys": tense,
        "slow_keys": slow_keys,
        "uniformly_high": uniformly_high,
        "no_bottleneck": no_bottleneck,
    }
    conclusion: ConclusionSlots = {
        "top_keys": [item["key"] for item in top5 if item["uses"] > 0 or item["visits"] > 0],
        "idle_keys": idle,
        "concentrated": concentrated,
    }
    return {
        "top5": top5,
        "high": high,
        "low": low,
        "idle": idle,
        "bottleneck_slots": bottleneck,
        "conclusion_slots": conclusion,
    }
