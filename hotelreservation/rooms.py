import sqlite3

from fastapi import APIRouter, HTTPException, status

from .common import row_dict
from .database import db_connection
from .schemas import RoomCreate, RoomResponse, RoomUpdate


router = APIRouter(tags=["rooms"])


@router.get("", summary="List rooms", response_model=list[RoomResponse])
def list_rooms(active_only: bool = False):
    with db_connection() as connection:
        sql = "SELECT * FROM rooms"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY room_number"
        return [row_dict(row) for row in connection.execute(sql)]


@router.post(
    "",
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


@router.patch(
    "/{room_id}",
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
