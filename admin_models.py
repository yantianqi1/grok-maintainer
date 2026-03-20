from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedApiKey:
    id: int
    label: str
    api_key: str
    is_enabled: bool
    error_count: int
    success_count: int
    last_error_message: str
    last_used_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BulkAddResult:
    added_count: int
    skipped_count: int


@dataclass(frozen=True)
class DashboardStats:
    total_keys: int
    enabled_keys: int
    total_error_count: int
