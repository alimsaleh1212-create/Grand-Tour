"""Load the trained travel-style classifier from a joblib file.

Called ONCE in the FastAPI lifespan.  The resulting Pipeline lives on
app.state.classifier for the entire process lifetime.  Never call this
from a request handler — loading a joblib on every request would add
hundreds of milliseconds per call.

PUBLIC SURFACE
--------------
    def load_classifier(path: Path) -> Pipeline
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.core.exceptions import MLModelError

log = logging.getLogger(__name__)


def load_classifier(path: Path) -> Pipeline:
    """Load and return the travel-style sklearn Pipeline from a joblib file.

    Args:
        path: Absolute or relative path to the .joblib artifact.

    Returns:
        Fitted sklearn Pipeline ready for predict / predict_proba calls.

    Raises:
        MLModelError: If the file is missing, unreadable, or does not contain
            an sklearn Pipeline.  The app refuses to start in this case.
    """
    if not path.exists():
        raise MLModelError(
            f"Classifier not found at {path}. "
            "Run 'uv run python -m ml.src.train' to produce the artifact."
        )

    try:
        obj = joblib.load(path)
    except Exception as exc:
        raise MLModelError(f"Failed to load classifier from {path}: {exc}") from exc

    if not isinstance(obj, Pipeline):
        raise MLModelError(
            f"Expected sklearn Pipeline at {path}, got {type(obj).__name__}."
        )

    log.info(
        "ml.classifier_loaded",
        extra={"path": str(path), "steps": [name for name, _ in obj.steps]},
    )
    return obj
