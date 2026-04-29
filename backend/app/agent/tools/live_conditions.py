"""Tool 3 — live_conditions (weather + FX + flights).

Implemented in Stage 5.

Three sub-clients, all sharing one `httpx.AsyncClient`:

    Open-Meteo               weather   no key, free
    exchangerate.host        FX        no key, free
    Amadeus self-service     flights   key-gated; degrades gracefully

Schemas (planned):
    class LiveConditionsQuery(BaseModel):
        city: str
        latitude: float
        longitude: float
        date_from: date
        date_to: date
        origin_iata: str | None = None
        destination_iata: str | None = None
        currency_pair: tuple[str, str] | None = None    # e.g. ("USD","EUR")

    class WeatherWindow(BaseModel):
        avg_temp_c: float
        min_temp_c: float
        max_temp_c: float
        precipitation_mm: float

    class FXQuote(BaseModel):
        base: str
        quote: str
        rate: float

    class FlightQuote(BaseModel):
        origin: str
        destination: str
        currency: str
        price_total: float | None
        available: bool
        reason: str | None        # populated when available is False

    class LiveConditions(BaseModel):
        weather: WeatherWindow | None
        fx: FXQuote | None
        flights: FlightQuote

Class (planned):
    class LiveConditionsTool(
        BaseTool[LiveConditionsQuery, LiveConditions]
    ):
        name = "live_conditions"
        ...

Caching:
    weather    cachetools.TTLCache(ttl=600)   key = (lat, lon, date)
    fx         cachetools.TTLCache(ttl=3600)  key = (base, quote, date)
    flights    cachetools.TTLCache(ttl=3600)  key = (origin, dest, date)

Per the plan's Caching Strategy section.

Graceful degradation:
    If `Settings.amadeus_api_key` is unset OR the upstream returns 429,
    the flights sub-client returns FlightQuote(available=False,
    reason=...). The agent must reason about missing data, not crash.
"""
