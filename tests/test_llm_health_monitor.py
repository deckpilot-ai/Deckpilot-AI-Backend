"""Comprehensive tests for LLM Provider Health Monitor and Dynamic Model Priority Router."""

import time
from unittest.mock import patch
import httpx
import pytest
from sqlalchemy.orm import Session

from app.models.system_lock import SystemLock
from app.services.health_tracker import (
    CircuitState,
    HealthTracker,
    ModelCapability,
    ModelHealthState,
    _ModelHealth,
    detect_model_capabilities,
    get_base_quality_score,
    health_tracker,
)


@pytest.fixture(autouse=True)
def reset_health():
    health_tracker.reset()
    yield
    health_tracker.reset()


def test_model_capabilities_detection():
    """Verify models are classified correctly into capability categories."""
    gemini_caps = detect_model_capabilities("gemini-2.5-flash", "Gemini 2.5 Flash")
    assert ModelCapability.VISION.value in gemini_caps
    assert ModelCapability.STRUCTURED_OUTPUT.value in gemini_caps
    assert ModelCapability.FAST_TEXT.value in gemini_caps

    claude_caps = detect_model_capabilities("claude-opus-5", "Claude Opus 5")
    assert ModelCapability.REASONING.value in claude_caps
    assert ModelCapability.PRESENTATION_PLANNING.value in claude_caps

    vision_caps = detect_model_capabilities("ling-3.0-flash-vl-free", "Ling 3.0 Flash VL Free")
    assert ModelCapability.VISION.value in vision_caps


def test_base_quality_scores():
    """Verify frontier models have higher base quality than basic models."""
    opus_score = get_base_quality_score("anthropic", "claude-opus-5", 100)
    gpt_score = get_base_quality_score("openai", "gpt-4o", 95)
    fast_free_score = get_base_quality_score("bynara", "laguna-s-2.1", 50)

    assert opus_score >= gpt_score
    assert gpt_score > fast_free_score


def test_health_state_transitions_and_circuit_breaker():
    """Verify state transitions: HEALTHY, SLOW, RATE_LIMITED, UNAVAILABLE, and Circuit Breaker."""
    m = _ModelHealth("test-provider", "model-a")
    assert m.status == ModelHealthState.UNKNOWN
    assert m.circuit_state == CircuitState.CLOSED

    # 1. Successful fast probe -> HEALTHY
    m.record_probe_success(latency_ms=250.0)
    assert m.status == ModelHealthState.HEALTHY
    assert m.is_available_for_traffic() is True
    assert m.consecutive_failures == 0

    # 2. Slow probe (> 5000ms) -> SLOW
    m.record_probe_success(latency_ms=6200.0)
    assert m.status == ModelHealthState.SLOW
    assert m.is_available_for_traffic() is True

    # 3. Rate limited probe (429) -> RATE_LIMITED
    m.record_probe_failure(status_code=429, error_msg="Rate limit exceeded", latency_ms=100.0)
    assert m.status == ModelHealthState.RATE_LIMITED
    assert m.consecutive_failures == 1

    # 4. Quota exceeded (402)
    m.record_probe_failure(status_code=402, error_msg="Insufficient credits", latency_ms=150.0)
    assert m.status == ModelHealthState.QUOTA_EXCEEDED
    assert m.consecutive_failures == 2

    # 5. Third consecutive failure trips circuit breaker -> OPEN / TEMPORARILY_DISABLED
    m.record_probe_failure(status_code=503, error_msg="Service unavailable", latency_ms=2000.0)
    assert m.consecutive_failures == 3
    assert m.circuit_state == CircuitState.OPEN
    assert m.status == ModelHealthState.TEMPORARILY_DISABLED
    assert m.is_available_for_traffic() is False
    assert m.calculate_health_score(90) == 0.0

    # 6. Cooldown elapsed -> transitions to HALF_OPEN
    m.circuit_opened_at = time.time() - 65.0  # 65s ago
    assert m.is_available_for_traffic() is True
    assert m.circuit_state == CircuitState.HALF_OPEN

    # 7. Success in HALF_OPEN recovers to CLOSED and HEALTHY
    m.record_probe_success(latency_ms=300.0)
    assert m.circuit_state == CircuitState.CLOSED
    assert m.status == ModelHealthState.HEALTHY


def test_quality_first_scoring_beats_raw_speed():
    """Verify a high-quality model with reasonable latency outranks a low-quality fast model."""
    high_quality_model = {
        "provider_name": "anthropic",
        "model_id": "claude-sonnet-5",
        "base_priority": 95,
        "capabilities": ["reasoning", "structured_output"],
    }
    fast_low_quality_model = {
        "provider_name": "budget",
        "model_id": "nano-fast",
        "base_priority": 30,
        "capabilities": ["fast_text", "structured_output"],
    }

    # Simulate Claude Sonnet responding in 1200ms with 100% success
    health_tracker.record_probe_result("anthropic", "claude-sonnet-5", 200, 1200.0)
    health_tracker.record_success("anthropic", "claude-sonnet-5", 1200.0)

    # Simulate budget model responding in 150ms with 100% success
    health_tracker.record_probe_result("budget", "nano-fast", 200, 150.0)
    health_tracker.record_success("budget", "nano-fast", 150.0)

    ranked = health_tracker.rank_candidates_for_capabilities(
        [high_quality_model, fast_low_quality_model],
        required_capabilities=["reasoning"],
    )

    # High quality model MUST rank first despite being slower
    assert ranked[0]["model_id"] == "claude-sonnet-5"
    assert ranked[0]["composite_score"] > ranked[1]["composite_score"]


def test_stability_damping_prevents_flapping():
    """Verify that a tiny latency difference (+50ms) does not flap Priority #1 model."""
    model_a = {
        "provider_name": "prov_a",
        "model_id": "model-alpha",
        "base_priority": 90,
        "capabilities": ["structured_output"],
    }
    model_b = {
        "provider_name": "prov_b",
        "model_id": "model-beta",
        "base_priority": 90,
        "capabilities": ["structured_output"],
    }

    # Cycle 1: Model A is slightly faster (800ms vs 850ms), becomes #1
    health_tracker.record_probe_result("prov_a", "model-alpha", 200, 800.0)
    health_tracker.record_probe_result("prov_b", "model-beta", 200, 850.0)
    rank1 = health_tracker.rank_candidates_for_capabilities([model_a, model_b], required_capabilities=["structured_output"])
    assert rank1[0]["model_id"] == "model-alpha"

    # Cycle 2: Model B has an isolated slightly lower latency (780ms vs 820ms, diff ~40ms = ~0.04 score points)
    health_tracker.record_probe_result("prov_a", "model-alpha", 200, 820.0)
    health_tracker.record_probe_result("prov_b", "model-beta", 200, 780.0)
    rank2 = health_tracker.rank_candidates_for_capabilities([model_a, model_b], required_capabilities=["structured_output"])

    # Stability rule should prevent flapping: Model A remains Priority #1 because challenger did not beat by threshold (+3.0)
    assert rank2[0]["model_id"] == "model-alpha"

    # Cycle 3: Model A degrades (e.g. rate-limited 429). Now Model B immediately takes over!
    health_tracker.record_probe_result("prov_a", "model-alpha", 429, 820.0, "Rate limited")
    rank3 = health_tracker.rank_candidates_for_capabilities([model_a, model_b], required_capabilities=["structured_output"])
    assert rank3[0]["model_id"] == "model-beta"


def test_schema_validation_penalty():
    """Verify that failing structured output contract heavily penalizes a model's score."""
    model = {
        "provider_name": "prov_test",
        "model_id": "model-json-fail",
        "base_priority": 85,
    }
    # Pass synthetic probe
    health_tracker.record_probe_result("prov_test", "model-json-fail", 200, 400.0)
    score_before = health_tracker.composite_score("prov_test", "model-json-fail", 85)

    # Real production request returns malformed output
    health_tracker.record_schema_validation_failure("prov_test", "model-json-fail", "slide_writer", "Missing slides array")
    score_after = health_tracker.composite_score("prov_test", "model-json-fail", 85)

    assert score_after < score_before
    assert score_before - score_after >= 5.0


def test_distributed_system_lock(db_session: Session):
    """Verify that only one instance acquires the lock and second instance is locked out."""
    lock_name = "test_health_lock"
    inst_1 = "worker-node-1"
    inst_2 = "worker-node-2"

    # 1. Instance 1 acquires
    acq1 = SystemLock.acquire(db_session, lock_name, inst_1, lease_seconds=2)
    assert acq1 is True

    # 2. Instance 2 tries while lease is active -> False
    acq2 = SystemLock.acquire(db_session, lock_name, inst_2, lease_seconds=2)
    assert acq2 is False

    # 3. Instance 1 refreshes its own lock -> True
    refresh1 = SystemLock.acquire(db_session, lock_name, inst_1, lease_seconds=2)
    assert refresh1 is True

    # 4. Instance 1 releases
    SystemLock.release(db_session, lock_name, inst_1)

    # 5. Now Instance 2 can acquire -> True
    acq2_again = SystemLock.acquire(db_session, lock_name, inst_2, lease_seconds=2)
    assert acq2_again is True


def test_execute_health_scan(db_session: Session):
    """Verify that background health prober scans models and updates capability rankings."""
    import asyncio
    from app.services.background_tasks import execute_health_scan
    from app.services.provider_router import ProviderRouter

    ProviderRouter.sync_environment_providers(db_session)

    async def _run():
        async def mock_post(url, *args, **kwargs):
            payload = kwargs.get("json", {})
            model = payload.get("model", "")
            if "timeout" in model:
                raise httpx.TimeoutException("Timeout")
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]}, request=httpx.Request("POST", url))

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await execute_health_scan()

        assert result["scanned"] > 0
        assert result["healthy"] > 0

        overview = health_tracker.get_status_overview()
        assert "capability_rankings" in overview
        assert len(overview["capability_rankings"]) > 0

    asyncio.run(_run())
