import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status

from .database import connect_db, db_connection, initialize_db
from .models import (
    GuestCreate,
    GuestResponse,
    GuestUpdate,
    HealthResponse,
    ReservationCreate,
    ReservationResponse,
    ReservationStatus,
    ReservationStatusUpdate,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
)


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield


app = FastAPI(
    title="HotelReservation API",
    description=(
        "A small hotel operations API for room inventory, guest records, and "
        "date-based reservations. Reservation dates use ISO 8601 format; "
        "check-out is exclusive."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"], summary="Check service health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}


@app.get("/rooms", tags=["rooms"], summary="List rooms", response_model=list[RoomResponse])
def list_rooms(active_only: bool = False):
    with db_connection() as connection:
        sql = "SELECT * FROM rooms"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY room_number"
        return [row_dict(row) for row in connection.execute(sql)]


@app.post(
    "/rooms",
    tags=["rooms"],
    summary="Add a room",
    status_code=status.HTTP_201_CREATED,
    response_model=RoomResponse,
)
def create_room(room: RoomCreate):
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rooms (room_number, room_type, capacity, nightly_rate)
                VALUES (?, ?, ?, ?)
                """,
                (room.room_number.strip(), room.room_type.strip(), room.capacity, room.nightly_rate),
            )
            result = connection.execute(
                "SELECT * FROM rooms WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return row_dict(result)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Room number already exists") from exc


@app.patch(
    "/rooms/{room_id}",
    tags=["rooms"],
    summary="Update room details or availability",
    response_model=RoomResponse,
)
def update_room(room_id: int, update: RoomUpdate):
    changes = update.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Room fields cannot be null")
    changes = {key: int(value) if key == "is_active" else value for key, value in changes.items()}
    with db_connection() as connection:
        cursor = connection.execute(
            f"UPDATE rooms SET {', '.join(f'{key} = ?' for key in changes)} WHERE id = ?",
            [*changes.values(), room_id],
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Room not found")
        return row_dict(connection.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone())


@app.get("/guests", tags=["guests"], summary="List guests", response_model=list[GuestResponse])
def list_guests():
    with db_connection() as connection:
        rows = connection.execute("SELECT * FROM guests ORDER BY last_name, first_name")
        return [row_dict(row) for row in rows]


@app.post(
    "/guests",
    tags=["guests"],
    summary="Register a guest",
    status_code=status.HTTP_201_CREATED,
    response_model=GuestResponse,
)
def create_guest(guest: GuestCreate):
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO guests (first_name, last_name, email, phone)
                VALUES (?, ?, ?, ?)
                """,
                (
                    guest.first_name.strip(),
                    guest.last_name.strip(),
                    guest.email.strip(),
                    guest.phone,
                ),
            )
            result = connection.execute(
                "SELECT * FROM guests WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return row_dict(result)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A guest with that email already exists") from exc


@app.get("/guests/{guest_id}", tags=["guests"], summary="Get a guest", response_model=GuestResponse)
def get_guest(guest_id: int):
    with db_connection() as connection:
        guest = connection.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone()
        if guest is None:
            raise HTTPException(status_code=404, detail="Guest not found")
        return row_dict(guest)


@app.patch("/guests/{guest_id}", tags=["guests"], summary="Update guest details", response_model=GuestResponse)
def update_guest(guest_id: int, update: GuestUpdate):
    changes = update.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")
    if any(changes.get(key) is None for key in ("first_name", "last_name", "email") if key in changes):
        raise HTTPException(status_code=422, detail="Name and email fields cannot be null")
    if "email" in changes:
        changes["email"] = changes["email"].strip()
    for key in ("first_name", "last_name"):
        if key in changes:
            changes[key] = changes[key].strip()
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                f"UPDATE guests SET {', '.join(f'{key} = ?' for key in changes)} WHERE id = ?",
                [*changes.values(), guest_id],
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Guest not found")
            return row_dict(connection.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A guest with that email already exists") from exc


@app.delete(
    "/guests/{guest_id}",
    tags=["guests"],
    summary="Delete a guest without reservations",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_guest(guest_id: int):
    try:
        with db_connection() as connection:
            cursor = connection.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Guest not found")
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Guest has reservations and cannot be deleted") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/reservations",
    tags=["reservations"],
    summary="List and filter reservations",
    response_model=list[ReservationResponse],
)
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


@app.post(
    "/reservations",
    tags=["reservations"],
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


@app.get(
    "/reservations/{reservation_id}",
    tags=["reservations"],
    summary="Get a reservation",
    response_model=ReservationResponse,
)
def read_reservation(reservation_id: int):
    with db_connection() as connection:
        reservation = get_reservation(connection, reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return row_dict(reservation)


@app.patch(
    "/reservations/{reservation_id}/status",
    tags=["reservations"],
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
