import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomCreate(APIModel):
    room_number: str = Field(min_length=1, max_length=20)
    room_type: str = Field(min_length=1, max_length=50)
    capacity: int = Field(gt=0, le=20)
    nightly_rate: float = Field(ge=0)


class RoomUpdate(APIModel):
    room_type: str | None = Field(default=None, min_length=1, max_length=50)
    capacity: int | None = Field(default=None, gt=0, le=20)
    nightly_rate: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class GuestCreate(APIModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("email must be a valid email address")
        return value


class GuestUpdate(APIModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("email must be a valid email address")
        return value


class ReservationStatus(str, Enum):
    booked = "booked"
    checked_in = "checked_in"
    checked_out = "checked_out"
    cancelled = "cancelled"


class RoomResponse(APIModel):
    id: int
    room_number: str
    room_type: str
    capacity: int
    nightly_rate: float
    is_active: bool


class GuestResponse(APIModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None


class ReservationResponse(APIModel):
    id: int
    room_id: int
    guest_id: int
    check_in: date
    check_out: date
    guest_count: int
    status: ReservationStatus
    created_at: str
    room_number: str
    first_name: str
    last_name: str
    email: str


class HealthResponse(APIModel):
    status: str


class ReservationCreate(APIModel):
    room_id: int = Field(gt=0)
    guest_id: int = Field(gt=0)
    check_in: date
    check_out: date
    guest_count: int = Field(gt=0, le=20)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class ReservationStatusUpdate(APIModel):
    status: ReservationStatus
