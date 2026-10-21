"""The agents of the Multi-Agent Financial Research System.

The package hosts the components that *act* on a document:

* :class:`~app.agents.document_agent.DocumentAgent` runs the ingestion
  pipeline for a single document and keeps the document row and the
  processing job in sync with the outcome.
* :class:`~app.agents.job_runner.JobRunner` is the strategy that decides
  where a processing job runs (inline or in a background thread).
"""

from __future__ import annotations

from app.agents.document_agent import DocumentAgent, ProcessingOutcome
from app.agents.job_runner import (
    BackgroundThreadJobRunner,
    InlineJobRunner,
    JobRunner,
)

__all__ = [
    "BackgroundThreadJobRunner",
    "DocumentAgent",
    "InlineJobRunner",
    "JobRunner",
    "ProcessingOutcome",
]