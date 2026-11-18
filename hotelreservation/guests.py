import sqlite3

from fastapi import APIRouter, HTTPException, Response, status

from .common import row_dict
from .database import db_connection
from .schemas import GuestCreate, GuestResponse, GuestUpdate


router = APIRouter(tags=["guests"])


@router.get("", summary="List guests", response_model=list[GuestResponse])
def list_guests():
    with db_connection() as connection:
        rows = connection.execute("SELECT * FROM guests ORDER BY last_name, first_name")
        return [row_dict(row) for row in rows]


@router.post(
    "",
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


@router.get("/{guest_id}", summary="Get a guest", response_model=GuestResponse)
def get_guest(guest_id: int):
    with db_connection() as connection:
        guest = connection.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone()
        if guest is None:
            raise HTTPException(status_code=404, detail="Guest not found")
        return row_dict(guest)


@router.patch("/{guest_id}", summary="Update guest details", response_model=GuestResponse)
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


@router.delete(
    "/{guest_id}",
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
