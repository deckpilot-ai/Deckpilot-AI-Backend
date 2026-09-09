"""Adaptive Health Tracker for LLM Provider/Model routing.

Provides EWMA latency tracking, circuit breaker pattern, and composite
scoring so that `call_llm()` always tries the fastest healthy candidate first,
automatically distributes load, and detects failures proactively via
background health probes.
"""

import logging
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # Healthy — traffic flows normally
    OPEN = "OPEN"  # Unhealthy — skip this candidate
    HALF_OPEN = "HALF_OPEN"  # Probing — allow one request to test recovery


class _ModelHealth:
    """Per-provider-model health metrics."""

    __slots__ = (
        "ewma_latency_ms",
        "total_calls",
        "total_successes",
        "total_failures",
        "consecutive_failures",
        "circuit_state",
        "circuit_opened_at",
        "last_success_at",
        "last_failure_at",
        "_recent_results",
    )

    # Circuit breaker thresholds
    FAILURE_THRESHOLD = 3  # consecutive failures to open circuit
    CIRCUIT_OPEN_DURATION = 60.0  # seconds before half-open

    # EWMA smoothing factor (higher = more weight on recent)
    EWMA_ALPHA = 0.3

    # Rolling window size for success rate calculation
    ROLLING_WINDOW = 20

    def __init__(self) -> None:
        self.ewma_latency_ms: float = 0.0
        self.total_calls: int = 0
        self.total_successes: int = 0
        self.total_failures: int = 0
        self.consecutive_failures: int = 0
        self.circuit_state: CircuitState = CircuitState.CLOSED
        self.circuit_opened_at: float = 0.0
        self.last_success_at: float = 0.0
        self.last_failure_at: float = 0.0
        self._recent_results: list[bool] = []  # True=success, False=failure

    @property
    def success_rate(self) -> float:
        """Success rate over the rolling window (0.0 to 1.0)."""
        if not self._recent_results:
            return 1.0  # Assume healthy until proven otherwise
        return sum(1 for r in self._recent_results if r) / len(self._recent_results)

    def record_success(self, latency_ms: float) -> None:
        """Record a successful LLM call."""
        self.total_calls += 1
        self.total_successes += 1
        self.consecutive_failures = 0
        self.last_success_at = time.time()

        # Update EWMA latency
        if self.ewma_latency_ms == 0.0:
            self.ewma_latency_ms = latency_ms
        else:
            self.ewma_latency_ms = (
                self.EWMA_ALPHA * latency_ms
                + (1 - self.EWMA_ALPHA) * self.ewma_latency_ms
            )

        # Update rolling window
        self._recent_results.append(True)
        if len(self._recent_results) > self.ROLLING_WINDOW:
            self._recent_results.pop(0)

        # Close circuit on success
        if self.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            self.circuit_state = CircuitState.CLOSED
            logger.info("Circuit CLOSED (recovered)")

    def record_failure(self) -> None:
        """Record a failed LLM call."""
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_failure_at = time.time()

        # Update rolling window
        self._recent_results.append(False)
        if len(self._recent_results) > self.ROLLING_WINDOW:
            self._recent_results.pop(0)

        # Open circuit after threshold consecutive failures
        if (
            self.consecutive_failures >= self.FAILURE_THRESHOLD
            and self.circuit_state == CircuitState.CLOSED
        ):
            self.circuit_state = CircuitState.OPEN
            self.circuit_opened_at = time.time()
            logger.warning(
                "Circuit OPEN after %d consecutive failures",
                self.consecutive_failures,
            )

    def is_available(self) -> bool:
        """Check if this candidate should receive traffic."""
        if self.circuit_state == CircuitState.CLOSED:
            return True
        if self.circuit_state == CircuitState.HALF_OPEN:
            return True  # Allow one test request
        # OPEN — check if cooldown has elapsed
        if time.time() - self.circuit_opened_at >= self.CIRCUIT_OPEN_DURATION:
            self.circuit_state = CircuitState.HALF_OPEN
            logger.info("Circuit transitioned to HALF_OPEN (cooldown elapsed)")
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the admin health API."""
        return {
            "ewma_latency_ms": round(self.ewma_latency_ms, 1),
            "success_rate": round(self.success_rate, 3),
            "circuit_state": self.circuit_state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "last_success_at": int(self.last_success_at) if self.last_success_at else None,
            "last_failure_at": int(self.last_failure_at) if self.last_failure_at else None,
        }


class HealthTracker:
    """Singleton registry of per-provider-model health metrics.

    Thread-safe via a reentrant lock. All data is in-memory for microsecond
    lookups with zero database overhead.
    """

    _instance: "HealthTracker | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "HealthTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._registry: dict[str, _ModelHealth] = {}
                    inst._data_lock = threading.Lock()
                    inst._last_probe_at: float = 0.0
                    cls._instance = inst
        return cls._instance

    @staticmethod
    def _key(provider_name: str, model_id: str) -> str:
        return f"{provider_name}::{model_id}"

    def _get_or_create(self, provider_name: str, model_id: str) -> _ModelHealth:
        key = self._key(provider_name, model_id)
        with self._data_lock:
            if key not in self._registry:
                self._registry[key] = _ModelHealth()
            return self._registry[key]

    def record_success(
        self, provider_name: str, model_id: str, latency_ms: float
    ) -> None:
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_success(latency_ms)
        logger.debug(
            "Health ✓ %s/%s latency=%dms ewma=%dms",
            provider_name,
            model_id,
            latency_ms,
            health.ewma_latency_ms,
        )

    def record_failure(self, provider_name: str, model_id: str) -> None:
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_failure()
        logger.debug(
            "Health ✗ %s/%s consecutive_failures=%d circuit=%s",
            provider_name,
            model_id,
            health.consecutive_failures,
            health.circuit_state.value,
        )

    def is_available(self, provider_name: str, model_id: str) -> bool:
        """Check if a provider/model candidate is available (circuit not open)."""
        key = self._key(provider_name, model_id)
        with self._data_lock:
            health = self._registry.get(key)
            if health is None:
                return True  # Unknown = assume healthy
            return health.is_available()

    def composite_score(
        self,
        provider_name: str,
        model_id: str,
        base_priority: int,
    ) -> float:
        """Calculate the composite routing score for a candidate.

        score = (base_priority × 0.3) + (latency_score × 0.4) + (reliability_score × 0.3)

        Higher score = tried first.
        """
        key = self._key(provider_name, model_id)
        with self._data_lock:
            health = self._registry.get(key)

        if health is None or health.total_calls == 0:
            # No data yet — use base priority as-is (normalized to 0-100)
            return float(min(base_priority, 100))

        # Normalize base priority to 0-100
        norm_priority = min(base_priority, 100)

        # Latency score: lower latency = higher score
        # Clamp at 50_000ms (50s) to avoid division issues
        clamped_latency = min(health.ewma_latency_ms, 50_000.0)
        latency_score = max(0.0, 100.0 - (clamped_latency / 500.0))

        # Reliability score: success rate as percentage
        reliability_score = health.success_rate * 100.0

        return (
            norm_priority * 0.3
            + latency_score * 0.4
            + reliability_score * 0.3
        )

    def rank_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sort candidates by composite score descending, filtering out circuit-broken ones.

        Each candidate dict must have keys: provider_name, model_id, base_priority.
        Returns a new list with an added 'composite_score' key.
        """
        scored: list[dict[str, Any]] = []
        circuit_broken: list[dict[str, Any]] = []

        for c in candidates:
            pname = c["provider_name"]
            mid = c["model_id"]
            bp = c.get("base_priority", 50)

            available = self.is_available(pname, mid)
            score = self.composite_score(pname, mid, bp)
            entry = {**c, "composite_score": round(score, 2)}

            if available:
                scored.append(entry)
            else:
                circuit_broken.append(entry)

        # Sort available candidates by score descending
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # Append circuit-broken as last resort (they might recover)
        circuit_broken.sort(key=lambda x: x["composite_score"], reverse=True)
        scored.extend(circuit_broken)

        return scored

    def record_probe(self, provider_name: str, latency_ms: float | None, success: bool) -> None:
        """Record a background health probe result for a provider.

        Uses a synthetic model_id '__probe__' to track provider-level health.
        """
        self._last_probe_at = time.time()
        if success and latency_ms is not None:
            self.record_success(provider_name, "__probe__", latency_ms)
        elif not success:
            self.record_failure(provider_name, "__probe__")

    def get_status_overview(self) -> dict[str, Any]:
        """Return full health status for the admin API."""
        with self._data_lock:
            providers: dict[str, list[dict[str, Any]]] = {}
            for key, health in self._registry.items():
                parts = key.split("::", 1)
                pname = parts[0]
                mid = parts[1] if len(parts) > 1 else "unknown"

                entry = health.to_dict()
                entry["model_id"] = mid
                entry["composite_score"] = round(
                    self.composite_score(pname, mid, 50), 2
                )

                if pname not in providers:
                    providers[pname] = []
                providers[pname].append(entry)

        # Sort models within each provider by composite score
        for models in providers.values():
            models.sort(key=lambda x: x["composite_score"], reverse=True)

        return {
            "providers": [
                {"name": pname, "models": models}
                for pname, models in sorted(providers.items())
            ],
            "probe_interval_seconds": 60,
            "last_probe_at": int(self._last_probe_at) if self._last_probe_at else None,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._registry.clear()
                cls._instance._last_probe_at = 0.0


# Module-level convenience accessor
health_tracker = HealthTracker()
