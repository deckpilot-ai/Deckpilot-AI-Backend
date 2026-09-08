"""Live end-to-end test: upload PDF → generate 22-slide deck on the deployed backend."""
import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "https://deckpilot-ai.duckdns.org/api/v1"
ADMIN_EMAIL = "admin@creatorpilot.ai"
ADMIN_PASSWORD = "Admin@123456"
PDF_PATH = r"c:\DeckPilotAI\source data.pdf"


def api_call(req, retries=6, timeout=45):
    """HTTP call with automatic retry and exponential backoff."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = min(5 * (attempt + 1), 30)
            print(f"  [Retry {attempt+1}/{retries}] HTTP error: {e}, waiting {wait}s...")
            time.sleep(wait)


def cancel_active_job(token: str, project_id: str) -> None:
    """Cancel any active generation job for the project (avoids 409 on retry)."""
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/projects/{project_id}/jobs/active",
            headers={"Authorization": f"Bearer {token}"},
        )
        active = api_call(req, retries=2, timeout=15)
        job_id = active.get("job_id") or active.get("id")
        if job_id and active.get("status") in ("queued", "running"):
            cancel_req = urllib.request.Request(
                f"{BASE_URL}/jobs/{job_id}/cancel",
                data=b"{}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            api_call(cancel_req, retries=2, timeout=15)
            print(f"  Cancelled existing active job {job_id}")
    except Exception as e:
        print(f"  No active job to cancel (or error): {e}")


def main():
    # ────────────────────────────────────────────────
    # 1. Login
    # ────────────────────────────────────────────────
    print("1. Logging in as admin...")
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    login_data = api_call(login_req, retries=8, timeout=30)
    token = login_data["token"]
    print(f"   ✓ Login successful: {login_data.get('user', {}).get('email')}")

    # ────────────────────────────────────────────────
    # 2. Create fresh test project
    # ────────────────────────────────────────────────
    print("2. Creating fresh test project...")
    proj_req = urllib.request.Request(
        f"{BASE_URL}/projects",
        data=json.dumps({"title": f"22-Slide E2E Test {int(time.time())}"}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    project = api_call(proj_req)
    project_id = project["id"]
    print(f"   ✓ Project created: {project_id}")

    # ────────────────────────────────────────────────
    # 3. Upload the PDF
    # ────────────────────────────────────────────────
    print(f"3. Uploading PDF: {PDF_PATH}")
    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()
    print(f"   File size: {len(pdf_bytes) / 1024 / 1024:.2f} MB")

    boundary = f"----E2EBoundary{int(time.time())}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="source data.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()

    upload_req = urllib.request.Request(
        f"{BASE_URL}/projects/{project_id}/attachments",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    t_up0 = time.perf_counter()
    att = api_call(upload_req, retries=3, timeout=90)
    att_id = att["id"]
    print(f"   ✓ Uploaded in {time.perf_counter()-t_up0:.1f}s — attachment: {att_id}, status: {att['status']}")

    # ────────────────────────────────────────────────
    # 4. Wait for background extraction to complete
    #    Large PDFs on Render free tier can take 8-15 minutes
    # ────────────────────────────────────────────────
    print("4. Waiting for background document extraction...")
    print("   (Large PDFs can take 8-15 min on free-tier workers — patience!)")
    max_wait_seconds = 1200  # 20 minutes hard cap
    t_ext_start = time.time()
    poll_interval = 5
    last_status = None
    while time.time() - t_ext_start < max_wait_seconds:
        try:
            get_att_req = urllib.request.Request(
                f"{BASE_URL}/projects/{project_id}/attachments/{att_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            curr_att = api_call(get_att_req, retries=3, timeout=30)
            status = curr_att.get("status")
            if status != last_status:
                elapsed = int(time.time() - t_ext_start)
                print(f"   [{elapsed}s] Attachment status: {status}")
                last_status = status
            if status == "ready":
                print(f"   ✓ Extraction complete in {int(time.time()-t_ext_start)}s!")
                break
            elif status == "failed":
                print("   ✗ Extraction FAILED!")
                sys.exit(1)
        except Exception as e:
            print(f"   Polling error: {e}")
        time.sleep(poll_interval)
    else:
        print(f"   ✗ Extraction did not complete within {max_wait_seconds}s — proceeding anyway (partial grounding).")

    # ────────────────────────────────────────────────
    # 5. Create 22-slide generation job
    # ────────────────────────────────────────────────
    print("5. Creating 22-slide generation job...")
    job_id = None
    for attempt in range(10):
        try:
            job_req = urllib.request.Request(
                f"{BASE_URL}/projects/{project_id}/jobs",
                data=json.dumps({
                    "prompt": (
                        "Create a comprehensive, high-quality, well-formatted 22-slide executive presentation "
                        "based on the uploaded document. Use professional design, executive language, detailed "
                        "bullet points, metrics, and a compelling narrative arc. Include a title slide, agenda, "
                        "key chapters with evidence, metrics slides, visuals, and a strong closing CTA."
                    ),
                    "mode": "generate",
                    "background": True,
                }).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            job = api_call(job_req, retries=4, timeout=30)
            job_id = job.get("job_id")
            print(f"   ✓ Started job: {job_id} (status: {job.get('status')})")
            break
        except urllib.error.HTTPError as e:
            if e.code == 409:
                print(f"   409 Conflict — cancelling existing active job and retrying...")
                cancel_active_job(token, project_id)
                time.sleep(5)
            elif e.code == 502:
                wait = min(10 * (attempt + 1), 60)
                print(f"   502 Bad Gateway — waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"   Job creation attempt {attempt+1}/10 failed: {e}")
                time.sleep(min(5 * (attempt + 1), 30))
        except Exception as e:
            print(f"   Job creation attempt {attempt+1}/10 failed: {e}")
            time.sleep(min(5 * (attempt + 1), 30))
    else:
        print("   ✗ Failed to create generation job after 10 attempts. Exiting.")
        sys.exit(1)

    # ────────────────────────────────────────────────
    # 6. Monitor job progression
    # ────────────────────────────────────────────────
    print("6. Monitoring live multi-agent DAG execution...")
    t0 = time.time()
    last_tasks_str = None
    consecutive_errors = 0
    while time.time() - t0 < 900:  # 15-minute hard cap
        time.sleep(5)
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                detail = json.loads(resp.read().decode())
            consecutive_errors = 0

            tasks = detail.get("tasks", [])
            tasks_str = " | ".join(f"{t['agent_type']}={t['status']}" for t in tasks)
            if tasks_str != last_tasks_str:
                elapsed = int(time.time() - t0)
                print(f"   [{elapsed}s] {detail.get('status')} | {tasks_str}")
                last_tasks_str = tasks_str

            job_status = detail.get("status")
            if job_status in ("completed", "permanently_failed", "cancelled"):
                print(f"\n   Final Job Status: {job_status}")
                if job_status == "completed":
                    print("   ✓ SUCCESS! 22-slide deck generated and rendered into PPTX!")
                    # Fetch deck version details
                    try:
                        req2 = urllib.request.Request(
                            f"{BASE_URL}/projects/{project_id}/decks/versions/1",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        with urllib.request.urlopen(req2, timeout=20) as vresp:
                            vdata = json.loads(vresp.read().decode())
                        spec = vdata.get("spec", {})
                        slides = spec.get("slides", [])
                        print(f"   Presentation Title: {spec.get('deckTitle')}")
                        print(f"   Total Slides: {len(slides)}")
                        print(f"   Download URL: {BASE_URL}/projects/{project_id}/decks/versions/1/download")
                        # Print slide titles for verification
                        for i, s in enumerate(slides[:5], 1):
                            title = s.get("title") or s.get("topic") or s.get("message") or "—"
                            print(f"     Slide {i}: {title}")
                        if len(slides) > 5:
                            print(f"     ... and {len(slides)-5} more slides")
                    except Exception as e:
                        print(f"   Note: error fetching deck detail: {e}")
                else:
                    print(f"   ✗ Job FAILED. Details:")
                    for t in detail.get("tasks", []):
                        if t.get("status") == "failed":
                            print(f"      - {t['agent_type']}: {t.get('error_code', 'no error code')}")
                break
        except Exception as e:
            consecutive_errors += 1
            print(f"   Polling error ({consecutive_errors}): {e}")
            if consecutive_errors > 12:
                print("   Too many polling errors — aborting.")
                break


if __name__ == "__main__":
    main()
