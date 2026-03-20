from __future__ import annotations

import sqlite3

from admin_models import ManagedApiKey


FILTER_ALL = "all"
FILTER_ENABLED = "enabled"
FILTER_DISABLED = "disabled"
FILTER_ERROR = "error"
FILTER_UNUSED = "unused"
VALID_FILTERS = frozenset(
    {FILTER_ALL, FILTER_ENABLED, FILTER_DISABLED, FILTER_ERROR, FILTER_UNUSED}
)
ACTION_ENABLE = "enable"
ACTION_DISABLE = "disable"
ACTION_DELETE = "delete"
VALID_BULK_ACTIONS = frozenset({ACTION_ENABLE, ACTION_DISABLE, ACTION_DELETE})


def build_filter_clause(filter_name: str) -> str:
    normalized = str(filter_name).strip().lower()
    if normalized not in VALID_FILTERS or normalized == FILTER_ALL:
        return ""
    if normalized == FILTER_ENABLED:
        return "WHERE is_enabled = 1"
    if normalized == FILTER_DISABLED:
        return "WHERE is_enabled = 0"
    if normalized == FILTER_ERROR:
        return "WHERE error_count > 0"
    return "WHERE success_count = 0"


def normalize_key_ids(key_ids: tuple[int, ...]) -> tuple[int, ...]:
    unique_ids = dict.fromkeys(int(key_id) for key_id in key_ids)
    return tuple(unique_ids)


def parse_bulk_lines(raw_input: str) -> tuple[tuple[str, str], ...]:
    parsed: list[tuple[str, str]] = []
    for raw_line in raw_input.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        label, api_key = split_label_and_key(line)
        if not api_key:
            continue
        parsed.append((label, api_key))
    return tuple(parsed)


def split_label_and_key(line: str) -> tuple[str, str]:
    if "," not in line:
        return "", line
    label, api_key = line.split(",", 1)
    return label.strip(), api_key.strip()


def row_to_key(row: sqlite3.Row) -> ManagedApiKey:
    return ManagedApiKey(
        id=int(row["id"]),
        label=str(row["label"] or ""),
        api_key=str(row["api_key"]),
        is_enabled=bool(row["is_enabled"]),
        error_count=int(row["error_count"]),
        success_count=int(row["success_count"]),
        last_error_message=str(row["last_error_message"] or ""),
        last_used_at=row["last_used_at"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def execute_bulk_action(
    connection: sqlite3.Connection,
    action: str,
    key_ids: tuple[int, ...],
) -> None:
    placeholders = ",".join("?" for _ in key_ids)
    if action == ACTION_DELETE:
        connection.execute(
            f"DELETE FROM upstream_api_keys WHERE id IN ({placeholders})",
            key_ids,
        )
        return
    enabled_value = 1 if action == ACTION_ENABLE else 0
    connection.execute(
        f"""
        UPDATE upstream_api_keys
        SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
        """,
        (enabled_value, *key_ids),
    )


def ensure_success_count_column(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(upstream_api_keys)").fetchall()
    column_names = {str(row["name"]) for row in columns}
    if "success_count" in column_names:
        return
    connection.execute(
        """
        ALTER TABLE upstream_api_keys
        ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0
        """
    )


def schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS upstream_api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL DEFAULT '',
        api_key TEXT NOT NULL UNIQUE,
        is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
        error_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        last_error_message TEXT NOT NULL DEFAULT '',
        last_used_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
