from __future__ import annotations

from threading import Lock


class RoundRobinApiKeyPool:
    def __init__(self, keys: tuple[str, ...]) -> None:
        if not keys:
            raise RuntimeError("至少需要一把 deAPI API key")
        self._keys = tuple(keys)
        self._cursor = 0
        self._lock = Lock()

    def reserve_attempt_order(self) -> tuple[str, ...]:
        with self._lock:
            start_index = self._cursor
            self._cursor = (self._cursor + 1) % len(self._keys)
        return self._keys[start_index:] + self._keys[:start_index]
