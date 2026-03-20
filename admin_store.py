from __future__ import annotations

from pathlib import Path
import sqlite3

from admin_models import BulkAddResult, DashboardStats, ManagedApiKey, ManagedApiKeyPage
from admin_store_support import (
    FILTER_ALL,
    VALID_BULK_ACTIONS,
    build_filter_clause,
    ensure_success_count_column,
    execute_bulk_action,
    normalize_key_ids,
    parse_bulk_lines,
    row_to_key,
    schema_sql,
)
from werkzeug.security import check_password_hash, generate_password_hash


MIN_PAGE_NUMBER = 1


class AdminStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def init_db(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(schema_sql())
            ensure_success_count_column(connection)

    def ensure_admin_user(self, username: str, password: str) -> None:
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM admin_users WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO admin_users (username, password_hash, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (username, password_hash),
                )
                return
            if not check_password_hash(row["password_hash"], password):
                connection.execute(
                    """
                    UPDATE admin_users
                    SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (password_hash, row["id"]),
                )

    def verify_admin_credentials(self, username: str, password: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM admin_users WHERE username = ?",
                (username,),
            ).fetchone()
        return row is not None and check_password_hash(row["password_hash"], password)

    def bulk_add_api_keys(self, raw_input: str) -> BulkAddResult:
        added_count = 0
        skipped_count = 0
        parsed_lines = parse_bulk_lines(raw_input)
        with self._connect() as connection:
            for label, api_key in parsed_lines:
                if self._api_key_exists(connection, api_key):
                    skipped_count += 1
                    continue
                connection.execute(
                    """
                    INSERT INTO upstream_api_keys (
                        label,
                        api_key,
                        is_enabled,
                        error_count,
                        last_error_message,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, 1, 0, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (label, api_key),
                )
                added_count += 1
        return BulkAddResult(added_count=added_count, skipped_count=skipped_count)

    def list_api_keys(self, filter_name: str = FILTER_ALL) -> tuple[ManagedApiKey, ...]:
        where_clause = build_filter_clause(filter_name)
        return self._list_keys(where_clause, descending=True)

    def list_api_keys_page(
        self,
        filter_name: str = FILTER_ALL,
        *,
        page: int,
        page_size: int,
    ) -> ManagedApiKeyPage:
        where_clause = build_filter_clause(filter_name)
        normalized_page_size = max(int(page_size), MIN_PAGE_NUMBER)
        total_items = self._count_keys(where_clause)
        total_pages = max(MIN_PAGE_NUMBER, self._calculate_total_pages(total_items, normalized_page_size))
        normalized_page = min(max(int(page), MIN_PAGE_NUMBER), total_pages)
        offset = (normalized_page - MIN_PAGE_NUMBER) * normalized_page_size
        items = self._list_keys(
            where_clause,
            descending=True,
            limit=normalized_page_size,
            offset=offset,
        )
        return ManagedApiKeyPage(
            items=items,
            page=normalized_page,
            page_size=normalized_page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    def list_enabled_api_keys(self) -> tuple[ManagedApiKey, ...]:
        return self._list_keys("WHERE is_enabled = 1", descending=False)

    def toggle_api_key(self, key_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE upstream_api_keys
                SET is_enabled = CASE WHEN is_enabled = 1 THEN 0 ELSE 1 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (key_id,),
            )

    def delete_api_key(self, key_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM upstream_api_keys WHERE id = ?", (key_id,))

    def apply_bulk_action(self, action: str, key_ids: tuple[int, ...]) -> int:
        normalized_action = str(action).strip().lower()
        if normalized_action not in VALID_BULK_ACTIONS:
            raise ValueError("不支持的批量操作")
        normalized_ids = normalize_key_ids(key_ids)
        if not normalized_ids:
            return 0
        with self._connect() as connection:
            execute_bulk_action(connection, normalized_action, normalized_ids)
            row = connection.execute("SELECT changes() AS affected").fetchone()
        return int(row["affected"])

    def record_key_error(self, key_id: int, message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE upstream_api_keys
                SET error_count = error_count + 1,
                    last_error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (message.strip(), key_id),
            )

    def record_key_success(self, key_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE upstream_api_keys
                SET success_count = success_count + 1,
                    last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (key_id,),
            )

    def get_dashboard_stats(self) -> DashboardStats:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_keys,
                    COALESCE(SUM(is_enabled), 0) AS enabled_keys,
                    COALESCE(SUM(error_count), 0) AS total_error_count
                FROM upstream_api_keys
                """
            ).fetchone()
        return DashboardStats(
            total_keys=int(row["total_keys"]),
            enabled_keys=int(row["enabled_keys"]),
            total_error_count=int(row["total_error_count"]),
        )

    def _list_keys(
        self,
        where_clause: str,
        *,
        descending: bool,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[ManagedApiKey, ...]:
        order = "DESC" if descending else "ASC"
        query = f"""
            SELECT
                id,
                label,
                api_key,
                is_enabled,
                error_count,
                success_count,
                last_error_message,
                last_used_at,
                created_at,
                updated_at
            FROM upstream_api_keys
            {where_clause}
            ORDER BY id {order}
        """
        parameters: tuple[int, ...] = ()
        if limit is not None:
            query = f"{query}\nLIMIT ? OFFSET ?"
            parameters = (limit, offset)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(row_to_key(row) for row in rows)

    def _count_keys(self, where_clause: str) -> int:
        query = f"SELECT COUNT(*) AS total FROM upstream_api_keys {where_clause}"
        with self._connect() as connection:
            row = connection.execute(query).fetchone()
        return int(row["total"])

    def _calculate_total_pages(self, total_items: int, page_size: int) -> int:
        if total_items == 0:
            return MIN_PAGE_NUMBER
        return (total_items + page_size - MIN_PAGE_NUMBER) // page_size

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _api_key_exists(self, connection: sqlite3.Connection, api_key: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM upstream_api_keys WHERE api_key = ?",
            (api_key,),
        ).fetchone()
        return row is not None
