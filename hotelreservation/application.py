from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import guests, reservations, rooms
from .database import initialize_db
from .schemas import HealthResponse


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
app.include_router(rooms.router, prefix="/rooms")
app.include_router(guests.router, prefix="/guests")
app.include_router(reservations.router, prefix="/reservations")


@app.get("/health", tags=["system"], summary="Check service health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}
