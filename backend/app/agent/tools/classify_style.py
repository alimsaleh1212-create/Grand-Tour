"""Tool 2 — classify_style: sklearn Pipeline → travel-style label.

The classifier is a pre-trained sklearn Pipeline (joblib) loaded once in
the FastAPI lifespan.  This tool wraps predict_proba() in a thread executor
so the synchronous sklearn call never blocks the async event loop.

FEATURE SET (matches ml/src/feature_pipeline.py exactly)
---------------------------------------------------------
Numeric (12): avg_temp_c, cost_per_day_usd, safety_index, language_difficulty,
              activity_density, nightlife_score, cultural_sites, nature_score,
              beach_score, family_friendly, infrastructure, luxury_index
Categorical (1): region

LABELS
------
Adventure | Budget | Culture | Family | Luxury | Relaxation

PUBLIC SURFACE
--------------
    class DestinationFeatures(BaseModel)
    class ClassifyInput(BaseModel)
    class ClassifyResult(BaseModel)
    class ClassifyStyleTool(BaseTool[ClassifyInput, ClassifyResult])
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field
from sklearn.pipeline import Pipeline

from app.agent.tools.base import BaseTool
from app.core.exceptions import MLModelError

log = logging.getLogger(__name__)

TravelStyle = Literal[
    "Adventure", "Budget", "Culture", "Family", "Luxury", "Relaxation"
]

_NUMERIC_FEATURES = [
    "avg_temp_c",
    "cost_per_day_usd",
    "safety_index",
    "language_difficulty",
    "activity_density",
    "nightlife_score",
    "cultural_sites",
    "nature_score",
    "beach_score",
    "family_friendly",
    "infrastructure",
    "luxury_index",
]
_CATEGORICAL_FEATURES = ["region"]
_ALL_FEATURES = _NUMERIC_FEATURES + _CATEGORICAL_FEATURES


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class DestinationFeatures(BaseModel):
    """Numeric + categorical features extracted from RAG chunks by the LLM.

    All numeric features are on a 0–10 scale unless noted otherwise.
    The cheap LLM fills these from retrieved text; gaps are filled with
    reasonable world-knowledge estimates.
    """

    avg_temp_c: float = Field(..., description="Average annual temperature (°C)")
    cost_per_day_usd: float = Field(..., ge=0, description="Typical daily budget (USD)")
    safety_index: float = Field(..., ge=0, le=10)
    language_difficulty: float = Field(..., ge=0, le=10)
    activity_density: float = Field(..., ge=0, le=10)
    nightlife_score: float = Field(..., ge=0, le=10)
    cultural_sites: float = Field(..., ge=0, le=10)
    nature_score: float = Field(..., ge=0, le=10)
    beach_score: float = Field(..., ge=0, le=10)
    family_friendly: float = Field(..., ge=0, le=10)
    infrastructure: float = Field(..., ge=0, le=10)
    luxury_index: float = Field(..., ge=0, le=10)
    region: str = Field(
        ...,
        description=(
            "One of: Europe, Asia, Americas, Africa, Middle East, Oceania"
        ),
    )


class ClassifyInput(BaseModel):
    """Input schema for the classify_style tool."""

    destination_name: str = Field(..., min_length=1, max_length=120)
    features: DestinationFeatures


class ClassifyResult(BaseModel):
    """Output schema for the classify_style tool."""

    destination_name: str
    predicted_style: TravelStyle
    confidence: float = Field(..., ge=0.0, le=1.0)
    all_probabilities: dict[str, float]


# ── Tool implementation ────────────────────────────────────────────────────────


class ClassifyStyleTool(BaseTool[ClassifyInput, ClassifyResult]):
    """Predict travel style from numeric/categorical destination features.

    Args:
        classifier: Trained sklearn Pipeline loaded from joblib.
    """

    name = "classify_style"
    input_schema = ClassifyInput
    output_schema = ClassifyResult

    def __init__(self, classifier: Pipeline) -> None:
        self._clf = classifier

    async def run(self, args: ClassifyInput) -> ClassifyResult:
        """Run predict_proba in a thread executor (sklearn is synchronous).

        Args:
            args: Validated destination name + feature vector.

        Returns:
            ClassifyResult with predicted label, confidence, and all probs.

        Raises:
            MLModelError: If the pipeline rejects the feature shape.
        """
        feat = args.features
        row = {
            "avg_temp_c": feat.avg_temp_c,
            "cost_per_day_usd": feat.cost_per_day_usd,
            "safety_index": feat.safety_index,
            "language_difficulty": feat.language_difficulty,
            "activity_density": feat.activity_density,
            "nightlife_score": feat.nightlife_score,
            "cultural_sites": feat.cultural_sites,
            "nature_score": feat.nature_score,
            "beach_score": feat.beach_score,
            "family_friendly": feat.family_friendly,
            "infrastructure": feat.infrastructure,
            "luxury_index": feat.luxury_index,
            "region": feat.region,
        }
        X = pd.DataFrame([row])

        def _predict() -> tuple[str, float, dict[str, float]]:
            try:
                proba = self._clf.predict_proba(X)[0]
                classes: list[str] = list(self._clf.classes_)
            except Exception as exc:
                raise MLModelError(f"Classifier predict failed: {exc}") from exc

            idx = int(proba.argmax())
            label: str = classes[idx]
            confidence: float = float(proba[idx])
            all_probs = {cls: float(p) for cls, p in zip(classes, proba)}
            return label, confidence, all_probs

        label, confidence, all_probs = await asyncio.to_thread(_predict)

        log.info(
            "tool.classify_style.success",
            extra={
                "destination": args.destination_name,
                "label": label,
                "confidence": f"{confidence:.2%}",
            },
        )

        return ClassifyResult(
            destination_name=args.destination_name,
            predicted_style=label,  # type: ignore[arg-type]
            confidence=confidence,
            all_probabilities=all_probs,
        )
