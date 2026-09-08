import urllib.request
import json
import time
import sys

def api_call(req, retries=5, timeout=30):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  [Retry {attempt+1}/{retries}] HTTP error: {e}, waiting 5s...")
            time.sleep(5)

def main():
    print("1. Logging in as admin...")
    login_req = urllib.request.Request(
        'https://deckpilot-ai-backend.onrender.com/api/v1/auth/login',
        data=json.dumps({'email': 'admin@creatorpilot.ai', 'password': 'Admin@123456'}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    login_data = api_call(login_req, retries=8)
    token = login_data['token']
    print(f"Login successful! User: {login_data.get('user', {}).get('email')}")

    # 2. Create fresh test project
    print("2. Creating test project...")
    proj_req = urllib.request.Request(
        'https://deckpilot-ai-backend.onrender.com/api/v1/projects',
        data=json.dumps({'title': '22-Slide E2E Live Test'}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    project = api_call(proj_req)
    project_id = project['id']
    print(f"Created test project: {project_id}")

    # 3. Upload source data.pdf
    print("3. Uploading source data.pdf (8.5 MB)...")
    with open(r'c:\DeckPilotAI\source data.pdf', 'rb') as f:
        pdf_bytes = f.read()

    boundary = f'----E2EBoundary{int(time.time())}'
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="source data.pdf"\r\n'
        f'Content-Type: application/pdf\r\n\r\n'
    ).encode() + pdf_bytes + f'\r\n--{boundary}--\r\n'.encode()

    upload_req = urllib.request.Request(
        f'https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/attachments',
        data=body,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST'
    )
    t_up0 = time.perf_counter()
    att = api_call(upload_req, timeout=60)
    print(f"Uploaded PDF in {time.perf_counter()-t_up0:.1f}s! Attachment ID: {att['id']}, status: {att['status']}")

    # 4. Trigger 22-slide presentation generation
    print("4. Starting 22-slide presentation generation job...")
    job_req = urllib.request.Request(
        f'https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/jobs',
        data=json.dumps({
            'prompt': 'Create a comprehensive 22-slide high quality deck presentation based on the uploaded document.',
            'mode': 'generate',
            'background': True
        }).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    job = api_call(job_req)
    job_id = job.get('job_id')
    print(f"Started generation job {job_id}, status: {job.get('status')}")

    # 5. Monitor job progression
    print("5. Monitoring live multi-agent DAG execution...")
    t0 = time.time()
    last_tasks_str = None
    while time.time() - t0 < 600:
        time.sleep(5)
        try:
            req = urllib.request.Request(
                f'https://deckpilot-ai-backend.onrender.com/api/v1/jobs/{job_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                detail = json.loads(resp.read().decode())
            tasks = detail.get('tasks', [])
            tasks_str = ' | '.join(f"{t['agent_type']}={t['status']}" for t in tasks)
            if tasks_str != last_tasks_str:
                last_tasks_str = tasks_str
                print(f"[{int(time.time()-t0)}s] Job status: {detail.get('status')} | Tasks: {tasks_str}")
            
            if detail.get('status') in ('completed', 'permanently_failed', 'cancelled'):
                print(f"\nFinal Job Status: {detail.get('status')}")
                if detail.get('status') == 'completed':
                    print("SUCCESS! 22-slide deck presentation generated and rendered into PPTX!")
                    # Check deck version
                    req2 = urllib.request.Request(
                        f'https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/decks/versions/1',
                        headers={'Authorization': f'Bearer {token}'}
                    )
                    try:
                        with urllib.request.urlopen(req2, timeout=15) as vresp:
                            vdata = json.loads(vresp.read().decode())
                            spec = vdata.get('spec', {})
                            slides = spec.get('slides', [])
                            print(f"Presentation Title: {spec.get('deckTitle')}")
                            print(f"Total Slides Generated: {len(slides)}")
                            print(f"Download PPTX URL: https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/decks/versions/1/download")
                    except Exception as e:
                        print(f"Note fetching deck version: {e}")
                else:
                    print("Job failed with detail:", detail)
                break
        except Exception as e:
            print(f"Polling warning at {int(time.time()-t0)}s: {e}")

if __name__ == '__main__':
    main()
