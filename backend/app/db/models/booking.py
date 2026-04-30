"""Booking ORM model — demo flight reservation (no real airline API).

A booking is created when the user confirms a flight from the live_conditions
tool result via the booking confirmation modal in the frontend.

DEMO NOTE: No actual airline API is called.  The booking is stored in Postgres
with a UUID reference so the UI can display a "confirmed" state.  The status
is always "confirmed" for demo purposes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Booking(TimestampMixin, Base):
    """One confirmed (demo) flight booking per row.

    Columns
    -------
    id               : surrogate PK
    user_id          : FK → users.id (for history queries)
    run_id           : FK → agent_runs.id (links back to the chat run)
    booking_ref      : UUID shown to the user as their "booking reference"
    origin_iata      : IATA code for departure airport (e.g. "LHR")
    destination_iata : IATA code for arrival airport (e.g. "NRT")
    departure_date   : date of the outbound flight
    passenger_name   : full name as entered in the confirmation form
    passenger_email  : email for "confirmation" notification
    price_total      : quoted price from Amadeus (or 0.0 when N/A)
    currency         : ISO 4217 (e.g. "USD")
    status           : always "confirmed" for demo
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    booking_ref: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        unique=True,
    )

    origin_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)

    passenger_name: Mapped[str] = mapped_column(String(200), nullable=False)
    passenger_email: Mapped[str] = mapped_column(String(200), nullable=False)

    price_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmed"
    )

    # Relationships
    user: Mapped[User] = relationship("User")
