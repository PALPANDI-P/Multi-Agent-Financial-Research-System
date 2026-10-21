"""Operational scripts of the Multi-Agent Financial Research System.

The package holds the runnable entry points of the backend:

* :mod:`scripts.seed_documents` - download the seed corpus, register it
  through the real document service and run the real ingestion pipeline.
* :mod:`scripts.verify_index` - verify the seeded corpus against the real
  database.

The scripts can be executed from the ``backend/`` directory::

    python -m scripts.seed_documents --workspace "Seed Documents"

and from the repository root::

    python backend/scripts/seed_documents.py --workspace "Seed Documents"

Importing the package puts the ``backend`` directory on ``sys.path``, so the
application package ``app`` is importable no matter from where the script was
started.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Directory that holds the ``app`` package.
BACKEND_DIR: Path = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

__all__ = ["BACKEND_DIR"]