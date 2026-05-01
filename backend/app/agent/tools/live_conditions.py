"""Tool 3 — live_conditions: weather + FX + estimated flights.

Three sub-clients sharing one httpx.AsyncClient:
    Open-Meteo      weather   no key, free
    open.er-api.com FX        no key, free
    lookup table    flights   no key, estimated prices from city→IATA map

TTL caches (cachetools) prevent hammering upstream APIs for repeated queries:
    weather  TTLCache(ttl=600)    key = (lat, lon, date)
    FX       TTLCache(ttl=3600)   key = (base, quote, date)

Thundering-herd protection: each cache has a paired asyncio.Lock with
double-check inside — see CLAUDE.md §8.

Flight prices are estimated from a city→IATA lookup table (no API key needed).
Each entry has a human-readable city name, full airport name, IATA codes, and
price range (off-season low, peak-season high).  Price varies deterministically
by day-of-year so the same query on the same day always returns the same price.
reason="estimated" flags this in the response.

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
from typing import NamedTuple

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

# ── Flight price estimates (no API key needed) ────────────────────────────────


class FlightEstimate(NamedTuple):
    """Estimated flight data for one destination.

    Fields:
        destination_city:    Human-readable city, e.g. "Paris"
        destination_airport: Full airport name, e.g. "Charles de Gaulle"
        dest_iata:           IATA airport code, e.g. "CDG"
        default_origin_iata: IATA code of the default departure airport
        default_origin_city: Human-readable origin city, e.g. "New York"
        price_low_usd:       Off-season estimated round-trip price (USD)
        price_high_usd:      Peak-season estimated round-trip price (USD)
        departure_time:      Typical departure (24h, local origin time)
        arrival_time:        Typical arrival (24h, local dest time, +1/+2 = next day)
        duration_hours:      Flight duration in hours
        frequency:           Service frequency, e.g. "Daily"
        airline:             Representative carrier, e.g. "Air France"
    """

    destination_city: str
    destination_airport: str
    dest_iata: str
    default_origin_iata: str
    default_origin_city: str
    price_low_usd: int
    price_high_usd: int
    departure_time: str
    arrival_time: str
    duration_hours: float
    frequency: str
    airline: str


_FLIGHT_ESTIMATES: dict[str, FlightEstimate] = {
    "paris": FlightEstimate(
        "Paris", "Charles de Gaulle", "CDG",
        "JFK", "New York", 350, 800,
        "18:30", "08:15+1", 7.75, "Daily", "Air France",
    ),
    "rome": FlightEstimate(
        "Rome", "Fiumicino", "FCO",
        "JFK", "New York", 350, 750,
        "20:15", "10:30+1", 8.25, "Daily", "ITA Airways",
    ),
    "london": FlightEstimate(
        "London", "Heathrow", "LHR",
        "JFK", "New York", 300, 700,
        "21:30", "09:30+1", 7.0, "Daily", "British Airways",
    ),
    "tokyo": FlightEstimate(
        "Tokyo", "Narita", "NRT",
        "LHR", "London", 500, 1100,
        "11:30", "08:45+1", 12.25, "Daily", "Japan Airlines",
    ),
    "bali": FlightEstimate(
        "Bali (Denpasar)", "Ngurah Rai", "DPS",
        "LHR", "London", 600, 1200,
        "21:30", "18:30+1", 15.0, "5x weekly", "Qatar Airways",
    ),
    "dubai": FlightEstimate(
        "Dubai", "Dubai International", "DXB",
        "LHR", "London", 250, 600,
        "22:00", "08:15+1", 6.25, "Daily", "Emirates",
    ),
    "bangkok": FlightEstimate(
        "Bangkok", "Suvarnabhumi", "BKK",
        "LHR", "London", 450, 900,
        "21:30", "15:30+1", 11.5, "Daily", "Thai Airways",
    ),
    "singapore": FlightEstimate(
        "Singapore", "Changi", "SIN",
        "LHR", "London", 500, 950,
        "22:05", "17:50+1", 12.75, "Daily", "Singapore Airlines",
    ),
    "barcelona": FlightEstimate(
        "Barcelona", "El Prat", "BCN",
        "JFK", "New York", 300, 650,
        "20:00", "09:30+1", 7.5, "Daily", "Iberia",
    ),
    "cancun": FlightEstimate(
        "Cancún", "Cancún International", "CUN",
        "JFK", "New York", 200, 500,
        "08:30", "12:00", 3.5, "Daily", "American Airlines",
    ),
    "istanbul": FlightEstimate(
        "Istanbul", "Istanbul Airport", "IST",
        "LHR", "London", 250, 550,
        "17:00", "23:15", 3.25, "Daily", "Turkish Airlines",
    ),
    "cape town": FlightEstimate(
        "Cape Town", "Cape Town International", "CPT",
        "LHR", "London", 600, 1100,
        "21:30", "11:00+1", 11.5, "Daily", "British Airways",
    ),
    "reykjavik": FlightEstimate(
        "Reykjavík", "Keflavík", "KEF",
        "LHR", "London", 150, 400,
        "08:00", "10:30", 3.5, "Daily", "Icelandair",
    ),
    "sydney": FlightEstimate(
        "Sydney", "Kingsford Smith", "SYD",
        "LHR", "London", 800, 1400,
        "21:30", "06:10+2", 22.5, "Daily", "Qantas",
    ),
    "maldives": FlightEstimate(
        "Malé", "Velana International", "MLE",
        "LHR", "London", 700, 1200,
        "22:00", "13:10+1", 10.5, "4x weekly", "Emirates",
    ),
    "kyoto": FlightEstimate(
        "Kyoto (Osaka)", "Kansai", "KIX",
        "LHR", "London", 550, 950,
        "19:00", "14:40+1", 11.67, "Daily", "KLM",
    ),
    "santorini": FlightEstimate(
        "Santorini", "Santorini (Thira)", "JTR",
        "LHR", "London", 200, 550,
        "07:30", "13:10", 3.67, "5x weekly", "Aegean Airlines",
    ),
    "chiang mai": FlightEstimate(
        "Chiang Mai", "Chiang Mai International", "CNX",
        "LHR", "London", 500, 950,
        "21:00", "17:30+1", 13.5, "4x weekly", "Thai Airways",
    ),
    "queenstown": FlightEstimate(
        "Queenstown", "Queenstown Airport", "ZQN",
        "LHR", "London", 900, 1600,
        "21:00", "10:30+2", 24.5, "3x weekly", "Air New Zealand",
    ),
    "patagonia": FlightEstimate(
        "Patagonia (El Calafate)", "El Calafate", "FTE",
        "LHR", "London", 800, 1500,
        "21:30", "16:00+1", 14.5, "3x weekly", "Aerolineas Argentinas",
    ),
}

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
    """Estimated flight quote with schedule, or an unavailability explanation."""

    origin: str
    origin_city: str = ""
    destination: str
    destination_city: str = ""
    destination_airport: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration_hours: float | None = None
    frequency: str = ""
    airline: str = ""
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
        url = f"https://open.er-api.com/v6/latest/{base}"
        r = await self._http.get(url, timeout=10.0)
        r.raise_for_status()
        body = r.json()
        if body.get("result") != "success":
            raise ExternalAPIError(f"FX API error: {body.get('error-type')}")
        rates: dict[str, float] = body.get("rates", {})
        rate = rates.get(quote)
        if rate is None:
            raise ExternalAPIError(f"FX rate {base}/{quote} not in response")
        return {"base": base, "quote": quote, "rate": round(rate, 6)}

    # ── Flights ───────────────────────────────────────────────────────────────

    async def _get_flights(self, args: LiveConditionsQuery) -> FlightQuote:
        city_key = args.city.lower().strip()
        entry = next(
            (v for k, v in _FLIGHT_ESTIMATES.items() if k in city_key or city_key in k),
            None,
        )
        if entry is None:
            log.info(
                "live_conditions.flights_no_estimate",
                extra={"city": args.city},
            )
            return FlightQuote(
                origin="N/A",
                destination="N/A",
                available=False,
                reason="No flight estimate for this destination",
            )

        day_seed = date.today().timetuple().tm_yday
        price = entry.price_low_usd + (
            (entry.price_high_usd - entry.price_low_usd) * (day_seed % 17) // 17
        )

        log.info(
            "live_conditions.flights_estimated",
            extra={
                "city": args.city,
                "origin": entry.default_origin_iata,
                "dest": entry.dest_iata,
                "price": price,
            },
        )
        return FlightQuote(
            origin=entry.default_origin_iata,
            origin_city=entry.default_origin_city,
            destination=entry.dest_iata,
            destination_city=entry.destination_city,
            destination_airport=entry.destination_airport,
            departure_time=entry.departure_time,
            arrival_time=entry.arrival_time,
            duration_hours=entry.duration_hours,
            frequency=entry.frequency,
            airline=entry.airline,
            currency="USD",
            price_total=float(price),
            available=True,
            reason="estimated",
        )
