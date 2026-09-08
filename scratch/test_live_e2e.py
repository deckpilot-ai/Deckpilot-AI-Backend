import urllib.request
import json
import time
import sys

def main():
    # 1. Login
    req = urllib.request.Request(
        'https://deckpilot-ai-backend.onrender.com/api/v1/auth/login',
        data=json.dumps({'email': 'admin@creatorpilot.ai', 'password': 'Admin@123456'}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode())['token']
    print('Login successful!')

    # 2. Create fresh test project
    req = urllib.request.Request(
        'https://deckpilot-ai-backend.onrender.com/api/v1/projects',
        data=json.dumps({'title': '22-Slide E2E Live Test'}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        project = json.loads(resp.read().decode())
    project_id = project['id']
    print(f'Created test project {project_id}')

    # 3. Upload source data.pdf
    with open(r'c:\DeckPilotAI\source data.pdf', 'rb') as f:
        pdf_bytes = f.read()

    boundary = f'----E2EBoundary{int(time.time())}'
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="source data.pdf"\r\n'
        f'Content-Type: application/pdf\r\n\r\n'
    ).encode() + pdf_bytes + f'\r\n--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        f'https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/attachments',
        data=body,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST'
    )
    t_up0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        att = json.loads(resp.read().decode())
    print(f'Uploaded PDF in {time.perf_counter()-t_up0:.1f}s! Attachment ID: {att["id"]}, status: {att["status"]}')

    # 4. Trigger 22-slide presentation generation
    req = urllib.request.Request(
        f'https://deckpilot-ai-backend.onrender.com/api/v1/projects/{project_id}/jobs',
        data=json.dumps({
            'prompt': 'Create a comprehensive 22-slide high quality deck presentation based on the uploaded document.',
            'mode': 'generate',
            'background': True
        }).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        job = json.loads(resp.read().decode())
    job_id = job.get('job_id')
    print(f'Started generation job {job_id} status: {job.get("status")}')

    # 5. Monitor job progression
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
                print(f'[{int(time.time()-t0)}s] Job status: {detail.get("status")} | Tasks: {tasks_str}')
            
            if detail.get('status') in ('completed', 'permanently_failed', 'cancelled'):
                print(f'\nFinal Job Status: {detail.get("status")}')
                if detail.get('status') == 'completed':
                    print('SUCCESS! Deck generation completed!')
                else:
                    print('Job failed with detail:', detail)
                break
        except Exception as e:
            print(f'Polling error at {int(time.time()-t0)}s: {e}')

if __name__ == '__main__':
    main()
