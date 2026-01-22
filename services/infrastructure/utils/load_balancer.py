"""
LLM Load Balancer
=================

Distributes DeepSeek requests between Dashscope and Volcengine providers
to maximize throughput and avoid rate limiting bottlenecks.

Key Design:
- ONLY DeepSeek is load-balanced between Dashscope and Volcengine
- Qwen always uses Dashscope (cost optimization)
- Kimi/Doubao always use Volcengine (higher RPM limits)
- Users see LOGICAL names (deepseek, qwen, kimi, doubao)
- Backend maps to PHYSICAL models transparently

@author MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
"""

from typing import Dict, Optional, Any, TYPE_CHECKING
import json
import logging
import random
import time

from services.infrastructure.rate_limiting.rate_limiter import LoadBalancerRateLimiter
from services.redis.redis_client import is_redis_available, RedisOps

if TYPE_CHECKING:
    from services.infrastructure.rate_limiting.rate_limiter import DashscopeRateLimiter

logger = logging.getLogger(__name__)

# Redis key prefixes
REDIS_KEY_PREFIX = "load_balancer:"
ROUND_ROBIN_KEY = f"{REDIS_KEY_PREFIX}deepseek:counter"
METRICS_KEY_PREFIX = f"{REDIS_KEY_PREFIX}provider:"


class LLMLoadBalancer:
    """
    Load balances DeepSeek requests between Dashscope and Volcengine.
    All other models use fixed providers (Qwen→Dashscope, Kimi/Doubao→Volcengine).

    KEY PRINCIPLE: Users see logical model names (deepseek, qwen, kimi, doubao).
    The load balancer maps these to physical models transparently.
    """

    # Provider constants
    PROVIDER_DASHSCOPE = 'dashscope'
    PROVIDER_VOLCENGINE = 'volcengine'

    # Fixed model mappings (for non-load-balanced models)
    FIXED_MODEL_MAP = {
        # Logical models (frontend buttons)
        'qwen': 'qwen',  # → Dashscope qwen-plus-latest (15,000 RPM, 1,200,000 TPM)
        # → Volcengine Kimi via endpoint (ALWAYS - 5,000 RPM, 500,000 TPM vs Dashscope's 60 RPM, 100,000 TPM)
        'kimi': 'ark-kimi',
        'doubao': 'ark-doubao',  # → Volcengine Doubao via endpoint (higher RPM than Dashscope)
        # DeepSeek load balancing:
        # - Dashscope route (deepseek-v3.1/v3.2): 15,000 RPM, 1,200,000-1,500,000 TPM
        # - Volcengine route (ark-deepseek v3.2): 15,000 RPM, 1,500,000 TPM
        # Internal aliases
        'qwen-turbo': 'qwen-turbo',  # → Dashscope qwen-turbo
        'qwen-plus': 'qwen-plus',    # → Dashscope qwen-plus
        'qwen-plus-latest': 'qwen-plus',  # → Dashscope qwen-plus-latest
        # Unaffected
        'hunyuan': 'hunyuan',  # → Tencent hunyuan
        'omni': 'omni',        # → Voice agent
    }

    def __init__(
        self,
        strategy: str = 'round_robin',
        weights: Optional[Dict[str, int]] = None,
        enabled: bool = True,
        dashscope_rate_limiter: Optional['DashscopeRateLimiter'] = None,
        load_balancer_rate_limiter: Optional[LoadBalancerRateLimiter] = None,
        rate_limit_aware: bool = True
    ):
        """
        Initialize load balancer.

        Args:
            strategy: 'weighted', 'random', or 'round_robin' (default: 'round_robin')
            weights: Provider weights, e.g., {'dashscope': 50, 'volcengine': 50}
            enabled: Whether load balancing is enabled
            dashscope_rate_limiter: Shared Dashscope rate limiter (for Dashscope route checks)
            load_balancer_rate_limiter: LoadBalancerRateLimiter instance (for Volcengine route checks)
            rate_limit_aware: Whether to consider rate limits when selecting provider (default: True)
        """
        self.strategy = strategy
        # Normalize weights to dashscope/volcengine format
        self.weights = self._normalize_weights(weights or {'dashscope': 50, 'volcengine': 50})
        self.enabled = enabled
        self._counter = 0  # Local fallback for round_robin if Redis unavailable
        self._use_redis = is_redis_available()
        self.dashscope_rate_limiter = dashscope_rate_limiter  # Shared Dashscope limiter
        self.load_balancer_rate_limiter = load_balancer_rate_limiter  # Volcengine limiter only
        self.rate_limit_aware = rate_limit_aware and (
            dashscope_rate_limiter is not None or
            load_balancer_rate_limiter is not None
        )

        # Validate strategy
        valid_strategies = ['weighted', 'random', 'round_robin']
        if strategy not in valid_strategies:
            logger.warning(
                "[LoadBalancer] Invalid strategy '%s', "
                "must be one of %s. Using 'round_robin'.",
                strategy, valid_strategies
            )
            self.strategy = 'round_robin'

        logger.info(
            "[LoadBalancer] Initialized: strategy=%s, "
            "weights=%s, enabled=%s, redis=%s",
            self.strategy, self.weights, enabled, self._use_redis
        )

    def _normalize_weights(self, weights: Dict[str, int]) -> Dict[str, int]:
        """
        Normalize weights to dashscope/volcengine format.
        Validates and normalizes weights to sum to 100.
        """
        normalized = {
            'dashscope': weights.get('dashscope', 50),
            'volcengine': weights.get('volcengine', 50)
        }

        # Validate weights are in valid range (0-100)
        normalized['dashscope'] = max(0, min(100, normalized['dashscope']))
        normalized['volcengine'] = max(0, min(100, normalized['volcengine']))

        # Normalize weights to sum to 100 for proper probability distribution
        total = normalized['dashscope'] + normalized['volcengine']
        if total > 0:
            # Preserve integer values while normalizing
            dashscope_weight = normalized['dashscope']
            normalized['dashscope'] = int(round(dashscope_weight * 100 / total))
            normalized['volcengine'] = 100 - normalized['dashscope']  # Ensure they sum to exactly 100
        else:
            # If both are 0, default to 50/50
            logger.warning("Load balancing weights sum to 0, using default 50/50")
            normalized = {'dashscope': 50, 'volcengine': 50}

        return normalized

    def _select_deepseek_provider(self) -> str:
        """
        Select provider for DeepSeek based on strategy.

        If rate_limit_aware is enabled, prefers providers with available capacity.
        Falls back to configured strategy if both providers are at capacity.

        NOTE: Rate limit-aware selection uses best-effort checks with potentially
        stale stats. The actual rate limiter acquire() may still block if conditions
        change between this check and the actual acquire() call. This is acceptable
        as the check is meant to optimize routing, not guarantee availability.

        Returns:
            'dashscope' or 'volcengine'

        Strategy Details:
            'round_robin' (DEFAULT):
                - Uses Redis INCR for shared counter across all workers
                - Even counter → Dashscope, odd counter → Volcengine
                - Provides true round-robin distribution in multi-worker deployments
                - Falls back to per-worker counter if Redis unavailable
                - Example: Request 1 → Dashscope, Request 2 → Volcengine, Request 3 → Dashscope...

            'weighted':
                - Stateless random selection based on configured weights
                - Each request independently selects provider with probability
                - Perfect for multi-worker (no coordination needed)
                - Example: 30/70 weights → 30% Dashscope, 70% Volcengine (probabilistic)

            'random':
                - Simple 50/50 random selection (ignores weights)
                - Stateless, multi-worker safe
        """
        if not self.enabled:
            return self.PROVIDER_DASHSCOPE  # Default to Dashscope when disabled

        # Rate limit-aware selection: prefer provider with available capacity
        # NOTE: This is a best-effort check using potentially stale stats.
        # The actual acquire() may still block if conditions change between
        # this check and the actual rate limiter acquire() call.
        if self.rate_limit_aware:
            # Check Dashscope availability using shared Dashscope rate limiter
            dashscope_available = True
            if self.dashscope_rate_limiter:
                stats = self.dashscope_rate_limiter.get_stats()
                current_qpm = stats.get('current_qpm', 0)
                active_requests = stats.get('active_requests', 0)
                dashscope_available = (
                    current_qpm < self.dashscope_rate_limiter.qpm_limit and
                    active_requests < self.dashscope_rate_limiter.concurrent_limit
                )

            # Check Volcengine availability using load balancer rate limiter
            volcengine_available = True
            if self.load_balancer_rate_limiter:
                volcengine_available = self.load_balancer_rate_limiter.can_acquire_now(self.PROVIDER_VOLCENGINE)

            # If only one provider has capacity, use it
            if dashscope_available and not volcengine_available:
                logger.debug("[LoadBalancer] Rate limit-aware: Dashscope has capacity, Volcengine at limit")
                return self.PROVIDER_DASHSCOPE
            elif volcengine_available and not dashscope_available:
                logger.debug("[LoadBalancer] Rate limit-aware: Volcengine has capacity, Dashscope at limit")
                return self.PROVIDER_VOLCENGINE
            elif not dashscope_available and not volcengine_available:
                # Both at capacity - fall through to strategy selection (will block on acquire)
                logger.debug("[LoadBalancer] Rate limit-aware: Both providers at capacity, using strategy")
            # If both available, fall through to strategy selection

        # Apply configured strategy
        if self.strategy == 'weighted':
            # Stateless! Each request independently rolls dice
            # Perfect for multi-worker - no coordination needed
            rand = random.randint(1, 100)
            provider = (
                self.PROVIDER_DASHSCOPE
                if rand <= self.weights.get('dashscope', 50)
                else self.PROVIDER_VOLCENGINE
            )
            logger.debug(
                "[LoadBalancer] Weighted selection: rand=%s, provider=%s",
                rand, provider
            )
            return provider

        elif self.strategy == 'random':
            return random.choice([self.PROVIDER_DASHSCOPE, self.PROVIDER_VOLCENGINE])

        elif self.strategy == 'round_robin':
            # Use Redis for shared counter across workers
            # HOW IT WORKS ACROSS WORKERS (example with 5 workers):
            # All workers share the same Redis counter, so number of workers doesn't matter!
            #
            # Worker 1: Request → Redis INCR → counter=1 → odd → Volcengine
            # Worker 2: Request → Redis INCR → counter=2 → even → Dashscope
            # Worker 3: Request → Redis INCR → counter=3 → odd → Volcengine
            # Worker 4: Request → Redis INCR → counter=4 → even → Dashscope
            # Worker 5: Request → Redis INCR → counter=5 → odd → Volcengine
            # Result: Perfect 50/50 distribution regardless of worker count!
            #
            # Redis INCR is atomic, so even if all 5 workers call it simultaneously,
            # they get sequential counter values (1, 2, 3, 4, 5), ensuring even distribution.
            if self._use_redis:
                counter = RedisOps.increment(ROUND_ROBIN_KEY, ttl_seconds=86400)  # 24h TTL
                if counter is not None:
                    # Even counter → Dashscope, odd → Volcengine
                    provider = (
                        self.PROVIDER_DASHSCOPE
                        if counter % 2 == 0
                        else self.PROVIDER_VOLCENGINE
                    )
                    logger.debug(
                        "[LoadBalancer] Round-robin (Redis): counter=%s, provider=%s",
                        counter, provider
                    )
                    return provider
                else:
                    # Redis failed, fall back to local counter
                    logger.warning(
                        "[LoadBalancer] Redis unavailable, using local counter "
                        "for round-robin (uneven distribution in multi-worker)"
                    )

            # Fallback: local counter (per-worker, uneven distribution in multi-worker)
            # Each worker maintains its own counter, so distribution is uneven:
            # Worker 1: Request 1 → Dashscope, Request 2 → Volcengine
            # Worker 2: Request 1 → Dashscope, Request 2 → Volcengine
            # Result: Both workers send first request to Dashscope (not ideal)
            self._counter += 1
            provider = (
                self.PROVIDER_DASHSCOPE
                if self._counter % 2 == 0
                else self.PROVIDER_VOLCENGINE
            )
            logger.debug(
                "[LoadBalancer] Round-robin (local): counter=%s, provider=%s",
                self._counter, provider
            )
            return provider

        return self.PROVIDER_DASHSCOPE  # Default to Dashscope

    def map_model(self, logical_model: str) -> str:
        """
        Map logical model name to physical model.

        For DeepSeek: Selects provider (Dashscope or Volcengine) based on weights.
        For others: Uses fixed mapping (Qwen→Dashscope, Kimi/Doubao→Volcengine).

        IMPORTANT: Kimi ALWAYS routes to Volcengine (ark-kimi) because:
        - Volcengine: 5,000 RPM, 500,000 TPM
        - Dashscope: 60 RPM, 100,000 TPM (83x lower RPM!)

        Args:
            logical_model: Frontend model name (e.g., 'deepseek', 'qwen')

        Returns:
            Physical model alias

        Example:
            map_model('deepseek') → 'deepseek' (Dashscope) or 'ark-deepseek' (Volcengine)
            map_model('qwen') → 'qwen' (Dashscope, always)
            map_model('kimi') → 'ark-kimi' (Volcengine, ALWAYS - never Dashscope)
        """
        # DeepSeek is the only load-balanced model
        if logical_model == 'deepseek':
            provider = self._select_deepseek_provider()
            if provider == self.PROVIDER_VOLCENGINE:
                physical = 'ark-deepseek'
            else:
                physical = 'deepseek'
            logger.debug(
                "[LoadBalancer] map_model: %s → %s (provider=%s)",
                logical_model, physical, provider
            )
            return physical

        # All other models use fixed mapping
        physical = self.FIXED_MODEL_MAP.get(logical_model, logical_model)

        # Safety check: Ensure Kimi always uses Volcengine (5,000 RPM vs Dashscope's 60 RPM)
        if logical_model == 'kimi' and physical != 'ark-kimi':
            logger.warning(
                "[LoadBalancer] Kimi mapped to %s instead of ark-kimi! "
                "Force routing to Volcengine (5,000 RPM vs Dashscope's 60 RPM)",
                physical
            )
            physical = 'ark-kimi'

        logger.debug(
            "[LoadBalancer] map_model: %s → %s (fixed)",
            logical_model, physical
        )
        return physical

    def get_provider_from_model(self, model: str) -> Optional[str]:
        """
        Get provider name from model name (logical or physical).

        Args:
            model: Model name (logical like 'deepseek' or physical like 'ark-deepseek')

        Returns:
            Provider name ('dashscope' or 'volcengine') if DeepSeek, None otherwise

        Example:
            get_provider_from_model('deepseek') → 'dashscope' or 'volcengine'
            get_provider_from_model('ark-deepseek') → 'volcengine'
            get_provider_from_model('qwen') → None
        """
        # Check if it's a physical DeepSeek model
        if model == 'ark-deepseek':
            return self.PROVIDER_VOLCENGINE
        if model == 'deepseek':
            return self.PROVIDER_DASHSCOPE

        # Check if it's a logical DeepSeek model (would need to map first)
        # But we can't know which provider was selected without mapping
        # So return None for logical 'deepseek' - caller should use map_model() first
        return None

    def record_provider_metrics(
        self,
        provider: str,
        success: bool,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        """
        Record performance metrics for a provider in Redis.

        This enables shared metrics across all workers for:
        - Health-aware routing
        - Dynamic weight adjustment
        - Better observability

        Args:
            provider: Provider name ('dashscope' or 'volcengine')
            success: Whether request succeeded
            duration: Request duration in seconds
            error: Optional error message for failed requests
        """
        # Note: error parameter is accepted for API compatibility but not currently stored
        _ = error  # Acknowledge parameter to avoid unused warning
        if not self._use_redis:
            return  # Skip if Redis unavailable

        try:
            metrics_key = f"{METRICS_KEY_PREFIX}{provider}:stats"
            window_key = f"{METRICS_KEY_PREFIX}{provider}:window"

            # Use atomic Redis operations for counters to avoid race conditions
            # Counters: total_requests, successful_requests, failed_requests, total_duration
            # Metadata: min_duration, max_duration, last_updated (stored in JSON, acceptable race condition)

            # Atomic counter increments
            total_requests_key = f"{metrics_key}:total_requests"
            successful_requests_key = f"{metrics_key}:successful_requests"
            failed_requests_key = f"{metrics_key}:failed_requests"
            total_duration_key = f"{metrics_key}:total_duration"

            RedisOps.increment(total_requests_key, ttl_seconds=3600)
            RedisOps.increment_float(total_duration_key, duration, ttl_seconds=3600)

            if success:
                RedisOps.increment(successful_requests_key, ttl_seconds=3600)
            else:
                RedisOps.increment(failed_requests_key, ttl_seconds=3600)

            # Update metadata (min/max duration, last_updated) - acceptable race condition
            # This is approximate data, so minor race conditions are acceptable
            metrics_json = RedisOps.get(metrics_key)
            if metrics_json:
                metrics = json.loads(metrics_json)
            else:
                metrics = {
                    'min_duration': float('inf'),
                    'max_duration': 0.0,
                    'last_updated': time.time()
                }

            metrics['min_duration'] = min(metrics.get('min_duration', duration), duration)
            metrics['max_duration'] = max(metrics.get('max_duration', 0.0), duration)
            metrics['last_updated'] = time.time()

            # Store metadata with 1 hour TTL
            RedisOps.set_with_ttl(
                metrics_key,
                json.dumps(metrics),
                ttl_seconds=3600
            )

            # Track recent requests in sliding window (last 100 requests)
            window_data = {
                'timestamp': time.time(),
                'success': success,
                'duration': duration
            }
            RedisOps.list_push(window_key, json.dumps(window_data))

            # Trim window to last 100 entries
            window_length = RedisOps.list_length(window_key)
            if window_length > 100:
                # Keep only last 100 entries
                # Note: ltrim keeps elements from start to end index
                # To keep last 100: ltrim(key, -100, -1) but redis_client doesn't have direct ltrim
                # Workaround: Use list_pop_many to remove excess from front
                excess = window_length - 100
                if excess > 0:
                    RedisOps.list_pop_many(window_key, excess)

            # Set TTL on window key
            RedisOps.set_ttl(window_key, 3600)

        except Exception as e:
            # Non-critical: metrics tracking failure shouldn't break load balancing
            logger.debug("[LoadBalancer] Failed to record metrics in Redis: %s", e)

    def get_provider_health(self, provider: str) -> Dict[str, Any]:
        """
        Get health metrics for a provider from Redis.

        Args:
            provider: Provider name ('dashscope' or 'volcengine')

        Returns:
            Dictionary with health metrics:
            {
                'success_rate': float,  # 0.0 to 1.0
                'avg_duration': float,  # Average response time
                'total_requests': int,
                'recent_failures': int,  # Failures in last 100 requests
                'healthy': bool  # True if success_rate > 0.8 and recent_failures < 10
            }
        """
        if not self._use_redis:
            return {
                'success_rate': 1.0,  # Assume healthy if no metrics
                'avg_duration': 0.0,
                'total_requests': 0,
                'recent_failures': 0,
                'healthy': True
            }

        try:
            metrics_key = f"{METRICS_KEY_PREFIX}{provider}:stats"
            window_key = f"{METRICS_KEY_PREFIX}{provider}:window"

            # Get metrics
            metrics_json = RedisOps.get(metrics_key)
            if not metrics_json:
                return {
                    'success_rate': 1.0,
                    'avg_duration': 0.0,
                    'total_requests': 0,
                    'recent_failures': 0,
                    'healthy': True
                }

            # Get counters from atomic Redis keys
            total_requests_key = f"{metrics_key}:total_requests"
            successful_requests_key = f"{metrics_key}:successful_requests"
            total_duration_key = f"{metrics_key}:total_duration"

            total_str = RedisOps.get(total_requests_key)
            successful_str = RedisOps.get(successful_requests_key)
            total_duration_str = RedisOps.get(total_duration_key)

            total = int(total_str) if total_str else 0
            successful = int(successful_str) if successful_str else 0
            total_duration = float(total_duration_str) if total_duration_str else 0.0

            # Get metadata from JSON
            json.loads(metrics_json) if metrics_json else {}

            success_rate = successful / total if total > 0 else 1.0
            avg_duration = total_duration / total if total > 0 else 0.0

            # Count recent failures (last 100 requests)
            recent_failures = 0
            window_length = RedisOps.list_length(window_key)
            if window_length > 0:
                # Get last 100 entries (negative indices: -100 to -1)
                start_idx = -min(100, window_length)
                window_data = RedisOps.list_range(window_key, start_idx, -1)
                for entry_json in window_data:
                    try:
                        entry = json.loads(entry_json)
                        if not entry.get('success', True):
                            recent_failures += 1
                    except (json.JSONDecodeError, KeyError):
                        continue

            # Provider is healthy if success_rate > 80% and recent_failures < 10
            healthy = success_rate > 0.8 and recent_failures < 10

            return {
                'success_rate': success_rate,
                'avg_duration': avg_duration,
                'total_requests': total,
                'recent_failures': recent_failures,
                'healthy': healthy
            }

        except Exception as e:
            logger.debug("[LoadBalancer] Failed to get provider health from Redis: %s", e)
            return {
                'success_rate': 1.0,
                'avg_duration': 0.0,
                'total_requests': 0,
                'recent_failures': 0,
                'healthy': True
            }

    def _select_health_aware_provider(self) -> str:
        """
        Select provider based on health metrics (if available).

        Falls back to weighted selection if health data unavailable.

        Returns:
            'dashscope' or 'volcengine'
        """
        if not self._use_redis:
            # Fallback to weighted if Redis unavailable
            return self._select_deepseek_provider()

        dashscope_health = self.get_provider_health(self.PROVIDER_DASHSCOPE)
        volcengine_health = self.get_provider_health(self.PROVIDER_VOLCENGINE)

        # If both healthy, use weighted selection
        if dashscope_health['healthy'] and volcengine_health['healthy']:
            rand = random.randint(1, 100)
            provider = (
                self.PROVIDER_DASHSCOPE
                if rand <= self.weights.get('dashscope', 50)
                else self.PROVIDER_VOLCENGINE
            )
            logger.debug(
                "[LoadBalancer] Health-aware: both healthy, using weighted: %s",
                provider
            )
            return provider

        # If one is unhealthy, prefer the healthy one
        if dashscope_health['healthy'] and not volcengine_health['healthy']:
            logger.warning(
                "[LoadBalancer] Health-aware: Volcengine unhealthy "
                "(success_rate=%.2f%%, recent_failures=%s), routing to Dashscope",
                volcengine_health['success_rate'] * 100,
                volcengine_health['recent_failures']
            )
            return self.PROVIDER_DASHSCOPE

        if volcengine_health['healthy'] and not dashscope_health['healthy']:
            logger.warning(
                "[LoadBalancer] Health-aware: Dashscope unhealthy "
                "(success_rate=%.2f%%, recent_failures=%s), routing to Volcengine",
                dashscope_health['success_rate'] * 100,
                dashscope_health['recent_failures']
            )
            return self.PROVIDER_VOLCENGINE

        # Both unhealthy - use weighted selection (better than random)
        logger.warning(
            "[LoadBalancer] Health-aware: Both providers unhealthy, "
            "using weighted selection"
        )
        rand = random.randint(1, 100)
        provider = (
            self.PROVIDER_DASHSCOPE
            if rand <= self.weights.get('dashscope', 50)
            else self.PROVIDER_VOLCENGINE
        )
        return provider



# Singleton instance (initialized by LLMService)
# Note: Currently, each LLMService instance stores its own load balancer.
# The singleton pattern is kept for potential future use cases where
# a global load balancer instance might be needed (e.g., admin endpoints,
# monitoring, or shared state across services).
_load_balancer: Optional[LLMLoadBalancer] = None


def initialize_load_balancer(
    strategy: str = 'round_robin',
    weights: Optional[Dict[str, int]] = None,
    enabled: bool = True,
    dashscope_rate_limiter: Optional['DashscopeRateLimiter'] = None,
    load_balancer_rate_limiter: Optional[LoadBalancerRateLimiter] = None,
    rate_limit_aware: bool = True
) -> LLMLoadBalancer:
    """
    Initialize the global load balancer.

    Args:
        strategy: Load balancing strategy
        weights: Provider weights in format {'dashscope': X, 'volcengine': Y}
        enabled: Whether to enable load balancing
        dashscope_rate_limiter: Shared Dashscope rate limiter (for Dashscope route checks)
        load_balancer_rate_limiter: LoadBalancerRateLimiter instance (for Volcengine route checks)
        rate_limit_aware: Whether to consider rate limits when selecting provider

    Returns:
        Initialized load balancer instance

    Note: This function initializes both the global singleton and returns
    the instance. The singleton is kept for potential future use cases.
    """
    global _load_balancer
    _load_balancer = LLMLoadBalancer(
        strategy=strategy,
        weights=weights,
        enabled=enabled,
        dashscope_rate_limiter=dashscope_rate_limiter,
        load_balancer_rate_limiter=load_balancer_rate_limiter,
        rate_limit_aware=rate_limit_aware
    )
    return _load_balancer
