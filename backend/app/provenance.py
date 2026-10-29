"""Compatibility alias for the citation and evidence system."""

import app.citations as _citation_module

globals().update({name: getattr(_citation_module, name) for name in _citation_module.__all__})
__all__ = list(_citation_module.__all__)
