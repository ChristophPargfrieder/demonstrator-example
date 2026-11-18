import sqlite3
from datetime import date

from fastapi import HTTPException


ACTIVE_BOOKING_STATUSES = ("booked", "checked_in")


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def get_reservation(connection: sqlite3.Connection, reservation_id: int):
    return connection.execute(
        """
        SELECT r.*, rooms.room_number, guests.first_name, guests.last_name,
               guests.email
        FROM reservations AS r
        JOIN rooms ON rooms.id = r.room_id
        JOIN guests ON guests.id = r.guest_id
        WHERE r.id = ?
        """,
        (reservation_id,),
    ).fetchone()


def ensure_no_booking_conflict(
    connection: sqlite3.Connection,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> None:
    sql = """
        SELECT id FROM reservations
        WHERE room_id = ?
          AND status IN (?, ?)
          AND check_in < ?
          AND check_out > ?
    """
    params: list = [room_id, *ACTIVE_BOOKING_STATUSES, check_out.isoformat(), check_in.isoformat()]
    if exclude_reservation_id is not None:
        sql += " AND id != ?"
        params.append(exclude_reservation_id)
    if connection.execute(sql, params).fetchone():
        raise HTTPException(status_code=409, detail="Room is already reserved for those dates")
