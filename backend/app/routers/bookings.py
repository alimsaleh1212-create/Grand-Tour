"""Bookings router — demo flight reservation (Bonus B1).

ENDPOINTS
---------
    POST /bookings          — confirm a booking (saves to DB, no real airline)
    GET  /bookings          — list user's bookings
    GET  /bookings/{id}     — one booking detail
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.booking import Booking
from app.deps.auth import CurrentUser
from app.deps.db import get_session
from app.schemas.booking import BookingOut, BookingRequest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingOut:
    """Save a demo flight booking and return the booking reference.

    No real airline API is called.  The booking is stored with status
    "confirmed" and a UUID reference for display purposes.
    """
    booking = Booking(
        user_id=user.id,
        run_id=body.run_id,
        booking_ref=str(uuid.uuid4()),
        origin_iata=body.origin_iata.upper(),
        destination_iata=body.destination_iata.upper(),
        departure_date=body.departure_date,
        passenger_name=body.passenger_name,
        passenger_email=str(body.passenger_email),
        price_total=body.price_total,
        currency=body.currency.upper(),
        status="confirmed",
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)

    log.info(
        "booking.created",
        extra={
            "booking_ref": booking.booking_ref,
            "user_id": user.id,
            "route": f"{booking.origin_iata}→{booking.destination_iata}",
        },
    )
    return BookingOut.model_validate(booking)


@router.get("", response_model=list[BookingOut])
async def list_bookings(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BookingOut]:
    """Return the authenticated user's bookings, newest first."""
    stmt = (
        select(Booking)
        .where(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
    )
    result = await session.execute(stmt)
    bookings = list(result.scalars().all())
    return [BookingOut.model_validate(b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingOut:
    """Return one booking (user-scoped — 404 for other users' bookings)."""
    stmt = select(Booking).where(
        Booking.id == booking_id,
        Booking.user_id == user.id,
    )
    result = await session.execute(stmt)
    booking = result.scalar_one_or_none()
    if booking is None:
        raise NotFoundError("Booking not found.")
    return BookingOut.model_validate(booking)
