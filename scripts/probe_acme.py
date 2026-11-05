#!/usr/bin/env python3
"""Probe: Acme two-page PDF ingestion + metrics + red flags (test DB)."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

# Run from backend/ so imports resolve.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.api.deps import clear_dependency_cache, get_settings_dep
from app.core.config import Settings
from app.db.session import create_engine_from_settings
from app.main import create_app

TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or (
    "postgresql+psycopg://frs:frs_dev_password@127.0.0.1:55432/financial_research_test"
)


def make_pdf() -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 80), "Acme Corporation Annual Report", fontsize=16)
        page.insert_text(
            (72, 120),
            "Acme Corporation Annual Report for the fiscal year 2025. Total revenue was "
            "1.2 billion US dollars, an increase of 8 percent compared with the previous "
            "year. The board of directors approved a dividend of 0.42 US dollars per "
            "share for the reporting period.",
            fontsize=11,
        )
        page = doc.new_page()
        page.insert_text((72, 80), "Management Discussion and Analysis", fontsize=16)
        page.insert_text(
            (72, 120),
            "Management discussion and analysis of the financial year 2025. Operating "
            "expenses grew by 3 percent while the operating margin improved to 18 "
            "percent. The industrial segment reported a revenue of 640 million US "
            "dollars and a profit of 95 million US dollars.",
            fontsize=11,
        )
        return doc.tobytes()
    finally:
        doc.close()


def truncate(engine):
    tables = [
        "red_flag_findings", "financial_metrics", "financial_calculations",
        "agent_runs", "document_chunks", "processing_jobs", "documents",
        "workspace_members", "workspaces", "auth_sessions", "users",
    ]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))


def main():
    settings = Settings(database_url=TEST_DB_URL, app_env="test", storage_root=Path(r"C:\Users\PALPANDI\AppData\Local\Temp\kilo\acme_storage"), processing_inline=True)
    engine = create_engine_from_settings(settings)
    truncate(engine)

    app = create_app(settings)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    clear_dependency_cache()

    email = f"probe_{uuid.uuid4().hex[:10]}@example.com"
    password = "ProbeTestPassword123!"

    with TestClient(app, raise_server_exceptions=False) as client:
        # register
        r = client.post("/api/v1/auth/register", json={"email": email, "full_name": "Probe User", "password": password})
        print("register:", r.status_code, r.text[:200])
        r.raise_for_status()
        # login
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        print("login:", r.status_code)

        # workspace
        r = client.post("/api/v1/workspaces", json={"name": "Acme Probe"})
        r.raise_for_status()
        ws_id = r.json()["id"]
        print("workspace:", ws_id)

        # upload
        pdf = make_pdf()
        r = client.post(f"/api/v1/workspaces/{ws_id}/documents", files={"file": ("acme.pdf", pdf, "application/pdf")})
        r.raise_for_status()
        doc_id = r.json()["document_id"]
        print("upload:", r.status_code, doc_id, r.json().get("processing_status"))

        # document detail
        r = client.get(f"/api/v1/documents/{doc_id}")
        r.raise_for_status()
        d = r.json()
        print("document page_count:", d.get("page_count"), "chunk_count:", d.get("chunk_count"), "status:", d.get("processing_status"))

        # metrics
        r = client.get(f"/api/v1/workspaces/{ws_id}/financial-metrics")
        print("metrics status:", r.status_code)
        metrics_body = r.json()
        items = metrics_body.get("items", [])
        print("METRICS COUNT:", len(items))
        print("METRICS LIST:")
        print(json.dumps(items, indent=2))

        # red-flag analysis
        r = client.post(f"/api/v1/workspaces/{ws_id}/red-flag-analysis", params={"document_id": doc_id})
        print("red-flag status:", r.status_code)
        rf = r.json()
        findings = rf.get("findings", [])
        print("RED FLAG FINDINGS COUNT:", len(findings))
        print("RED FLAG FINDINGS:")
        print(json.dumps(rf, indent=2))

        # cleanup
        r = client.delete(f"/api/v1/workspaces/{ws_id}")
        print("cleanup workspace:", r.status_code)

    truncate(engine)
    print("DONE")


if __name__ == "__main__":
    main()
