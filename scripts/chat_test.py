import time
import httpx
from pathlib import Path

BASE = "http://localhost:8000/api/v1"
EMAIL = "analyst@demo.local"
PASSWORD = "DemoAnalyst2024!"
APPLE_PDF = Path("data/documents/apple_fy2025_form_10k.pdf")

QUESTIONS = [
    "What file formats are supported?",
    "What is the maximum file size?",
    "Explain the processing flow.",
    "What was revenue?",
    "Forecast revenue for next 2 periods",
]

client = httpx.Client(base_url=BASE, timeout=120.0)

# Login
r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
print("LOGIN", r.status_code, r.text[:200])
r.raise_for_status()

# Create workspace
ws = client.post("/workspaces", json={"name": "chat-test-apple", "description": "chat test"})
print("WS CREATE", ws.status_code, ws.text[:200])
ws.raise_for_status()
workspace_id = ws.json()["id"]
print("workspace_id", workspace_id)

# Upload Apple PDF
with APPLE_PDF.open("rb") as f:
    files = {"file": (APPLE_PDF.name, f, "application/pdf")}
    data = {"company_name": "Apple Inc.", "document_type": "10-K", "fiscal_period": "FY2025"}
    up = client.post(f"/workspaces/{workspace_id}/documents", files=files, data=data)
print("UPLOAD", up.status_code, up.text[:300])
up.raise_for_status()
upj = up.json()
doc_id = upj["document_id"]
print("doc_id", doc_id, upj.get("processing_status"))

# Poll until completed/failed
deadline = time.time() + 300
status = upj.get("processing_status")
while status not in ("completed", "failed") and time.time() < deadline:
    time.sleep(3)
    d = client.get(f"/documents/{doc_id}")
    d.raise_for_status()
    dj = d.json()
    status = dj.get("processing_status")
    stage = dj.get("processing_stage")
    print("POLL", status, stage)
if status not in ("completed", "failed"):
    print("TIMEOUT waiting for processing")

results = []
for q in QUESTIONS:
    try:
        rr = client.post(f"/workspaces/{workspace_id}/research", json={"question": q})
        print("RESEARCH", q, rr.status_code)
        if rr.status_code >= 400:
            ans = f"ERROR {rr.status_code}: {rr.text[:500]}"
        else:
            j = rr.json()
            ans = (j.get("answer") or j.get("final_answer") or j.get("summary") or j.get("text")
                   or j.get("response") or str(j))
    except Exception as e:
        ans = f"EXCEPTION: {e}"
    trunc = ans[:800]
    results.append((q, trunc, ans))
    print("ANSWER:", trunc[:300].replace("\n", " "))

# Write markdown
out = Path("docs/chat_test.md")
lines = ["# Chat Test Results", "", f"Workspace: `{workspace_id}`", f"Document: Apple FY2025 10-K (`{doc_id}`), status: `{status}`", ""]
for q, trunc, full in results:
    lines.append(f"## Q: {q}")
    lines.append("")
    lines.append("```")
    lines.append(trunc)
    lines.append("```")
    lines.append("")
out.write_text("\n".join(lines), encoding="utf-8")
print("WROTE", out)
client.close()
