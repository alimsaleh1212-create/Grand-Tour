"""Booking request/response schemas (Bonus B1 — demo flight booking)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BookingRequest(BaseModel):
    """Body for POST /bookings — user confirms a flight from live_conditions."""

    run_id: int | None = Field(
        default=None, description="AgentRun that produced this flight quote."
    )
    origin_iata: str = Field(..., min_length=3, max_length=3)
    destination_iata: str = Field(..., min_length=3, max_length=3)
    departure_date: date
    passenger_name: str = Field(..., min_length=2, max_length=200)
    passenger_email: EmailStr
    price_total: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class BookingOut(BaseModel):
    """Public representation of a confirmed booking."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_ref: str
    origin_iata: str
    destination_iata: str
    departure_date: date
    passenger_name: str
    price_total: Decimal
    currency: str
    status: str
    created_at: datetime
