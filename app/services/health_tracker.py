"""Adaptive Health Tracker & Dynamic Capability Model Priority Router.

Provides automated 60-second health state tracking, EWMA latency tracking,
circuit breaker state management, capability-aware priority rankings,
real production request feedback (schema validations & QC pass rates),
and stability damping to prevent priority flapping.
"""

from enum import Enum
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class ModelHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    SLOW = "SLOW"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_ERROR = "AUTH_ERROR"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    TEMPORARILY_DISABLED = "TEMPORARILY_DISABLED"
    UNKNOWN = "UNKNOWN"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # Healthy — traffic flows normally
    OPEN = "OPEN"  # Unhealthy — skip this candidate
    HALF_OPEN = "HALF_OPEN"  # Probing — allow one test request to verify recovery


class ModelCapability(str, Enum):
    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    FAST_TEXT = "fast_text"
    PRESENTATION_PLANNING = "presentation_planning"


def detect_model_capabilities(model_id: str, display_name: str | None = None) -> list[str]:
    """Infer supported capabilities from model identifier and display name."""
    mid = (model_id or "").lower()
    mname = (display_name or "").lower()
    combined = f"{mid} {mname}"

    caps = set()

    # Fast text: general fast conversational generation
    if any(k in combined for k in ("flash", "lite", "mini", "haiku", "lightning", "nano", "spark", "mimo", "laguna", "gpt-oss-20b", "mercury")):
        caps.add(ModelCapability.FAST_TEXT.value)

    # Vision: image extraction, brand inspection, layout visual analysis
    if any(k in combined for k in ("vl", "vision", "gemini", "gpt-4o", "pro-vision", "omni", "claude-3", "stepfun", "nex")):
        caps.add(ModelCapability.VISION.value)

    # Reasoning: deep outline synthesis, architectural logic, complex constraints
    if any(k in combined for k in ("nemotron", "reasoning", "opus", "sonnet", "deepseek", "o3", "r1", "qwen3.8-max", "sol", "terra", "luna", "astra", "fable", "pro")):
        caps.add(ModelCapability.REASONING.value)

    # Structured output: strictly follows schema and emits valid JSON envelopes
    if any(k in combined for k in ("gpt-4o", "gemini-2.5", "flash", "fin", "pro", "sonnet", "deepseek", "ling", "nemotron", "mercury", "qwen", "laguna")):
        caps.add(ModelCapability.STRUCTURED_OUTPUT.value)

    # Presentation planning: holistic slide deck flow and chapter hierarchy
    if any(k in combined for k in ("gpt-4o", "gemini-2.5", "claude", "opus", "sonnet", "nemotron", "ling", "deepseek", "mercury", "qwen", "sol")):
        caps.add(ModelCapability.PRESENTATION_PLANNING.value)

    # Defaults if no specific flags caught
    if not caps:
        caps.add(ModelCapability.FAST_TEXT.value)
        caps.add(ModelCapability.STRUCTURED_OUTPUT.value)

    return sorted(list(caps))


def get_base_quality_score(provider_name: str, model_id: str, configured_priority: int = 50) -> float:
    """Return intrinsic capability/quality score (0-100) based on model architecture."""
    mid = model_id.lower()
    pname = provider_name.lower()
    combined = f"{pname}::{mid}"

    # Frontier tier (95-99)
    if any(k in combined for k in ("claude-opus-5", "claude-sonnet-5", "claude-opus-4.8", "gpt-5.6-sol", "gpt-4o")):
        base = 98.0
    elif any(k in combined for k in ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-pro")):
        base = 95.0
    elif any(k in combined for k in ("mercury-2.5", "mercury-2")):
        base = 94.0
    elif any(k in combined for k in ("ling-3.0-flash-vl-free", "ling-3.0-flash-fin-free", "nemotron-3.5-lightning-free")):
        base = 93.0
    elif any(k in combined for k in ("deepseek-v4-flash", "deepseek-v4.1", "qwen3.8-max")):
        base = 91.0
    elif any(k in combined for k in ("nemotron-3-ultra-free", "nemotron-3-super-free", "ling-3.0-flash-sante-free", "gpt-5.6-luna-free")):
        base = 88.0
    elif any(k in combined for k in ("nex-n2.5-pro", "laguna-s-2.1", "openai/gpt-oss-120b", "kimi-k3-free", "grok-4.6-free")):
        base = 85.0
    else:
        # Scale configured priority (1-100) to baseline (70-85)
        base = 70.0 + (min(max(configured_priority, 1), 100) * 0.15)

    return round(base, 2)


class _ModelHealth:
    """Per-provider-model health metrics, status, and production observability."""

    __slots__ = (
        "provider_name",
        "model_id",
        "status",
        "circuit_state",
        "circuit_opened_at",
        "ewma_latency_ms",
        "rolling_latencies",
        "consecutive_failures",
        "consecutive_successes",
        "total_probes",
        "probe_successes",
        "probe_failures",
        "real_calls",
        "real_successes",
        "real_failures",
        "schema_validation_failures",
        "qc_rejections",
        "last_error",
        "last_error_status",
        "last_checked_at",
        "last_success_at",
        "last_failure_at",
        "backoff_cycles_remaining",
        "_recent_results",
    )

    FAILURE_THRESHOLD = 3  # consecutive failures to open circuit
    CIRCUIT_OPEN_DURATION = 60.0  # seconds before half-open
    EWMA_ALPHA = 0.3  # Smoothing factor
    ROLLING_WINDOW = 10  # Window for synthetic probe success rate
    SLOW_LATENCY_THRESHOLD_MS = 5000.0  # Latency above this marks model SLOW

    def __init__(self, provider_name: str, model_id: str) -> None:
        self.provider_name: str = provider_name
        self.model_id: str = model_id
        self.status: ModelHealthState = ModelHealthState.UNKNOWN
        self.circuit_state: CircuitState = CircuitState.CLOSED
        self.circuit_opened_at: float = 0.0
        self.ewma_latency_ms: float = 0.0
        self.rolling_latencies: list[float] = []
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.total_probes: int = 0
        self.probe_successes: int = 0
        self.probe_failures: int = 0
        self.real_calls: int = 0
        self.real_successes: int = 0
        self.real_failures: int = 0
        self.schema_validation_failures: int = 0
        self.qc_rejections: int = 0
        self.last_error: str | None = None
        self.last_error_status: int | None = None
        self.last_checked_at: float = 0.0
        self.last_success_at: float = 0.0
        self.last_failure_at: float = 0.0
        self.backoff_cycles_remaining: int = 0
        self._recent_results: list[bool] = []

    @property
    def synthetic_success_rate(self) -> float:
        """Synthetic probe success rate over rolling window (0.0 to 1.0)."""
        if not self._recent_results:
            return 1.0
        return sum(1 for r in self._recent_results if r) / len(self._recent_results)

    @property
    def production_success_rate(self) -> float:
        """Real request success rate (0.0 to 1.0)."""
        if self.real_calls == 0:
            return 1.0
        return self.real_successes / self.real_calls

    def record_probe_success(self, latency_ms: float) -> None:
        """Record synthetic 60s health probe success."""
        now = time.time()
        self.total_probes += 1
        self.probe_successes += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_success_at = now
        self.last_checked_at = now
        self.last_error = None
        self.last_error_status = None
        self.backoff_cycles_remaining = 0

        # Update EWMA and rolling latencies
        if self.ewma_latency_ms == 0.0:
            self.ewma_latency_ms = latency_ms
        else:
            self.ewma_latency_ms = (self.EWMA_ALPHA * latency_ms) + ((1.0 - self.EWMA_ALPHA) * self.ewma_latency_ms)

        self.rolling_latencies.append(latency_ms)
        if len(self.rolling_latencies) > 10:
            self.rolling_latencies.pop(0)

        self._recent_results.append(True)
        if len(self._recent_results) > self.ROLLING_WINDOW:
            self._recent_results.pop(0)

        # Update status
        if latency_ms >= self.SLOW_LATENCY_THRESHOLD_MS:
            self.status = ModelHealthState.SLOW
        else:
            self.status = ModelHealthState.HEALTHY

        # Close circuit if in HALF_OPEN or OPEN
        if self.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            self.circuit_state = CircuitState.CLOSED
            logger.info("Circuit CLOSED for %s/%s after successful probe", self.provider_name, self.model_id)

    def record_probe_failure(self, status_code: int | None, error_msg: str, latency_ms: float | None = None) -> None:
        """Record synthetic 60s health probe failure."""
        now = time.time()
        self.total_probes += 1
        self.probe_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_at = now
        self.last_checked_at = now
        self.last_error = error_msg
        self.last_error_status = status_code

        if latency_ms is not None:
            self.rolling_latencies.append(latency_ms)
            if len(self.rolling_latencies) > 10:
                self.rolling_latencies.pop(0)

        self._recent_results.append(False)
        if len(self._recent_results) > self.ROLLING_WINDOW:
            self._recent_results.pop(0)

        # Categorize status
        err_lower = (error_msg or "").lower()
        if status_code == 429 or "rate limit" in err_lower:
            self.status = ModelHealthState.RATE_LIMITED
        elif status_code == 402 or "quota" in err_lower or "insufficient" in err_lower:
            self.status = ModelHealthState.QUOTA_EXCEEDED
        elif status_code in (401, 403) or "auth" in err_lower or "api_key" in err_lower:
            self.status = ModelHealthState.AUTH_ERROR
        elif status_code in (500, 502, 503, 504) or "timeout" in err_lower or "connect" in err_lower:
            self.status = ModelHealthState.UNAVAILABLE
        else:
            self.status = ModelHealthState.DEGRADED

        # Trip circuit breaker
        if self.consecutive_failures >= self.FAILURE_THRESHOLD and self.circuit_state == CircuitState.CLOSED:
            self.circuit_state = CircuitState.OPEN
            self.circuit_opened_at = now
            self.status = ModelHealthState.TEMPORARILY_DISABLED
            # Set exponential backoff cycles (e.g. skip next 2 probe cycles)
            self.backoff_cycles_remaining = 2
            logger.warning(
                "Circuit OPEN for %s/%s after %d failures (Status: %s)",
                self.provider_name, self.model_id, self.consecutive_failures, self.status.value,
            )

    def record_production_success(self, latency_ms: float) -> None:
        """Record a successful user/agent production request."""
        now = time.time()
        self.real_calls += 1
        self.real_successes += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_success_at = now

        if self.ewma_latency_ms == 0.0:
            self.ewma_latency_ms = latency_ms
        else:
            self.ewma_latency_ms = (self.EWMA_ALPHA * latency_ms) + ((1.0 - self.EWMA_ALPHA) * self.ewma_latency_ms)

        if self.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            self.circuit_state = CircuitState.CLOSED
            self.status = ModelHealthState.HEALTHY

    def record_production_failure(self, status_code: int | None, error_msg: str) -> None:
        """Record a real production request failure and trigger failover state."""
        now = time.time()
        self.real_calls += 1
        self.real_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_at = now
        self.last_error = error_msg
        self.last_error_status = status_code

        err_lower = (error_msg or "").lower()
        if status_code == 429 or "rate limit" in err_lower:
            self.status = ModelHealthState.RATE_LIMITED
        elif status_code == 402 or "quota" in err_lower or "insufficient" in err_lower:
            self.status = ModelHealthState.QUOTA_EXCEEDED
        elif status_code in (401, 403):
            self.status = ModelHealthState.AUTH_ERROR
        elif status_code in (500, 502, 503, 504) or "timeout" in err_lower:
            self.status = ModelHealthState.UNAVAILABLE
        else:
            self.status = ModelHealthState.DEGRADED

        if self.consecutive_failures >= self.FAILURE_THRESHOLD and self.circuit_state == CircuitState.CLOSED:
            self.circuit_state = CircuitState.OPEN
            self.circuit_opened_at = now
            self.status = ModelHealthState.TEMPORARILY_DISABLED
            self.backoff_cycles_remaining = 2

    def record_schema_failure(self, reason: str) -> None:
        """Record that output returned by the model failed structured JSON / contract schema."""
        self.schema_validation_failures += 1
        self.consecutive_failures += 1
        self.last_failure_at = time.time()
        self.last_error = f"Schema validation failed: {reason}"
        if self.status == ModelHealthState.HEALTHY:
            self.status = ModelHealthState.DEGRADED

    def record_qc_result(self, passed: bool) -> None:
        """Record downstream Agent Quality Control verification outcome."""
        if not passed:
            self.qc_rejections += 1
            if self.status == ModelHealthState.HEALTHY:
                self.status = ModelHealthState.DEGRADED

    def is_available_for_traffic(self) -> bool:
        """Check if candidate can receive live production user requests."""
        if self.circuit_state == CircuitState.CLOSED:
            return self.status not in (
                ModelHealthState.AUTH_ERROR,
                ModelHealthState.QUOTA_EXCEEDED,
                ModelHealthState.TEMPORARILY_DISABLED,
            )
        if self.circuit_state == CircuitState.HALF_OPEN:
            return True
        # OPEN — verify if circuit open duration (cooldown) has elapsed
        if time.time() - self.circuit_opened_at >= self.CIRCUIT_OPEN_DURATION:
            self.circuit_state = CircuitState.HALF_OPEN
            logger.info("Circuit transitioned to HALF_OPEN for %s/%s", self.provider_name, self.model_id)
            return True
        return False

    def calculate_health_score(self, configured_priority: int = 50) -> float:
        """Compute the weighted quality-first health score (0.0 to 100.0).

        Model Score =
            Quality Score (40%)
            + Real Production Reliability (25%)
            + Synthetic Health Reliability (15%)
            + Latency Score (10%)
            + Capability Match (10%)
            - State Penalties
        """
        if self.circuit_state == CircuitState.OPEN or self.status == ModelHealthState.TEMPORARILY_DISABLED:
            return 0.0

        base_quality = get_base_quality_score(self.provider_name, self.model_id, configured_priority)
        prod_reliability = self.production_success_rate * 100.0
        synth_reliability = self.synthetic_success_rate * 100.0

        # Sub-linear latency penalty: 500ms -> 97 score, 2000ms -> 87 score, 5000ms -> 67 score
        effective_latency = self.ewma_latency_ms if self.ewma_latency_ms > 0 else 500.0
        latency_score = max(0.0, 100.0 - (min(effective_latency, 15000.0) / 150.0))

        # Base composite before penalties
        score = (
            (base_quality * 0.40)
            + (prod_reliability * 0.25)
            + (synth_reliability * 0.15)
            + (latency_score * 0.10)
            + (min(configured_priority, 100) * 0.10)
        )

        # Deduct penalties for degraded states
        if self.status == ModelHealthState.RATE_LIMITED:
            score -= 30.0
        elif self.status == ModelHealthState.SLOW:
            score -= 10.0
        elif self.status == ModelHealthState.DEGRADED:
            score -= 15.0
        elif self.status == ModelHealthState.UNAVAILABLE:
            score -= 60.0
        elif self.status in (ModelHealthState.AUTH_ERROR, ModelHealthState.QUOTA_EXCEEDED):
            score -= 80.0

        # Heavy deduction for downstream schema failures and QC rejections
        score -= min(self.schema_validation_failures * 5.0, 25.0)
        score -= min(self.qc_rejections * 4.0, 20.0)

        return round(max(0.0, min(score, 100.0)), 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics for observability and admin API."""
        return {
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "status": self.status.value,
            "circuit_state": self.circuit_state.value,
            "ewma_latency_ms": round(self.ewma_latency_ms, 1),
            "synthetic_success_rate": round(self.synthetic_success_rate, 3),
            "production_success_rate": round(self.production_success_rate, 3),
            "total_probes": self.total_probes,
            "real_calls": self.real_calls,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "schema_validation_failures": self.schema_validation_failures,
            "qc_rejections": self.qc_rejections,
            "last_error": self.last_error,
            "last_error_status": self.last_error_status,
            "last_checked_at": int(self.last_checked_at) if self.last_checked_at else None,
            "last_success_at": int(self.last_success_at) if self.last_success_at else None,
            "last_failure_at": int(self.last_failure_at) if self.last_failure_at else None,
        }


class HealthTracker:
    """Thread-safe global singleton for provider/model health and dynamic capability routing."""

    _instance: "HealthTracker | None" = None
    _lock = threading.Lock()

    # Flapping prevention threshold: new challenger must beat incumbent #1 by this margin to replace it
    STABILITY_THRESHOLD = 3.0

    def __new__(cls) -> "HealthTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._registry: dict[str, _ModelHealth] = {}
                    inst._provider_outages: dict[str, tuple[float, float, str, int | None]] = {}
                    inst._data_lock = threading.RLock()
                    inst._last_probe_at: float = 0.0
                    inst._top_model_by_capability: dict[str, str] = {}
                    inst._capability_rankings: dict[str, list[dict[str, Any]]] = {}
                    cls._instance = inst
        return cls._instance

    @staticmethod
    def _key(provider_name: str, model_id: str) -> str:
        return f"{provider_name.lower()}::{model_id}"

    def _get_or_create(self, provider_name: str, model_id: str) -> _ModelHealth:
        key = self._key(provider_name, model_id)
        with self._data_lock:
            if key not in self._registry:
                self._registry[key] = _ModelHealth(provider_name, model_id)
            return self._registry[key]

    # --- Backward compatibility methods for existing call sites ---
    def record_success(self, provider_name: str, model_id: str, latency_ms: float) -> None:
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_production_success(latency_ms)

    def record_failure(self, provider_name: str, model_id: str) -> None:
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_production_failure(None, "Production request failure")

    def record_probe(self, provider_name: str, latency_ms: float | None, success: bool) -> None:
        self._last_probe_at = time.time()
        health = self._get_or_create(provider_name, "__probe__")
        with self._data_lock:
            if success and latency_ms is not None:
                health.record_probe_success(latency_ms)
            else:
                health.record_probe_failure(None, "Probe ping failure")

    def is_available(self, provider_name: str, model_id: str) -> bool:
        pname_lower = provider_name.lower()
        now = time.time()
        with self._data_lock:
            if pname_lower in self._provider_outages:
                outage_time, cooldown, _, _ = self._provider_outages[pname_lower]
                if now - outage_time < cooldown:
                    return False
                self._provider_outages.pop(pname_lower, None)
            key = self._key(provider_name, model_id)
            health = self._registry.get(key)
            if health is None:
                return True
            return health.is_available_for_traffic()

    def record_account_outage(
        self,
        provider_name: str,
        status_code: int | None,
        error_msg: str,
        cooldown_seconds: float = 1800.0,
    ) -> None:
        """Mark entire provider as circuit-broken on account outage (401, 402, quota 429)."""
        now = time.time()
        pname_lower = provider_name.lower()
        with self._data_lock:
            self._provider_outages[pname_lower] = (now, cooldown_seconds, error_msg, status_code)
            p_prefix = f"{pname_lower}::"
            for key, health in self._registry.items():
                if key.startswith(p_prefix):
                    health.circuit_state = CircuitState.OPEN
                    health.circuit_opened_at = now
                    health.CIRCUIT_OPEN_DURATION = max(health.CIRCUIT_OPEN_DURATION, cooldown_seconds)
                    health.status = (
                        ModelHealthState.AUTH_ERROR if status_code in (401, 403)
                        else ModelHealthState.QUOTA_EXCEEDED
                    )
                    health.last_error = error_msg
                    health.last_error_status = status_code
                    health.consecutive_failures = max(health.consecutive_failures, 3)
            logger.warning(
                "HealthTracker: Provider %s placed in full account outage cooldown for %ds (HTTP %s: %s)",
                provider_name, int(cooldown_seconds), status_code, error_msg[:100],
            )

    def composite_score(self, provider_name: str, model_id: str, base_priority: int) -> float:
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            return health.calculate_health_score(base_priority)

    # --- Upgraded Fine-Grained Recording Methods ---
    def record_probe_result(
        self,
        provider_name: str,
        model_id: str,
        status_code: int,
        latency_ms: float,
        error_msg: str | None = None,
    ) -> None:
        """Record granular probe result for an individual model."""
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            self._last_probe_at = time.time()
            if status_code == 200:
                health.record_probe_success(latency_ms)
            else:
                health.record_probe_failure(status_code, error_msg or f"HTTP {status_code}", latency_ms)

    def record_production_error(
        self,
        provider_name: str,
        model_id: str,
        status_code: int | None,
        error_msg: str,
    ) -> None:
        """Record real-world production error during agent call."""
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_production_failure(status_code, error_msg)

    def record_schema_validation_failure(
        self,
        provider_name: str,
        model_id: str,
        agent_type: str,
        reason: str,
    ) -> None:
        """Penalize model for emitting unparseable or contract-violating JSON."""
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_schema_failure(f"[{agent_type}] {reason}")

    def record_qc_feedback(
        self,
        provider_name: str,
        model_id: str,
        passed: bool,
    ) -> None:
        """Record downstream Agent Quality Control verification outcome."""
        health = self._get_or_create(provider_name, model_id)
        with self._data_lock:
            health.record_qc_result(passed)

    # --- Dynamic Capability-Aware Ranking & Flapping Prevention ---
    def rank_candidates_for_capabilities(
        self,
        candidates: list[dict[str, Any]],
        required_capabilities: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Sort candidates using quality-weighted health score and stability damping.

        If required_capabilities are given, filters/prioritizes models matching those capabilities.
        Applies hysteresis to prevent switching Priority 1 on minor fluctuations.
        """
        required_set = set(required_capabilities or [])
        scored: list[dict[str, Any]] = []
        circuit_broken: list[dict[str, Any]] = []

        with self._data_lock:
            for c in candidates:
                pname = c["provider_name"]
                mid = c["model_id"]
                bp = c.get("base_priority", 50)
                display_name = c.get("display_name") or mid

                health = self._get_or_create(pname, mid)
                available = health.is_available_for_traffic()
                score = health.calculate_health_score(bp)

                caps = set(c.get("capabilities") or detect_model_capabilities(mid, display_name))
                matches_caps = True
                if required_set:
                    # Capability match bonus or filter
                    if required_set.intersection(caps):
                        score += 5.0
                    else:
                        matches_caps = False

                entry = {
                    **c,
                    "composite_score": round(score, 2),
                    "health_status": health.status.value,
                    "circuit_state": health.circuit_state.value,
                    "ewma_latency_ms": round(health.ewma_latency_ms, 1),
                    "capabilities": list(caps),
                    "matches_capabilities": matches_caps,
                }

                if available and matches_caps:
                    scored.append(entry)
                else:
                    circuit_broken.append(entry)

            # Sort available candidates by composite score descending
            scored.sort(key=lambda x: x["composite_score"], reverse=True)

            # Apply Stability Damping (Flapping Prevention) for top candidate
            primary_cap = required_capabilities[0] if required_capabilities else "general"
            incumbent_key = self._top_model_by_capability.get(primary_cap)

            if scored and incumbent_key:
                top_key = f"{scored[0]['provider_name'].lower()}::{scored[0]['model_id']}"
                if top_key != incumbent_key:
                    # Look up incumbent candidate in current pool
                    incumbent_idx = next(
                        (i for i, x in enumerate(scored) if f"{x['provider_name'].lower()}::{x['model_id']}" == incumbent_key),
                        None,
                    )
                    if incumbent_idx is not None:
                        incumbent_candidate = scored[incumbent_idx]
                        incumbent_score = incumbent_candidate["composite_score"]
                        challenger_score = scored[0]["composite_score"]
                        incumbent_health = self._registry.get(incumbent_key)

                        # Only displace incumbent #1 if challenger exceeds by stability threshold OR incumbent is unhealthy
                        is_incumbent_healthy = incumbent_health and incumbent_health.status == ModelHealthState.HEALTHY
                        if is_incumbent_healthy and (challenger_score < incumbent_score + self.STABILITY_THRESHOLD):
                            # Retain incumbent as Priority #1
                            scored.pop(incumbent_idx)
                            scored.insert(0, incumbent_candidate)

            # Record current active top model
            if scored:
                self._top_model_by_capability[primary_cap] = f"{scored[0]['provider_name'].lower()}::{scored[0]['model_id']}"

            # Fallback candidates appended at the tail
            circuit_broken.sort(key=lambda x: x["composite_score"], reverse=True)
            scored.extend(circuit_broken)
            return scored

    def rank_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Standard candidate ranking maintaining compatibility with existing callers."""
        return self.rank_candidates_for_capabilities(candidates, required_capabilities=None)

    def refresh_capability_rankings(self, all_candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Precompute and cache priority rankings for every capability category."""
        rankings = {}
        for cap in ModelCapability:
            ranked = self.rank_candidates_for_capabilities(all_candidates, required_capabilities=[cap.value])
            rankings[cap.value] = [
                {
                    "provider_name": r["provider_name"],
                    "model_id": r["model_id"],
                    "composite_score": r["composite_score"],
                    "health_status": r["health_status"],
                    "ewma_latency_ms": r["ewma_latency_ms"],
                }
                for r in ranked[:5]  # Top 5 per capability
            ]
        with self._data_lock:
            self._capability_rankings = rankings
        return rankings

    def get_status_overview(self) -> dict[str, Any]:
        """Return comprehensive health metrics and capability rankings for the Admin API."""
        with self._data_lock:
            providers: dict[str, list[dict[str, Any]]] = {}
            for key, health in self._registry.items():
                parts = key.split("::", 1)
                pname = parts[0]
                mid = parts[1] if len(parts) > 1 else "unknown"

                entry = health.to_dict()
                entry["composite_score"] = round(health.calculate_health_score(50), 2)
                entry["capabilities"] = detect_model_capabilities(mid)

                if pname not in providers:
                    providers[pname] = []
                providers[pname].append(entry)

            for models in providers.values():
                models.sort(key=lambda x: x["composite_score"], reverse=True)

            return {
                "providers": [
                    {"name": pname, "models": models}
                    for pname, models in sorted(providers.items())
                ],
                "probe_interval_seconds": 60,
                "last_probe_at": int(self._last_probe_at) if self._last_probe_at else None,
                "capability_rankings": self._capability_rankings,
                "top_models": self._top_model_by_capability,
            }

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._registry.clear()
                cls._instance._top_model_by_capability.clear()
                cls._instance._capability_rankings.clear()
                cls._instance._last_probe_at = 0.0


# Module-level convenience accessor
health_tracker = HealthTracker()
