#!/usr/bin/env python3
"""End-to-end smoke test for the Multi-Agent Financial Research System API."""

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


def _resolve_pdf_path(arg):
    if not arg:
        pdfs = sorted((ROOT / "data" / "documents").glob("*.pdf"))
        if not pdfs:
            raise SystemExit("No PDF found in data/documents")
        return pdfs[0]
    candidate = Path(arg)
    if candidate.is_absolute():
        return candidate
    if (ROOT / candidate).exists():
        return ROOT / candidate
    return candidate.resolve()


def _resolve_report_path(suffix):
    suffix = (suffix or "").strip()
    if not suffix:
        return ROOT / "docs" / "e2e_report.md"
    safe = suffix.replace(" ", "_")
    return ROOT / "docs" / ("e2e_" + safe + ".md")


PDF_PATH = _resolve_pdf_path(sys.argv[1] if len(sys.argv) > 1 else None)
REPORT_SUFFIX = sys.argv[2] if len(sys.argv) > 2 else None
REPORT_PATH = _resolve_report_path(REPORT_SUFFIX)

OUT_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "docs").mkdir(parents=True, exist_ok=True)


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {"text": response.text}


def trunc(obj, limit=4000):
    text = json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return text


def main():
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = {"base_url": BASE_URL, "started_at": started, "steps": [], "artifacts": []}

    def add_step(name, method, path, response=None, elapsed=None, error=None, body_override=None):
        entry = {
            "name": name,
            "method": method,
            "path": path,
            "elapsed_ms": round(elapsed * 1000, 2) if elapsed is not None else None,
        }
        if response is not None:
            entry["status_code"] = response.status_code
            if body_override is None:
                try:
                    entry["response"] = response.json()
                except Exception:
                    entry["response"] = response.text
        if body_override is not None:
            entry["response"] = body_override
        if error is not None:
            entry["error"] = str(error)
        report["steps"].append(entry)
        return entry

    with httpx.Client(base_url=BASE_URL, cookies={}, timeout=300.0) as client:
        # --- auth: register a temp user (handle 409) then login ---
        email = f"e2e_{uuid.uuid4().hex[:10]}@example.com"
        password = "E2eTestPassword123!"

        t0 = time.perf_counter()
        try:
            r = client.post("/auth/register", json={"email": email, "full_name": "E2E Test User", "password": password})
            t = time.perf_counter() - t0
            add_step("register", "POST", "/auth/register", r, t)
            if r.status_code not in (201, 409):
                r.raise_for_status()
        except Exception as exc:
            add_step("register", "POST", "/auth/register", None, time.perf_counter() - t0, error=exc)
            raise

        t0 = time.perf_counter()
        r = client.post("/auth/login", json={"email": email, "password": password})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("login", "POST", "/auth/login", r, t)
        login_body = r.json()

        # --- workspace ---
        t0 = time.perf_counter()
        r = client.post("/workspaces", json={"name": "E2E Test"})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("create_workspace", "POST", "/workspaces", r, t)
        ws_id = r.json()["id"]

        # --- upload Apple 10-K ---
        t0 = time.perf_counter()
        with open(PDF_PATH, "rb") as f:
            r = client.post(
                f"/workspaces/{ws_id}/documents",
                files={"file": (PDF_PATH.name, f, "application/pdf")},
            )
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("upload_document", "POST", f"/workspaces/{ws_id}/documents", r, t)
        doc_id = r.json()["document_id"]

        # --- poll document status ---
        t0 = time.perf_counter()
        final_doc = None
        deadline = time.time() + 900
        last_resp = None
        while time.time() < deadline:
            last_resp = client.get(f"/documents/{doc_id}")
            last_resp.raise_for_status()
            final_doc = last_resp.json()
            status = final_doc["processing_status"]
            if status in ("completed", "failed"):
                break
            time.sleep(2)
        t = time.perf_counter() - t0
        add_step("poll_document_status", "GET", f"/documents/{doc_id}", last_resp, t)
        if final_doc is None or final_doc["processing_status"] not in ("completed", "failed"):
            raise RuntimeError("document processing did not finish within 900s")

        # --- search ---
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/search", json={"query": "revenue"})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("search", "POST", f"/workspaces/{ws_id}/search", r, t)

        # --- red flag analysis ---
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/red-flags/analyze", params={"document_id": doc_id})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("red_flag_analysis", "POST", f"/workspaces/{ws_id}/red-flags/analyze", r, t)

        # --- research question ---
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/research", json={"question": "What was revenue?"})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("research", "POST", f"/workspaces/{ws_id}/research", r, t)

        # --- forecast with manual observations ---
        obs = [
            {"period": "2022", "value": 100},
            {"period": "2023", "value": 120},
            {"period": "2024", "value": 145},
        ]
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/forecasts", json={"observations": obs, "horizon": 2, "method": "linear"})
        t = time.perf_counter() - t0
        r.raise_for_status()
        add_step("forecast", "POST", f"/workspaces/{ws_id}/forecasts", r, t)

        # --- exports (CSV + JSON) ---
        for fmt in ("csv", "json"):
            t0 = time.perf_counter()
            r = client.post(f"/workspaces/{ws_id}/exports", json={"format": fmt, "data_type": "metrics"})
            t = time.perf_counter() - t0
            r.raise_for_status()
            suffix = "csv" if fmt == "csv" else "json"
            out_file = OUT_DIR / f"e2e_metrics.{suffix}"
            out_file.write_bytes(r.content)
            add_step(
                f"export_{fmt}",
                "POST",
                f"/workspaces/{ws_id}/exports",
                r,
                t,
                body_override={
                    "saved_to": str(out_file),
                    "bytes": len(r.content),
                    "content_type": r.headers.get("content-type"),
                },
            )
            report["artifacts"].append(str(out_file))

    # --- write report ---
    lines = []
    lines.append("# E2E Test Report")
    lines.append("")
    lines.append(f"- Base URL: {BASE_URL}")
    lines.append(f"- Started: {started}")
    lines.append(f"- Finished: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    lines.append("")
    lines.append(f"- User: {email}")
    lines.append(f"- Workspace ID: {ws_id}")
    lines.append(f"- Document ID: {doc_id}")
    lines.append(f"- Document status: {final_doc['processing_status']}")
    lines.append("")
    for step in report["steps"]:
        lines.append(f"## {step['name']}")
        lines.append("")
        lines.append(f"- Method: {step['method']}")
        lines.append(f"- Path: {step['path']}")
        if step.get("elapsed_ms") is not None:
            lines.append(f"- Elapsed: {step['elapsed_ms']} ms")
        if step.get("status_code") is not None:
            lines.append(f"- Status: {step['status_code']}")
        if step.get("error"):
            lines.append(f"- Error: {step['error']}")
        lines.append("")
        lines.append("```json")
        lines.append(trunc(step.get("response")))
        lines.append("```")
        lines.append("")
    if report["artifacts"]:
        lines.append("## Artifacts")
        lines.append("")
        for artifact in report["artifacts"]:
            lines.append(f"- {artifact}")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("Report written to", REPORT_PATH)
    print("E2E SUMMARY")
    for step in report["steps"]:
        print(f"  {step['name']}: {step.get('status_code', 'ERR')} ({step.get('elapsed_ms')} ms)")
    print("Artifacts:", report["artifacts"])


if __name__ == "__main__":
    main()
