from __future__ import annotations

from threading import Lock


class ManagedApiKeyPool:
    def __init__(self, store) -> None:
        self._store = store
        self._cursor = 0
        self._lock = Lock()

    def reserve_attempt_order(self):
        keys = self._store.list_enabled_api_keys()
        if not keys:
            return ()
        with self._lock:
            if self._cursor >= len(keys):
                self._cursor = 0
            start_index = self._cursor
            self._cursor = (self._cursor + 1) % len(keys)
        return keys[start_index:] + keys[:start_index]
