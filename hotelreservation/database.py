import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "hotel.db"))


def connect_db() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


@contextmanager
def db_connection():
    connection = connect_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_db() -> None:
    with db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY,
                room_number TEXT NOT NULL UNIQUE,
                room_type TEXT NOT NULL,
                capacity INTEGER NOT NULL CHECK (capacity > 0),
                nightly_rate REAL NOT NULL CHECK (nightly_rate >= 0),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT
            );
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY,
                room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
                guest_id INTEGER NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
                check_in DATE NOT NULL,
                check_out DATE NOT NULL,
                guest_count INTEGER NOT NULL CHECK (guest_count > 0),
                status TEXT NOT NULL DEFAULT 'booked'
                    CHECK (status IN ('booked', 'checked_in', 'checked_out', 'cancelled')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (check_out > check_in)
            );
            CREATE INDEX IF NOT EXISTS idx_reservations_room_dates
                ON reservations(room_id, check_in, check_out, status);
            CREATE INDEX IF NOT EXISTS idx_reservations_guest
                ON reservations(guest_id);
            """
        )
