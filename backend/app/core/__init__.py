"""Core cross-cutting concerns.

Modules:
    settings.py    Single source of truth for configuration. Implemented as a
                   pydantic-settings `Settings` class with `@lru_cache(maxsize=1)`
                   accessor `get_settings()`. Every other module imports its
                   config FROM HERE — no scattered `os.getenv` calls.
    logging.py     Structured (JSON) logging setup. Called once at app start;
                   modules use `logger = logging.getLogger(__name__)`.
    security.py    Password hashing (bcrypt) and JWT issue/verify helpers.
                   The thin layer used by `services.auth_service`.
    exceptions.py  `AppError` hierarchy. Routers translate these to
                   HTTPException with sanitized client messages; full traces
                   are logged server-side only.
"""
