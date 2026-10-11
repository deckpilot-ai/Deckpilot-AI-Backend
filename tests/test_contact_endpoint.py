"""Test suite for the contact endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_contact_submission_valid():
    response = client.post(
        "/api/v1/contact",
        json={
            "full_name": "Dr. Sarah Lin",
            "email": "sarah.lin@example.com",
            "company": "Enterprise Advisory Partner",
            "inquiry_type": "partnership",
            "message": "We are interested in evaluating DeckPilotAI presentation capabilities for enterprise teams.",
            "honeypot": "",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "received" in data["message"].lower()


def test_contact_submission_honeypot_bot():
    response = client.post(
        "/api/v1/contact",
        json={
            "full_name": "Spam Bot",
            "email": "bot@spammer.com",
            "company": "Spam Co",
            "inquiry_type": "general",
            "message": "Click this spam link now http://example.com/spam",
            "honeypot": "http://spambot.com",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_contact_submission_invalid_email():
    response = client.post(
        "/api/v1/contact",
        json={
            "full_name": "Alex Smith",
            "email": "not-an-email",
            "company": "Tech Corp",
            "inquiry_type": "general",
            "message": "Valid length message for testing.",
            "honeypot": "",
        },
    )
    assert response.status_code == 422


def test_contact_submission_short_message():
    response = client.post(
        "/api/v1/contact",
        json={
            "full_name": "Alex Smith",
            "email": "alex@example.com",
            "company": "Tech Corp",
            "inquiry_type": "general",
            "message": "short",
            "honeypot": "",
        },
    )
    assert response.status_code == 422
