#!/usr/bin/env python3
"""Probe: full research response JSON for 'What was total revenue?'.

Also prints red-flag findings and report metrics. Uses a fresh user, checks the
database, and cleans up the created workspace at the end.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000/api/v1"
PDF_PATH = ROOT / "data" / "documents" / "microsoft_fy2025_annual_report.pdf"


def main() -> None:
    started = time.time()
    metrics: dict = {"steps": []}

    def record(name, status, elapsed_ms, ok):
        metrics["steps"].append({"name": name, "status": status, "elapsed_ms": round(elapsed_ms, 2), "ok": ok})
        print(f"[probe] {name}: {status} ({elapsed_ms:.0f} ms) {'OK' if ok else 'FAIL'}", flush=True)

    with httpx.Client(base_url=BASE_URL, timeout=300.0) as client:
        # --- DB test ---
        t0 = time.perf_counter()
        r = client.get("/health")
        r.raise_for_status()
        health = r.json()
        db_ok = str(health.get("checks", {}).get("database", "")).startswith("ok")
        record("db_health", r.status_code, (time.perf_counter() - t0) * 1000, db_ok and r.status_code == 200)
        if not db_ok:
            raise SystemExit(f"DB check failed: {health}")

        # --- fresh user ---
        email = f"probe_{uuid.uuid4().hex[:10]}@example.com"
        password = "ProbeTestPassword123!"
        t0 = time.perf_counter()
        r = client.post("/auth/register", json={"email": email, "full_name": "Probe User", "password": password})
        record("register", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code in (201, 409))
        t0 = time.perf_counter()
        r = client.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        record("login", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 200)

        # --- workspace ---
        t0 = time.perf_counter()
        r = client.post("/workspaces", json={"name": "Probe Workspace"})
        r.raise_for_status()
        record("create_workspace", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 201)
        ws_id = r.json()["id"]

        # --- upload document ---
        t0 = time.perf_counter()
        with open(PDF_PATH, "rb") as f:
            r = client.post(f"/workspaces/{ws_id}/documents", files={"file": (PDF_PATH.name, f, "application/pdf")})
        r.raise_for_status()
        record("upload_document", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 201)
        doc_id = r.json()["document_id"]

        # --- poll processing ---
        t0 = time.perf_counter()
        final_status = "unknown"
        deadline = time.time() + 300
        last_resp = None
        while time.time() < deadline:
            last_resp = client.get(f"/documents/{doc_id}")
            last_resp.raise_for_status()
            final_status = last_resp.json().get("processing_status", "unknown")
            if final_status in ("completed", "failed"):
                break
            time.sleep(2)
        elapsed = (time.perf_counter() - t0) * 1000
        record("poll_document", last_resp.status_code if last_resp else 0, elapsed, final_status == "completed")
        if final_status != "completed":
            raise SystemExit(f"Document processing failed: {final_status}")

        # --- research ---
        question = "What was total revenue?"
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/research", json={"question": question})
        r.raise_for_status()
        research_json = r.json()
        record("research", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 200)
        print("\n=== RESEARCH RESPONSE JSON ===", flush=True)
        print(json.dumps(research_json, indent=2), flush=True)

        # --- red-flag findings ---
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/red-flags/analyze", params={"document_id": doc_id})
        r.raise_for_status()
        redflag_json = r.json()
        record("red_flag_analyze", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 200)
        print("\n=== RED-FLAG FINDINGS ===", flush=True)
        print(json.dumps(redflag_json, indent=2), flush=True)

        # list stored findings too
        t0 = time.perf_counter()
        r = client.get(f"/workspaces/{ws_id}/red-flags")
        if r.status_code == 200:
            record("list_red_flags", r.status_code, (time.perf_counter() - t0) * 1000, True)
            print("\n=== STORED RED-FLAG FINDINGS ===", flush=True)
            print(json.dumps(r.json(), indent=2), flush=True)

        # --- report metrics ---
        t0 = time.perf_counter()
        r = client.get(f"/workspaces/{ws_id}/metrics")
        metrics_ok = r.status_code == 200
        if metrics_ok:
            record("list_metrics", r.status_code, (time.perf_counter() - t0) * 1000, True)
            print("\n=== REPORT METRICS ===", flush=True)
            print(json.dumps(r.json(), indent=2), flush=True)
        else:
            record("list_metrics", r.status_code, (time.perf_counter() - t0) * 1000, False)

        # generate a report as well
        t0 = time.perf_counter()
        r = client.post(f"/workspaces/{ws_id}/report", json={"question": question})
        if r.status_code in (200, 201):
            record("generate_report", r.status_code, (time.perf_counter() - t0) * 1000, True)
            print("\n=== REPORT RESPONSE ===", flush=True)
            print(json.dumps(r.json(), indent=2), flush=True)
        else:
            record("generate_report", r.status_code, (time.perf_counter() - t0) * 1000, False)

        # --- cleanup ---
        t0 = time.perf_counter()
        r = client.delete(f"/workspaces/{ws_id}")
        record("cleanup_workspace", r.status_code, (time.perf_counter() - t0) * 1000, r.status_code == 204)

    metrics["total_elapsed_ms"] = round((time.time() - started) * 1000, 2)
    metrics["user"] = email
    print("\n=== PROBE METRICS ===", flush=True)
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
