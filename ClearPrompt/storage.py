"""SQLite storage for persistent policy settings and content-free audit records."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SETTINGS = {
    "policy": "warn",
    "enabled_detectors": [
        "Private key", "Cloud access key", "API token", "Email address",
        "US Social Security number", "Credit card number", "Phone number",
    ],
    "custom_keywords": [],
}


def _connect(database: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _connection(database: str):
    connection = _connect(database)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(database: str) -> None:
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with _connection(database) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                policy TEXT NOT NULL,
                outcome TEXT NOT NULL,
                finding_count INTEGER NOT NULL,
                finding_types TEXT NOT NULL
            );
        """)
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )


def get_settings(database: str) -> dict:
    with _connection(database) as connection:
        rows = connection.execute("SELECT key, value FROM settings").fetchall()
    settings = {row["key"]: json.loads(row["value"]) for row in rows}
    return {**DEFAULT_SETTINGS, **settings}


def save_settings(database: str, settings: dict) -> None:
    with _connection(database) as connection:
        connection.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(key, json.dumps(value)) for key, value in settings.items()],
        )


def record_scan(database: str, policy: str, outcome: str, findings: list[dict]) -> None:
    event_types = list(dict.fromkeys(item["type"] for item in findings))
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection(database) as connection:
        connection.execute(
            "INSERT INTO audit (timestamp, policy, outcome, finding_count, finding_types) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, policy, outcome, len(findings), json.dumps(event_types)),
        )


def get_audit(database: str, limit: int = 50) -> list[dict]:
    limit = max(0, limit)
    with _connection(database) as connection:
        rows = connection.execute(
            "SELECT timestamp, policy, outcome, finding_count, finding_types "
            "FROM audit ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [{**dict(row), "finding_types": json.loads(row["finding_types"])} for row in rows]


def clear_audit(database: str) -> None:
    with _connection(database) as connection:
        connection.execute("DELETE FROM audit")
        connection.execute("DELETE FROM sqlite_sequence WHERE name='audit'")


def get_scan_count(database: str) -> int:
    with _connection(database) as connection:
        return connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
