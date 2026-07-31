#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Document-type registry.

Built-in types are registered on package import. After importing
``core.doc_types``, you can:

  * ``registry.get("vat")`` → DocType instance or None
  * ``registry.all_types()`` → list of all registered DocTypes (for UI menus)
  * ``registry.detect(response_json)`` → first DocType whose ``detect_response``
    returns True, used as a fallback when the caller didn't specify a type
"""
from __future__ import annotations

from typing import Optional

from .base import DocType

_REGISTRY: dict[str, DocType] = {}


def register(doc_type: DocType) -> DocType:
    """Register a DocType instance. Idempotent — re-registering the same
    type_id replaces the previous entry (used for tests)."""
    if not doc_type.type_id:
        raise ValueError("DocType.type_id must be set before register()")
    _REGISTRY[doc_type.type_id] = doc_type
    return doc_type


def unregister(type_id: str) -> None:
    _REGISTRY.pop(type_id, None)


def get(type_id: str) -> Optional[DocType]:
    return _REGISTRY.get(type_id)


def all_types() -> list[DocType]:
    """Stable order: insertion order."""
    return list(_REGISTRY.values())


def detect(response_json: dict) -> Optional[DocType]:
    """First DocType whose detect_response() returns True. None if nothing
    matches — caller decides whether to fall back to a default or fail."""
    for dt in _REGISTRY.values():
        try:
            if dt.detect_response(response_json):
                return dt
        except Exception:
            # A misbehaving detector must not break the whole pipeline.
            continue
    return None


# --- Eager-register built-in types ------------------------------------------
# Importing the module is what triggers registration. Keep at the bottom so
# the registry helpers above are defined first.

from . import vat  # noqa: E402,F401  -- registers "vat"
from . import medical  # noqa: E402,F401  -- registers "medical"
from . import train  # noqa: E402,F401  -- registers "train"
