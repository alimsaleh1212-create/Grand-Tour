"""Integration tests — FastAPI TestClient + transactional DB session.

External services (Gemini, Open-Meteo, Amadeus, exchangerate.host) are
always stubbed; we exercise our own routers/services/db, not the
internet.
"""
