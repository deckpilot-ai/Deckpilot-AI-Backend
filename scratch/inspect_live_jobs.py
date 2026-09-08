import urllib.request
import json
import traceback

def main():
    try:
        # Login as admin
        req = urllib.request.Request(
            'https://deckpilot-ai.duckdns.org/api/v1/auth/login',
            data=json.dumps({'email': 'admin@creatorpilot.ai', 'password': 'Admin@123456'}).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as resp:
            token = json.loads(resp.read().decode())['token']

        # Get projects
        req = urllib.request.Request(
            'https://deckpilot-ai.duckdns.org/api/v1/projects',
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(req) as resp:
            projects = json.loads(resp.read().decode())
        
        for p in projects[:3]:
            pid = p['id']
            print(f"\n==========================================")
            print(f"Project: {pid} | Title: {p.get('title')}")
            
            # Get active job
            req = urllib.request.Request(
                f'https://deckpilot-ai.duckdns.org/api/v1/projects/{pid}/jobs/active',
                headers={'Authorization': f'Bearer {token}'}
            )
            try:
                with urllib.request.urlopen(req) as jresp:
                    jdata = json.loads(jresp.read().decode())
                    job = jdata.get('job')
                    if job:
                        jid = job['id']
                        print(f"  Latest Job: {jid} | Status: {job.get('status')}")
                        # Fetch full job
                        req2 = urllib.request.Request(
                            f'https://deckpilot-ai.duckdns.org/api/v1/jobs/{jid}',
                            headers={'Authorization': f'Bearer {token}'}
                        )
                        with urllib.request.urlopen(req2) as jdresp:
                            jdetail = json.loads(jdresp.read().decode())
                            print("  Tasks detail:")
                            for t in jdetail.get('tasks', []):
                                print(f"    - [{t.get('status')}] {t.get('agent_type')}: error='{t.get('error_message')}' payload={str(t.get('output_payload', ''))[:150]}")
            except Exception as e:
                print(f"  Error fetching active job: {e}")

            # Get attachments
            req = urllib.request.Request(
                f'https://deckpilot-ai.duckdns.org/api/v1/projects/{pid}/attachments',
                headers={'Authorization': f'Bearer {token}'}
            )
            try:
                with urllib.request.urlopen(req) as aresp:
                    attachments = json.loads(aresp.read().decode())
                    print(f"  Attachments count: {len(attachments)}")
                    for att in attachments:
                        print(f"    Attachment: {att.get('id')} | filename={att.get('filename')} | status={att.get('status')} | error={att.get('error_message')}")
            except Exception as e:
                print(f"  Error fetching attachments: {e}")

            # Get messages
            req = urllib.request.Request(
                f'https://deckpilot-ai.duckdns.org/api/v1/projects/{pid}/messages',
                headers={'Authorization': f'Bearer {token}'}
            )
            try:
                with urllib.request.urlopen(req) as mresp:
                    messages = json.loads(mresp.read().decode())
                    print(f"  Messages count: {len(messages)}")
                    for m in messages[-3:]:
                        print(f"    Msg [{m.get('role')}]: {str(m.get('content'))[:200]}")
            except Exception as e:
                print(f"  Error fetching messages: {e}")

    except Exception as e:
        traceback.print_exc()

if __name__ == '__main__':
    main()
