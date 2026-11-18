# HotelReservation API

A compact REST service for room inventory, guest records, and hotel reservations.
FastAPI generates interactive OpenAPI documentation at `/docs` and a JSON
schema at `/openapi.json`.

## Run locally

Requires Python 3.13 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

By default, SQLite stores data in `hotel.db` in the working directory. Set
`DATABASE_PATH` to choose another file path.

## Run with Docker

```powershell
docker build -t hotelreservation-api .
docker run --rm -p 8000:8000 -v hotel-data:/data hotelreservation-api
```

The named volume persists the SQLite database across container restarts. Open
`http://localhost:8000/docs` to explore and call the endpoints.

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health check |
| GET, POST | `/rooms` | List rooms or add a room |
| PATCH | `/rooms/{room_id}` | Change room details or active status |
| GET, POST | `/guests` | List or register guests |
| GET, PATCH, DELETE | `/guests/{guest_id}` | Read, update, or remove a guest without reservations |
| GET, POST | `/reservations` | List/filter reservations or book a room |
| GET | `/reservations/{reservation_id}` | Read reservation details |
| PATCH | `/reservations/{reservation_id}/status` | Check in, check out, or cancel |

Reservation filters include `guest_id`, `room_id`, and `status`. Dates are
`YYYY-MM-DD`; check-out is exclusive, so a new stay may start on the prior
reservation's check-out date. Overlapping active bookings for a room are rejected
with HTTP 409. Allowed status transitions are `booked` to `checked_in` or
`cancelled`, then `checked_in` to `checked_out`.

All endpoints are documented with request validation and response schemas in
the generated OpenAPI document.

## Source layout

The `hotelreservation` package separates the API application, database access, request
and response schemas, shared reservation helpers, and the room, guest, and
reservation route modules. `main.py` remains the ASGI entry point, so the
existing `uvicorn main:app --reload` command continues to work.

## Example workflow

1. `POST /rooms` with `{"room_number":"101","room_type":"queen","capacity":2,"nightly_rate":129.0}`
2. `POST /guests` with `{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com"}`
3. `POST /reservations` with room/guest IDs, `check_in`, `check_out`, and `guest_count`
4. `PATCH /reservations/{id}/status` with `{"status":"checked_in"}` or `{"status":"cancelled"}`

This sample service does not include authentication or payment processing.
