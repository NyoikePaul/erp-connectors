"""Conflict strategies for two-way sync (stub for Phase 2)."""

from __future__ import annotations

from datetime import datetime

from erp_connectors.models import Customer


def last_write_wins(
    local: Customer,
    remote: Customer,
    local_updated_at: datetime | None,
    remote_updated_at: datetime | None,
) -> Customer:
    if local_updated_at and remote_updated_at:
        return local if local_updated_at >= remote_updated_at else remote
    return remote  # default: prefer remote when timestamps missing
