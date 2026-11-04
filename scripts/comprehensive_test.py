"""Comprehensive overall project test – covers all major API flows.

This test file runs against the **live** backend server
(``http://localhost:8000/api/v1``).  It:

* Authenticates (register + login).
* Uploads multiple PDF documents from data/documents/.
* Waits for processing to complete.
* Exercises: search, research, red-flag analysis, forecasting, export (CSV/JSON),
  AND the new chatbot endpoint with document questions AND project questions.
* Writes a detailed Markdown report and captures metrics to the var/e2e/ folder.

Run:
    python scripts/comprehensive_test.py

or:
    python scripts/comprehensive_test.py <pdf_path> [<report_suffix>]
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://localhost:8000/api/v1"
OUT_DIR = ROOT / "var" / "e2e"
DOCS_DIR = ROOT / "data" / "documents"

CHATBOT_DOCUMENT_QUESTIONS = [
    "What was the total revenue reported in this document?",
    "Did the company report a profit or a loss? What were the figures?",
    "What are the key risks and red flags mentioned?",
    "What does management say about future growth outlook or forecasts?",
    "What is the gross margin and how has it changed year-over-year?",
    "Are there any going-concern disclosures or auditor warnings?",
    "What market rate or pricing information is disclosed?",
    "What are the main operating expenses?",
    "How did revenue change compared to the previous year?",
]

CHATBOT_PROJECT_QUESTIONS = [
    "How do I upload a document?",
    "What file formats are supported?",
    "What is the maximum file size limit?",
    "What is a workspace?",
    "How does the semantic search work?",
    "What are red flags in this system?",
    "How does forecasting work?",
    "Can I export data as CSV?",
    "Where is the API documentation?",
]


def _resolve_pdfs() -> list[Path]:
    pdfs = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF found in {DOCS_DIR}")
    return pdfs


def _resolve_report_path(suffix: str | None) -> Path:
    suffix = (suffix or "").strip()
    if not suffix:
        return ROOT / "docs" / "e2e_comprehensive_report.md"
    safe = suffix.replace(" ", "_")
    return ROOT / "docs" / f"e2e_{safe}.md"


def safe_json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except Exception:
        return {"text": response.text[:500]}


def trunc(obj, limit: int = 3000) -> str:
    text = json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return text


def step_ok(step: dict) -> bool:
    code = step.get("status_code", 0)
    return 200 <= code < 300


def main() -> None:
    report_suffix = sys.argv[1] if len(sys.argv) > 1 else None
    report_path = _resolve_report_path(report_suffix)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)

    all_pdfs = _resolve_pdfs()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    report: dict = {
        "base_url": BASE_URL,
        "started_at": started,
        "steps": [],
        "artifacts": [],
        "chatbot_qa": [],
        "summary": {},
    }

    total_steps = 0
    passed_steps = 0

    def add_step(
        name: str,
        method: str,
        path: str,
        response: httpx.Response | None = None,
        elapsed: float | None = None,
        error: Exception | None = None,
        body_override: dict | None = None,
    ) -> dict:
        nonlocal total_steps, passed_steps
        entry: dict = {
            "name": name,
            "method": method,
            "path": path,
            "elapsed_ms": round(elapsed * 1000, 2) if elapsed else None,
        }
        if response is not None:
            entry["status_code"] = response.status_code
            if body_override is None:
                entry["response"] = safe_json(response)
            else:
                entry["response"] = body_override
        if error is not None:
            entry["error"] = str(error)
        report["steps"].append(entry)
        total_steps += 1
        if step_ok(entry):
            passed_steps += 1
        icon = "✅" if step_ok(entry) else "❌"
        print(f"  {icon} {name}: {entry.get('status_code', 'ERR')} ({entry.get('elapsed_ms')} ms)")
        return entry

    with httpx.Client(base_url=BASE_URL, timeout=600.0) as client:

        # ------------------------------------------------------------------ #
        # 1. Auth
        # ------------------------------------------------------------------ #
        print("\n=== Auth ===")
        email = f"e2e_{uuid.uuid4().hex[:10]}@example.com"
        password = "E2eTestPassword123!"

        t0 = time.perf_counter()
        try:
            r = client.post("/auth/register", json={"email": email, "full_name": "E2E Test User", "password": password})
            add_step("register", "POST", "/auth/register", r, time.perf_counter() - t0)
        except Exception as exc:
            add_step("register", "POST", "/auth/register", None, time.perf_counter() - t0, error=exc)
            raise

        t0 = time.perf_counter()
        r = client.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        add_step("login", "POST", "/auth/login", r, time.perf_counter() - t0)

        # ------------------------------------------------------------------ #
        # 2. Create workspace
        # ------------------------------------------------------------------ #
        print("\n=== Workspace ===")
        t0 = time.perf_counter()
        r = client.post("/workspaces", json={"name": "Comprehensive E2E Test"})
        r.raise_for_status()
        add_step("create_workspace", "POST", "/workspaces", r, time.perf_counter() - t0)
        ws_id = r.json()["id"]
        print(f"  Workspace: {ws_id}")

        # ------------------------------------------------------------------ #
        # 3. Upload documents
        # ------------------------------------------------------------------ #
        print("\n=== Document Upload ===")
        uploaded_docs: list[dict] = []

        for pdf_path in all_pdfs[:3]:  # Test with up to 3 docs
            print(f"  Uploading: {pdf_path.name} ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")
            t0 = time.perf_counter()
            try:
                with open(pdf_path, "rb") as f:
                    r = client.post(
                        f"/workspaces/{ws_id}/documents",
                        files={"file": (pdf_path.name, f, "application/pdf")},
                    )
                elapsed = time.perf_counter() - t0
                r.raise_for_status()
                entry = add_step(f"upload_{pdf_path.stem}", "POST", f"/workspaces/{ws_id}/documents", r, elapsed)
                uploaded_docs.append({"id": r.json()["document_id"], "name": pdf_path.name})
            except Exception as exc:
                add_step(f"upload_{pdf_path.stem}", "POST", f"/workspaces/{ws_id}/documents", None,
                         time.perf_counter() - t0, error=exc)
                print(f"    ⚠ Upload failed: {exc}")

        # ------------------------------------------------------------------ #
        # 4. Poll document processing status
        # ------------------------------------------------------------------ #
        print("\n=== Processing Status Poll ===")
        completed_docs: list[dict] = []
        for doc in uploaded_docs:
            doc_id = doc["id"]
            print(f"  Polling: {doc['name']} ({doc_id})")
            t0 = time.perf_counter()
            final_status = "unknown"
            deadline = time.time() + 600
            last_resp = None
            while time.time() < deadline:
                last_resp = client.get(f"/documents/{doc_id}")
                body = safe_json(last_resp)
                final_status = body.get("processing_status", "unknown")
                if final_status in ("completed", "failed"):
                    break
                time.sleep(3)
                print(f"    Status: {final_status} …", end="\r")
            elapsed = time.perf_counter() - t0
            add_step(f"poll_{doc['name'][:20]}", "GET", f"/documents/{doc_id}", last_resp, elapsed)
            print(f"  → Final status: {final_status} ({elapsed:.1f}s)")
            if final_status == "completed":
                completed_docs.append(doc)

        if not completed_docs:
            print("\n⚠ No documents completed processing – skipping analysis steps.")

        doc_id = completed_docs[0]["id"] if completed_docs else None

        # ------------------------------------------------------------------ #
        # 5. List documents
        # ------------------------------------------------------------------ #
        print("\n=== Document Listing ===")
        t0 = time.perf_counter()
        r = client.get(f"/workspaces/{ws_id}/documents")
        add_step("list_documents", "GET", f"/workspaces/{ws_id}/documents", r, time.perf_counter() - t0)

        # ------------------------------------------------------------------ #
        # 6. Search
        # ------------------------------------------------------------------ #
        print("\n=== Search ===")
        for query in ["revenue", "net income", "risk factors", "market rate"]:
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/search", json={"query": query, "limit": 5})
            add_step(f"search_{query.replace(' ', '_')}", "POST", f"/workspaces/{ws_id}/search", r,
                     time.perf_counter() - t0)
            if r.status_code == 200:
                hits = r.json().get("total", 0)
                print(f"  '{query}': {hits} hits")

        # ------------------------------------------------------------------ #
        # 7. Red flag analysis
        # ------------------------------------------------------------------ #
        print("\n=== Red Flag Analysis ===")
        if doc_id:
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/red-flags/analyze", params={"document_id": doc_id})
            add_step("red_flag_analysis", "POST", f"/workspaces/{ws_id}/red-flags/analyze", r,
                     time.perf_counter() - t0)

        # ------------------------------------------------------------------ #
        # 8. Research questions
        # ------------------------------------------------------------------ #
        print("\n=== Research Agent ===")
        for question in [
            "What was revenue and how did it change?",
            "What are the main financial risks?",
        ]:
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/research", json={"question": question})
            add_step(f"research_{question[:30].replace(' ', '_')}", "POST",
                     f"/workspaces/{ws_id}/research", r, time.perf_counter() - t0)

        # ------------------------------------------------------------------ #
        # 9. Forecasting
        # ------------------------------------------------------------------ #
        print("\n=== Forecasting ===")
        obs = [
            {"period": "2022", "value": 100},
            {"period": "2023", "value": 120},
            {"period": "2024", "value": 145},
        ]
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/forecasts",
                        json={"observations": obs, "horizon": 3, "method": "linear"})
        add_step("forecast_linear", "POST", f"/workspaces/{ws_id}/forecasts", r, time.perf_counter() - t0)

        # ------------------------------------------------------------------ #
        # 10. Exports
        # ------------------------------------------------------------------ #
        print("\n=== Exports ===")
        for fmt in ("csv", "json"):
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/exports", json={"format": fmt, "data_type": "metrics"})
            elapsed = time.perf_counter() - t0
            out_file = OUT_DIR / f"e2e_metrics.{fmt}"
            out_file.write_bytes(r.content)
            add_step(f"export_{fmt}", "POST", f"/workspaces/{ws_id}/exports", r, elapsed,
                     body_override={"saved_to": str(out_file), "bytes": len(r.content),
                                    "content_type": r.headers.get("content-type")})
            report["artifacts"].append(str(out_file))

        # ------------------------------------------------------------------ #
        # 11. Chatbot – document Q&A
        # ------------------------------------------------------------------ #
        print("\n=== Chatbot – Document Questions ===")
        history: list[dict] = []
        for question in CHATBOT_DOCUMENT_QUESTIONS:
            t0 = time.perf_counter()
            payload: dict = {"question": question, "history": history, "top_k": 5}
            r = client.post(f"/workspaces/{ws_id}/chat", json=payload)
            elapsed = time.perf_counter() - t0
            add_step(f"chat_doc_{question[:30].replace(' ', '_')}", "POST",
                     f"/workspaces/{ws_id}/chat", r, elapsed)

            if r.status_code == 200:
                body = r.json()
                answer = body.get("answer", "")
                sources = body.get("sources", [])
                qa_entry = {
                    "question": question,
                    "answer": answer[:600],
                    "source_count": len(sources),
                    "took_ms": body.get("took_ms"),
                }
                report["chatbot_qa"].append(qa_entry)
                # Update history for follow-up
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer[:300]})
                print(f"  ✅ '{question[:50]}' → {len(sources)} sources, {body.get('took_ms'):.0f}ms")
            else:
                print(f"  ❌ '{question[:50]}' → {r.status_code}")

        # ------------------------------------------------------------------ #
        # 12. Chatbot – project Q&A
        # ------------------------------------------------------------------ #
        print("\n=== Chatbot – Project Questions ===")
        for question in CHATBOT_PROJECT_QUESTIONS:
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/chat", json={"question": question, "top_k": 3})
            elapsed = time.perf_counter() - t0
            add_step(f"chat_proj_{question[:30].replace(' ', '_')}", "POST",
                     f"/workspaces/{ws_id}/chat", r, elapsed)

            if r.status_code == 200:
                body = r.json()
                qa_entry = {
                    "question": question,
                    "answer": body.get("answer", "")[:400],
                    "source_count": body.get("source_count", 0),
                    "took_ms": body.get("took_ms"),
                }
                report["chatbot_qa"].append(qa_entry)
                print(f"  ✅ '{question[:50]}' → {body.get('took_ms'):.0f}ms (project answer)")
            else:
                print(f"  ❌ '{question[:50]}' → {r.status_code}")

        # ------------------------------------------------------------------ #
        # 13. Health check
        # ------------------------------------------------------------------ #
        print("\n=== Health ===")
        t0 = time.perf_counter()
        r = client.get("/health")
        add_step("health", "GET", "/health", r, time.perf_counter() - t0)

    # ---------------------------------------------------------------------- #
    # Build report
    # ---------------------------------------------------------------------- #
    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["summary"] = {
        "total_steps": total_steps,
        "passed_steps": passed_steps,
        "failed_steps": total_steps - passed_steps,
        "pass_rate": f"{100 * passed_steps / max(total_steps, 1):.1f}%",
        "uploaded_docs": len(uploaded_docs),
        "completed_docs": len(completed_docs),
        "chatbot_qa_count": len(report["chatbot_qa"]),
        "finished_at": finished,
    }

    lines: list[str] = []
    lines.append("# 📊 Comprehensive E2E Test Report")
    lines.append("")
    lines.append(f"> **Started**: {started}  **Finished**: {finished}")
    lines.append(f"> **API**: {BASE_URL}")
    lines.append(f"> **User**: {email}")
    lines.append(f"> **Workspace**: {ws_id}")
    lines.append("")

    # Summary table
    s = report["summary"]
    lines.append("## ✅ Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Steps | {s['total_steps']} |")
    lines.append(f"| Passed | {s['passed_steps']} |")
    lines.append(f"| Failed | {s['failed_steps']} |")
    lines.append(f"| Pass Rate | {s['pass_rate']} |")
    lines.append(f"| Documents Uploaded | {s['uploaded_docs']} |")
    lines.append(f"| Documents Completed | {s['completed_docs']} |")
    lines.append(f"| Chatbot Q&A Pairs | {s['chatbot_qa_count']} |")
    lines.append("")

    # API Steps
    lines.append("## 🔗 API Steps")
    lines.append("")
    for step in report["steps"]:
        icon = "✅" if step_ok(step) else "❌"
        lines.append(f"### {icon} {step['name']}")
        lines.append("")
        lines.append(f"- **Method**: `{step['method']}`")
        lines.append(f"- **Path**: `{step['path']}`")
        lines.append(f"- **Elapsed**: {step.get('elapsed_ms')} ms")
        lines.append(f"- **Status**: {step.get('status_code', 'N/A')}")
        if step.get("error"):
            lines.append(f"- **Error**: {step['error']}")
        lines.append("")
        lines.append("```json")
        lines.append(trunc(step.get("response")))
        lines.append("```")
        lines.append("")

    # Chatbot Q&A
    if report["chatbot_qa"]:
        lines.append("## 💬 Chatbot Q&A Results")
        lines.append("")
        for i, qa in enumerate(report["chatbot_qa"], 1):
            lines.append(f"### Q{i}. {qa['question']}")
            lines.append("")
            lines.append(f"**Answer** _(took {qa.get('took_ms', '?')} ms, {qa.get('source_count', 0)} sources)_:")
            lines.append("")
            lines.append(qa["answer"])
            lines.append("")

    # Artifacts
    if report["artifacts"]:
        lines.append("## 📁 Artifacts")
        lines.append("")
        for artifact in report["artifacts"]:
            lines.append(f"- `{artifact}`")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ Report written to {report_path}")
    print(f"\n📊 SUMMARY: {passed_steps}/{total_steps} steps passed ({s['pass_rate']})")
    print(f"   Chatbot Q&A: {len(report['chatbot_qa'])} questions answered")
    print(f"   Artifacts: {report['artifacts']}")


if __name__ == "__main__":
    main()

