"""Tests for DatabaseConnection protocol and connect() in explorer.py."""

import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from vic_health.explorer import connect, _redact_dsn, _Sqlite3Connection, _Psycopg2Connection


# --- _redact_dsn ---

def test_redact_dsn_removes_password():
    dsn = "postgresql://user:s3cr3t@localhost/mydb"
    assert "s3cr3t" not in _redact_dsn(dsn)
    assert "user" in _redact_dsn(dsn)
    assert "localhost" in _redact_dsn(dsn)


def test_redact_dsn_no_password_unchanged():
    dsn = "postgresql://user@localhost/mydb"
    assert _redact_dsn(dsn) == dsn


def test_redact_dsn_sqlite_unchanged():
    dsn = "sqlite:///mydb.sqlite"
    assert _redact_dsn(dsn) == dsn


# --- _Sqlite3Connection adapter ---

def test_sqlite3_execute_returns_list_of_dicts():
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    raw.execute("INSERT INTO t VALUES (1, 'hello')")
    raw.commit()

    conn = _Sqlite3Connection(raw)
    rows = conn.execute("SELECT a, b FROM t")
    assert rows == [{"a": 1, "b": "hello"}]


def test_sqlite3_execute_empty_result():
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE t (a INTEGER)")
    raw.commit()

    conn = _Sqlite3Connection(raw)
    rows = conn.execute("SELECT a FROM t")
    assert rows == []


def test_sqlite3_close():
    raw = sqlite3.connect(":memory:")
    conn = _Sqlite3Connection(raw)
    conn.close()
    with pytest.raises(Exception):
        raw.execute("SELECT 1")


# --- connect() for SQLite ---

def test_connect_sqlite_memory():
    conn = connect(":memory:")
    rows = conn.execute("SELECT 1 AS val")
    assert rows == [{"val": 1}]
    conn.close()


def test_connect_sqlite_prefix_stripped():
    conn = connect("sqlite:///:memory:")
    rows = conn.execute("SELECT 42 AS n")
    assert rows == [{"n": 42}]
    conn.close()


def test_connect_sqlite_failure_raises_connection_error():
    with patch("vic_health.explorer.sqlite3") as mock_sqlite:
        mock_sqlite.connect.side_effect = Exception("disk I/O error")
        with pytest.raises(ConnectionError) as exc_info:
            connect("/nonexistent/path/db.sqlite")
        assert "Failed to connect" in str(exc_info.value)


# --- connect() for PostgreSQL ---

def test_connect_postgresql_raises_connection_error_with_redacted_dsn():
    dsn = "postgresql://admin:topsecret@localhost/testdb"
    with pytest.raises(ConnectionError) as exc_info:
        connect(dsn)
    error_msg = str(exc_info.value)
    assert "topsecret" not in error_msg
    assert "admin" in error_msg
    assert "localhost" in error_msg


def test_connect_postgres_prefix_also_raises_redacted_error():
    dsn = "postgres://user:mypassword@db.host/prod"
    with pytest.raises(ConnectionError) as exc_info:
        connect(dsn)
    assert "mypassword" not in str(exc_info.value)


def test_connect_postgresql_success():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.description = [("id",), ("name",)]
    mock_cursor.fetchall.return_value = [(1, "Alice")]
    mock_conn.cursor.return_value = mock_cursor

    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn

    import sys
    with patch.dict(sys.modules, {"psycopg2": mock_psycopg2}):
        conn = connect("postgresql://user:pass@localhost/db")

    rows = conn.execute("SELECT id, name FROM t")
    assert rows == [{"id": 1, "name": "Alice"}]


# --- discover() ---

from vic_health.explorer import discover, DiscoveryError
from vic_health.models import TableInfo


def _make_sqlite_conn(setup_sql: list[str]) -> _Sqlite3Connection:
    """Helper: create an in-memory SQLite connection with given setup SQL."""
    raw = sqlite3.connect(":memory:")
    for stmt in setup_sql:
        raw.execute(stmt)
    raw.commit()
    return _Sqlite3Connection(raw)


def test_discover_sqlite_finds_relevant_table(capsys):
    conn = _make_sqlite_conn([
        "CREATE TABLE meshblocks (mb_id TEXT, geom BLOB)",
    ])
    results = discover(conn)
    assert len(results) == 1
    assert results[0].name == "meshblocks"
    assert results[0].meshblock_column == "mb_id"
    assert results[0].geometry_column == "geom"
    captured = capsys.readouterr()
    assert "meshblocks" in captured.out


def test_discover_sqlite_ignores_table_without_geometry():
    conn = _make_sqlite_conn([
        "CREATE TABLE scores (meshblock_id TEXT, score REAL)",
    ])
    with pytest.raises(DiscoveryError) as exc_info:
        discover(conn)
    assert "scores" in str(exc_info.value)


def test_discover_sqlite_ignores_table_without_meshblock_column():
    conn = _make_sqlite_conn([
        "CREATE TABLE shapes (id INTEGER, geom BLOB)",
    ])
    with pytest.raises(DiscoveryError):
        discover(conn)


def test_discover_sqlite_raises_when_no_relevant_tables():
    conn = _make_sqlite_conn([
        "CREATE TABLE unrelated (id INTEGER, name TEXT)",
    ])
    with pytest.raises(DiscoveryError) as exc_info:
        discover(conn)
    assert "unrelated" in str(exc_info.value)


def test_discover_sqlite_multiple_tables_returns_relevant_only():
    conn = _make_sqlite_conn([
        "CREATE TABLE meshblocks (mb_code TEXT, geom BLOB)",
        "CREATE TABLE unrelated (id INTEGER, name TEXT)",
        "CREATE TABLE also_relevant (meshblock_id TEXT, geometry BLOB)",
    ])
    results = discover(conn)
    names = {r.name for r in results}
    assert names == {"meshblocks", "also_relevant"}
    assert "unrelated" not in names


def test_discover_sqlite_table_hint_valid(capsys):
    conn = _make_sqlite_conn([
        "CREATE TABLE mytable (mb_id TEXT, geom BLOB)",
    ])
    results = discover(conn, table_hint="mytable")
    assert len(results) == 1
    assert results[0].name == "mytable"
    captured = capsys.readouterr()
    assert "mytable" in captured.out


def test_discover_sqlite_table_hint_skips_enumeration():
    """With a valid hint, only the hinted table is returned even if others qualify."""
    conn = _make_sqlite_conn([
        "CREATE TABLE mytable (mb_id TEXT, geom BLOB)",
        "CREATE TABLE other (meshblock_id TEXT, geometry BLOB)",
    ])
    results = discover(conn, table_hint="mytable")
    assert len(results) == 1
    assert results[0].name == "mytable"


def test_discover_sqlite_table_hint_nonexistent_raises():
    conn = _make_sqlite_conn([
        "CREATE TABLE something (id INTEGER)",
    ])
    with pytest.raises(DiscoveryError) as exc_info:
        discover(conn, table_hint="ghost_table")
    assert "ghost_table" in str(exc_info.value)


def test_discover_sqlite_table_hint_missing_geometry_raises():
    conn = _make_sqlite_conn([
        "CREATE TABLE mytable (mb_id TEXT, score REAL)",
    ])
    with pytest.raises(DiscoveryError) as exc_info:
        discover(conn, table_hint="mytable")
    assert "geometry" in str(exc_info.value).lower()


def test_discover_sqlite_table_hint_missing_meshblock_raises():
    conn = _make_sqlite_conn([
        "CREATE TABLE mytable (id INTEGER, geom BLOB)",
    ])
    with pytest.raises(DiscoveryError) as exc_info:
        discover(conn, table_hint="mytable")
    assert "meshblock" in str(exc_info.value).lower()


def test_discover_sqlite_geometry_type_column():
    """Column with type 'geometry' (not BLOB) should also be recognised."""
    conn = _make_sqlite_conn([
        "CREATE TABLE t (meshblock_id TEXT, shape geometry)",
    ])
    results = discover(conn)
    assert results[0].geometry_column == "shape"


def test_discover_sqlite_all_meshblock_column_variants():
    """All recognised meshblock column name variants should be detected."""
    variants = ["meshblock_id", "mb_id", "mb21_code", "mb_code", "mb_2021_code"]
    for col in variants:
        conn = _make_sqlite_conn([
            f"CREATE TABLE t ({col} TEXT, geom BLOB)",
        ])
        results = discover(conn)
        assert results[0].meshblock_column == col
