"""One helper for tests that write a database through a plain connection."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from velometer.report.data import ReportData, open_readonly


@contextmanager
def committing(
    path: Path, connect: Callable[[Path], sqlite3.Connection] = sqlite3.connect
) -> Iterator[sqlite3.Connection]:
    """`with sqlite3.connect(path) as conn` commits (or rolls back) but leaves the connection
    open; this does the same and then closes it."""
    conn = connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


@contextmanager
def read_data(db_path: Path, config_dir: Path) -> Iterator[ReportData]:
    """A ReportData on a fresh read-only connection, closed on exit."""
    conn = open_readonly(db_path)
    try:
        yield ReportData(conn, config_dir)
    finally:
        conn.close()
