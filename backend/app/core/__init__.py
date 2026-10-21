"""Core building blocks: configuration, logging and domain exceptions.

This package intentionally contains no I/O beyond reading the local ``.env``
file, so it can be imported safely from any layer (models, migrations,
services, API) without side effects.
"""

__all__: list[str] = []