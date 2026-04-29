"""Load the trained travel-style classifier joblib.

Implemented in Stage 3 (training) + Stage 5 (wiring into the agent tool).

Design (per project brief):
    "Loading the joblib model on every request is a bug, not a style
    choice." The loader is called ONCE in the FastAPI lifespan startup
    and the resulting `Pipeline` lives on `app.state.classifier`.

Public surface (planned):
    def load_classifier(path: Path) -> Pipeline:
        # Returns the sklearn Pipeline that the classify_style tool uses.
        # Raises MLModelError if the file is missing or fails to load —
        # the app refuses to start in that case.

Path is taken from `Settings.ml_model_path` (added in Stage 1) — a single
config value, no hard-coded paths anywhere else.
"""
