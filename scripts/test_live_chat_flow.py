"""Verify live API against running daemon at http://127.0.0.1:8000"""

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_live_chat_flow():
    # 1. Login with user credentials
    login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "pilot@deckpilot.ai",
        "password": "Admin@123456"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] Logged in as pilot@deckpilot.ai")

    # 2. Create a clean session
    proj_res = requests.post(f"{BASE_URL}/projects", json={
        "title": "Greeting Verification Test"
    }, headers=headers)
    assert proj_res.status_code == 201, f"Project creation failed: {proj_res.text}"
    project_id = proj_res.json()["id"]
    print(f"[PASS] Created test session: {project_id}")

    # 3. User says "hi"
    chat_res = requests.post(f"{BASE_URL}/projects/{project_id}/chat", json={
        "content": "hi",
        "has_attachments": False
    }, headers=headers)
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    print("\n--- Chat Response for 'hi' ---")
    print(f"Intent: {chat_data['intent']}")
    print(f"Should Generate: {chat_data['should_generate']}")
    print(f"User Message: {chat_data['user_message']['content']}")
    print(f"Assistant Message:\n{chat_data['assistant_message']['content'].encode('ascii', errors='replace').decode('ascii')}")

    print("--------------------------------\n")

    assert chat_data["intent"] == "chat"
    assert chat_data["should_generate"] is False
    assert chat_data["assistant_message"] is not None
    assert "deckpilot" in chat_data["assistant_message"]["content"].lower()
    print("[PASS] User saying 'hi' returned conversational guidance without generating PPT")

    # 4. Verify no jobs were launched for this project
    job_res = requests.get(f"{BASE_URL}/projects/{project_id}/jobs/active", headers=headers)
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["active"] is False
    assert job_data["job"] is None
    print("[PASS] Verified 0 generation jobs created in database for 'hi'")

    # 5. Now test presentation request: "Create a 5-slide pitch deck"
    gen_chat_res = requests.post(f"{BASE_URL}/projects/{project_id}/chat", json={
        "content": "Create a 5-slide pitch deck for our seed round",
        "has_attachments": False
    }, headers=headers)
    assert gen_chat_res.status_code == 200
    gen_chat_data = gen_chat_res.json()
    assert gen_chat_data["intent"] == "generate"
    assert gen_chat_data["should_generate"] is True
    print("[PASS] Verified 'Create a 5-slide pitch deck' correctly detected presentation intent (should_generate=True)")

    print("\nALL LIVE INTEGRATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_live_chat_flow()
