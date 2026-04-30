"""Tool 3 — live_conditions: weather + FX + optional flights.

Three sub-clients sharing one httpx.AsyncClient:
    Open-Meteo            weather   no key, free
    exchangerate.host     FX        no key, free
    Amadeus self-service  flights   key-gated, degrades gracefully

TTL caches (cachetools) prevent hammering upstream APIs for repeated queries:
    weather  TTLCache(ttl=600)    key = (lat, lon, date)
    FX       TTLCache(ttl=3600)   key = (base, quote, date)
    flights  TTLCache(ttl=3600)   key = (origin, dest, date)

Thundering-herd protection: each cache has a paired asyncio.Lock with
double-check inside — see CLAUDE.md §8.

Graceful degradation:
    If Amadeus keys are absent OR the upstream returns 4xx/5xx after retries,
    FlightQuote(available=False, reason=...) is returned.  The agent reasons
    about the absence rather than crashing.

PUBLIC SURFACE
--------------
    class LiveConditionsQuery(BaseModel)
    class WeatherWindow(BaseModel)
    class FXQuote(BaseModel)
    class FlightQuote(BaseModel)
    class LiveConditions(BaseModel)
    class LiveConditionsTool(BaseTool[LiveConditionsQuery, LiveConditions])
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx
from cachetools import TTLCache
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agent.tools.base import BaseTool
from app.core.exceptions import ExternalAPIError

log = logging.getLogger(__name__)

# ── TTL caches + locks ────────────────────────────────────────────────────────
_weather_cache: TTLCache[tuple[float, float, str], dict[str, object]] = TTLCache(
    maxsize=512, ttl=600
)
_weather_lock = asyncio.Lock()

_fx_cache: TTLCache[tuple[str, str, str], dict[str, object]] = TTLCache(
    maxsize=128, ttl=3600
)
_fx_lock = asyncio.Lock()

_flights_cache: TTLCache[tuple[str, str, str], dict[str, object]] = TTLCache(
    maxsize=128, ttl=3600
)
_flights_lock = asyncio.Lock()

# ── Pydantic schemas ───────────────────────────────────────────────────────────


class LiveConditionsQuery(BaseModel):
    """Input schema for the live_conditions tool."""

    city: str = Field(..., min_length=1, max_length=120)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    date_from: date
    date_to: date
    origin_iata: str | None = Field(
        default=None,
        description="IATA code for flight origin (e.g. 'LHR').",
        max_length=3,
    )
    destination_iata: str | None = Field(
        default=None,
        description="IATA code for flight destination (e.g. 'NRT').",
        max_length=3,
    )
    base_currency: str = Field(
        default="USD",
        description="ISO 4217 base currency for FX quote.",
        max_length=3,
    )
    quote_currency: str = Field(
        default="USD",
        description="ISO 4217 quote currency for FX quote.",
        max_length=3,
    )


class WeatherWindow(BaseModel):
    """Aggregated weather stats for a date window."""

    avg_temp_c: float
    min_temp_c: float
    max_temp_c: float
    precipitation_mm: float


class FXQuote(BaseModel):
    """Current exchange rate between two currencies."""

    base: str
    quote: str
    rate: float


class FlightQuote(BaseModel):
    """Cheapest available flight quote, or an unavailability explanation."""

    origin: str
    destination: str
    currency: str = "USD"
    price_total: float | None = None
    available: bool
    reason: str | None = None


class LiveConditions(BaseModel):
    """Aggregated live conditions for one destination."""

    weather: WeatherWindow | None
    fx: FXQuote | None
    flights: FlightQuote


# ── Tool implementation ────────────────────────────────────────────────────────


class LiveConditionsTool(BaseTool[LiveConditionsQuery, LiveConditions]):
    """Fetch real-time weather, FX, and (optionally) flight data.

    Args:
        http: Shared httpx.AsyncClient (injected from lifespan).
    """

    name = "live_conditions"
    input_schema = LiveConditionsQuery
    output_schema = LiveConditions

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def run(self, args: LiveConditionsQuery) -> LiveConditions:
        """Gather weather, FX, and flights concurrently."""
        weather_task = asyncio.create_task(self._get_weather(args))
        fx_task = asyncio.create_task(self._get_fx(args))
        flights_task = asyncio.create_task(self._get_flights(args))

        weather, fx, flights = await asyncio.gather(
            weather_task, fx_task, flights_task
        )

        return LiveConditions(weather=weather, fx=fx, flights=flights)

    # ── Weather ───────────────────────────────────────────────────────────────

    async def _get_weather(self, args: LiveConditionsQuery) -> WeatherWindow | None:
        date_str = str(args.date_from)
        key = (round(args.latitude, 2), round(args.longitude, 2), date_str)

        if key in _weather_cache:
            return WeatherWindow(**_weather_cache[key])

        async with _weather_lock:
            if key in _weather_cache:
                return WeatherWindow(**_weather_cache[key])

            try:
                data = await self._fetch_weather(
                    args.latitude, args.longitude, args.date_from, args.date_to
                )
                _weather_cache[key] = data
                return WeatherWindow(**data)
            except Exception as exc:
                log.warning(
                    "live_conditions.weather_failed",
                    extra={"city": args.city, "error": str(exc)},
                )
                return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
    async def _fetch_weather(
        self,
        lat: float,
        lon: float,
        date_from: date,
        date_to: date,
    ) -> dict[str, object]:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "start_date": str(date_from),
            "end_date": str(date_to),
            "timezone": "auto",
        }
        r = await self._http.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        body = r.json()
        daily = body.get("daily", {})
        max_temps: list[float] = daily.get("temperature_2m_max") or []
        min_temps: list[float] = daily.get("temperature_2m_min") or []
        precip: list[float] = daily.get("precipitation_sum") or []

        def _avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        return {
            "avg_temp_c": round((_avg(max_temps) + _avg(min_temps)) / 2, 1),
            "min_temp_c": round(min(min_temps, default=0.0), 1),
            "max_temp_c": round(max(max_temps, default=0.0), 1),
            "precipitation_mm": round(_avg(precip), 1),
        }

    # ── FX ────────────────────────────────────────────────────────────────────

    async def _get_fx(self, args: LiveConditionsQuery) -> FXQuote | None:
        base = args.base_currency.upper()
        quote = args.quote_currency.upper()
        if base == quote:
            return FXQuote(base=base, quote=quote, rate=1.0)

        date_str = str(args.date_from)
        key = (base, quote, date_str)

        if key in _fx_cache:
            return FXQuote(**_fx_cache[key])

        async with _fx_lock:
            if key in _fx_cache:
                return FXQuote(**_fx_cache[key])

            try:
                data = await self._fetch_fx(base, quote)
                _fx_cache[key] = data
                return FXQuote(**data)
            except Exception as exc:
                log.warning(
                    "live_conditions.fx_failed",
                    extra={"base": base, "quote": quote, "error": str(exc)},
                )
                return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError)
        ),
        reraise=True,
    )
    async def _fetch_fx(self, base: str, quote: str) -> dict[str, object]:
        url = "https://api.exchangerate.host/latest"
        params = {"base": base, "symbols": quote}
        r = await self._http.get(url, params=params, timeout=10.0)
        r.raise_for_status()
        body = r.json()
        rates: dict[str, float] = body.get("rates", {})
        rate = rates.get(quote)
        if rate is None:
            raise ExternalAPIError(f"FX rate {base}/{quote} not in response")
        return {"base": base, "quote": quote, "rate": round(rate, 6)}

    # ── Flights ───────────────────────────────────────────────────────────────

    async def _get_flights(self, args: LiveConditionsQuery) -> FlightQuote:
        origin = (args.origin_iata or "").upper()
        dest = (args.destination_iata or "").upper()

        if not origin or not dest:
            return FlightQuote(
                origin=origin or "N/A",
                destination=dest or "N/A",
                available=False,
                reason="origin_iata or destination_iata not provided",
            )

        from app.core.settings import get_settings

        settings = get_settings()
        if not settings.amadeus_api_key:
            return FlightQuote(
                origin=origin,
                destination=dest,
                available=False,
                reason="Amadeus API key not configured",
            )

        date_str = str(args.date_from)
        key = (origin, dest, date_str)

        if key in _flights_cache:
            return FlightQuote(**_flights_cache[key])

        async with _flights_lock:
            if key in _flights_cache:
                return FlightQuote(**_flights_cache[key])

            try:
                data = await self._fetch_flights(
                    origin,
                    dest,
                    args.date_from,
                    settings.amadeus_api_key.get_secret_value(),
                    settings.amadeus_api_secret.get_secret_value()  # type: ignore[union-attr]
                    if settings.amadeus_api_secret
                    else "",
                )
                _flights_cache[key] = data
                return FlightQuote(**data)
            except Exception as exc:
                log.warning(
                    "live_conditions.flights_failed",
                    extra={"origin": origin, "dest": dest, "error": str(exc)},
                )
                return FlightQuote(
                    origin=origin,
                    destination=dest,
                    available=False,
                    reason=f"Flight lookup failed: {type(exc).__name__}",
                )

    async def _fetch_flights(
        self,
        origin: str,
        dest: str,
        departure_date: date,
        api_key: str,
        api_secret: str,
    ) -> dict[str, object]:
        # Step 1: get OAuth2 token from Amadeus
        token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        token_r = await self._http.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": api_secret,
            },
            timeout=10.0,
        )
        token_r.raise_for_status()
        access_token: str = token_r.json()["access_token"]

        # Step 2: search for cheapest flight offer
        search_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        search_r = await self._http.get(
            search_url,
            params={
                "originLocationCode": origin,
                "destinationLocationCode": dest,
                "departureDate": str(departure_date),
                "adults": 1,
                "max": 1,
                "currencyCode": "USD",
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )
        search_r.raise_for_status()
        offers: list[dict[str, object]] = search_r.json().get("data", [])

        if not offers:
            return {
                "origin": origin,
                "destination": dest,
                "currency": "USD",
                "price_total": None,
                "available": False,
                "reason": "No flights found for this route and date",
            }

        price_info = offers[0].get("price", {})
        price_total = float(price_info.get("grandTotal", 0) or 0)
        currency: str = str(price_info.get("currency", "USD"))

        return {
            "origin": origin,
            "destination": dest,
            "currency": currency,
            "price_total": price_total,
            "available": True,
            "reason": None,
        }
