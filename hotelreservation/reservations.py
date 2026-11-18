from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from .common import ensure_no_booking_conflict, get_reservation, row_dict
from .database import connect_db, db_connection
from .schemas import (
    ReservationCreate,
    ReservationResponse,
    ReservationStatus,
    ReservationStatusUpdate,
)


router = APIRouter(tags=["reservations"])


@router.get("", summary="List and filter reservations", response_model=list[ReservationResponse])
def list_reservations(
    guest_id: int | None = None,
    room_id: int | None = None,
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
):
    conditions = []
    params: list = []
    if guest_id is not None:
        conditions.append("r.guest_id = ?")
        params.append(guest_id)
    if room_id is not None:
        conditions.append("r.room_id = ?")
        params.append(room_id)
    if reservation_status is not None:
        conditions.append("r.status = ?")
        params.append(reservation_status.value)
    sql = """
        SELECT r.*, rooms.room_number, guests.first_name, guests.last_name, guests.email
        FROM reservations AS r
        JOIN rooms ON rooms.id = r.room_id
        JOIN guests ON guests.id = r.guest_id
    """
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY r.check_in, r.id"
    with db_connection() as connection:
        return [row_dict(row) for row in connection.execute(sql, params)]


@router.post(
    "",
    summary="Book a room",
    status_code=status.HTTP_201_CREATED,
    response_model=ReservationResponse,
)
def create_reservation(reservation: ReservationCreate):
    connection = connect_db()
    try:
        connection.execute("BEGIN IMMEDIATE")
        room = connection.execute(
            "SELECT capacity, is_active FROM rooms WHERE id = ?", (reservation.room_id,)
        ).fetchone()
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        if not room["is_active"]:
            raise HTTPException(status_code=409, detail="Room is not available for booking")
        if reservation.guest_count > room["capacity"]:
            raise HTTPException(status_code=422, detail="Guest count exceeds room capacity")
        if connection.execute("SELECT id FROM guests WHERE id = ?", (reservation.guest_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Guest not found")
        ensure_no_booking_conflict(
            connection,
            reservation.room_id,
            reservation.check_in,
            reservation.check_out,
        )
        cursor = connection.execute(
            """
            INSERT INTO reservations (room_id, guest_id, check_in, check_out, guest_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                reservation.room_id,
                reservation.guest_id,
                reservation.check_in.isoformat(),
                reservation.check_out.isoformat(),
                reservation.guest_count,
            ),
        )
        result = row_dict(get_reservation(connection, cursor.lastrowid))
        connection.commit()
        return result
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


@router.get(
    "/{reservation_id}",
    summary="Get a reservation",
    response_model=ReservationResponse,
)
def read_reservation(reservation_id: int):
    with db_connection() as connection:
        reservation = get_reservation(connection, reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return row_dict(reservation)


@router.patch(
    "/{reservation_id}/status",
    summary="Advance or cancel a reservation",
    response_model=ReservationResponse,
)
def update_reservation_status(reservation_id: int, update: ReservationStatusUpdate):
    allowed_transitions = {
        "booked": {"checked_in", "cancelled"},
        "checked_in": {"checked_out"},
        "checked_out": set(),
        "cancelled": set(),
    }
    with db_connection() as connection:
        current = connection.execute(
            "SELECT status FROM reservations WHERE id = ?", (reservation_id,)
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if update.status.value not in allowed_transitions[current["status"]]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot change reservation from {current['status']} to {update.status.value}",
            )
        connection.execute(
            "UPDATE reservations SET status = ? WHERE id = ?",
            (update.status.value, reservation_id),
        )
        return row_dict(get_reservation(connection, reservation_id))
