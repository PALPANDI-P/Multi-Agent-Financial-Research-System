"""Multi-Agent Financial Research System - backend application package.

The package is split into focused layers that later waves build on:

* :mod:`app.core` - settings, logging and the domain exception hierarchy.
* :mod:`app.db` - SQLAlchemy declarative base, session management and models.
* :mod:`app.schemas` - Pydantic v2 request/response contracts.

Later waves add :mod:`app.api`, :mod:`app.services`, :mod:`app.ingestion`,
:mod:`app.embeddings` and :mod:`app.vectorstore` on top of these contracts.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"