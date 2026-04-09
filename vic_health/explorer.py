# Explorer: database connection factory

import re
import sqlite3
from typing import Protocol


class DatabaseConnection(Protocol):
    """Thin protocol so Extractor is testable without a real DB."""

    def execute(self, sql: str, params: tuple = ()) -> list[dict]: ...
    def close(self) -> None: ...


def _redact_dsn(dsn: str) -> str:
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", dsn)


class _Psycopg2Connection:
    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


class _Sqlite3Connection:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self._conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


# Keep for backwards compat with any existing imports
class DiscoveryError(Exception):
    pass


def connect(dsn: str) -> DatabaseConnection:
    """
    Parse the DSN and return the appropriate connection wrapper.
    Raises ConnectionError (with redacted DSN) on failure.
    """
    redacted = _redact_dsn(dsn)

    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        try:
            import psycopg2  # type: ignore[import]
            conn = psycopg2.connect(dsn)
            return _Psycopg2Connection(conn)
        except ConnectionError:
            raise
        except Exception as exc:
            raise ConnectionError(f"Failed to connect to database ({redacted}): {exc}") from exc
    else:
        path = re.sub(r"^sqlite:///?", "", dsn)
        try:
            conn = sqlite3.connect(path)
            return _Sqlite3Connection(conn)
        except Exception as exc:
            raise ConnectionError(f"Failed to connect to database ({redacted}): {exc}") from exc
