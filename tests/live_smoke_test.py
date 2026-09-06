import json
import urllib.request


def run_smoke():
    # 1. Health
    h = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health").read())
    print("1. Health check:", h)

    # 2. Register
    email = f"founder_{id(h)}@deckpilot.ai"
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/register",
        data=json.dumps({"email": email, "password": "Password123!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    reg = json.loads(urllib.request.urlopen(req).read())
    print("2. Register:", reg["email"], "id:", reg["id"])

    # 3. Login
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data=json.dumps({"email": email, "password": "Password123!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    login = json.loads(urllib.request.urlopen(req).read())
    token = login["token"]
    auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("3. Login OK, token length:", len(token))

    # 4. Create Project
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/projects",
        data=json.dumps({"title": "Series A Investment Pitch"}).encode("utf-8"),
        headers=auth_headers
    )
    proj = json.loads(urllib.request.urlopen(req).read())
    proj_id = proj["id"]
    print("4. Project created:", proj["title"], "id:", proj_id)

    # 5. Post Message
    req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/v1/projects/{proj_id}/messages",
        data=json.dumps({"content": "Build a 4-slide Series A pitch deck with market traction.", "role": "user"}).encode("utf-8"),
        headers=auth_headers
    )
    msg = json.loads(urllib.request.urlopen(req).read())
    print("5. Message posted:", msg["content"])

    # 6. Start Generation Job
    req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/v1/projects/{proj_id}/jobs",
        data=json.dumps({"prompt": "Build a 4-slide Series A pitch deck with market traction.", "mode": "generate"}).encode("utf-8"),
        headers=auth_headers
    )
    job = json.loads(urllib.request.urlopen(req).read())
    print("6. Generation Job status:", job["status"], "job_id:", job["job_id"])

    # 7. Check Job Tasks
    req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/jobs/{job['job_id']}", headers=auth_headers)
    job_detail = json.loads(urllib.request.urlopen(req).read())
    completed = [t for t in job_detail["tasks"] if t["status"] == "completed"]
    print(f"7. Tasks completed: {len(completed)} of {len(job_detail['tasks'])}")

    # 8. Download PPTX
    req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/projects/{proj_id}/decks/1/download", headers=auth_headers)
    pptx_data = urllib.request.urlopen(req).read()
    print(f"8. PPTX downloaded! Size: {len(pptx_data)} bytes, ZIP signature: {pptx_data[:4]}")
    assert pptx_data[:4] == b"PK\x03\x04", "Invalid PPTX file signature!"
    print("=== ALL PHASES LIVE SMOKE TEST PASSED ===")

if __name__ == "__main__":
    run_smoke()
