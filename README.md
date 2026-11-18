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
uvicorn service.application:app --reload
```

By default, SQLite stores data in `hotel.db` in the working directory. Set
`DATABASE_PATH` to choose another file path.

## Run with Docker Compose

```sh
docker compose up --build
```

Open `http://localhost:8080` for the UI or `http://localhost:8000/docs` for the
service API. Compose builds the service and UI from their separate Dockerfiles;
the named volume persists the SQLite database across container restarts.

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

The `service` folder contains the FastAPI application, models, database setup,
and its Dockerfile. The `ui` folder contains a static browser UI, its Nginx API
proxy configuration, and its Dockerfile. The root `docker-compose.yml` runs
both containers together. `main.py` remains a compatibility ASGI entry point
for `uvicorn main:app --reload`.

## Example workflow

1. `POST /rooms` with `{"room_number":"101","room_type":"queen","capacity":2,"nightly_rate":129.0}`
2. `POST /guests` with `{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com"}`
3. `POST /reservations` with room/guest IDs, `check_in`, `check_out`, and `guest_count`
4. `PATCH /reservations/{id}/status` with `{"status":"checked_in"}` or `{"status":"cancelled"}`

This sample service does not include authentication or payment processing.
