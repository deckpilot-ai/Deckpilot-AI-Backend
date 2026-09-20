"""Tests for Dual-Track Chain-of-Thought AI Chat and SSE streaming."""

import json
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.message import Message
from app.services.prompts import DUAL_TRACK_COT_SYSTEM_PROMPT


def test_dual_track_system_prompt_rules():
    """Verify that DUAL_TRACK_COT_SYSTEM_PROMPT contains the required 3 tiers and XML tags."""
    assert "<thinking>" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "</thinking>" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "<answer>" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "</answer>" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "TIER 1: TRIVIAL & CASUAL" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "TIER 2: INTERMEDIATE" in DUAL_TRACK_COT_SYSTEM_PROMPT
    assert "TIER 3: COMPLEX & DEEP WORK" in DUAL_TRACK_COT_SYSTEM_PROMPT


def test_dual_track_tag_parsing():
    """Verify tag extraction logic for dual-track messages."""
    raw_message = (
        "<thinking>\n"
        "1. Direct user inquiry regarding SQL vs NoSQL.\n"
        "2. Structure comparison by schema, scalability, and ACID.\n"
        "</thinking>\n\n"
        "<answer>\n"
        "### SQL vs NoSQL\n\n"
        "- **SQL**: Relational, fixed schema, ACID compliant.\n"
        "- **NoSQL**: Non-relational, dynamic schema, horizontal scaling.\n"
        "</answer>"
    )

    assert raw_message.startswith("<thinking>")
    assert "</thinking>" in raw_message
    thinking_part = raw_message.split("</thinking>")[0].replace("<thinking>", "").strip()
    answer_part = raw_message.split("</thinking>")[1].replace("<answer>", "").replace("</answer>", "").strip()

    assert "SQL vs NoSQL" in thinking_part
    assert "### SQL vs NoSQL" in answer_part


def test_chat_stream_endpoint_requires_auth():
    """Verify that unauthenticated streaming chat returns 401."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/projects/proj-123/chat/stream",
        json={"content": "Hello", "mode": "ask"},
    )
    assert resp.status_code in (401, 403)
