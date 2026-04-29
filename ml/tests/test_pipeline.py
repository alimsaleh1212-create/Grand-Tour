"""Tests for feature_pipeline and data_loader."""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from src.data_loader import LABEL_CLASSES, TARGET_COLUMN, compute_dataset_hash, load_raw
from src.feature_pipeline import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_pipeline


class TestLoadRaw:
    def test_loads_real_dataset(self) -> None:
        df = load_raw()
        assert len(df) == 160
        assert TARGET_COLUMN in df.columns

    def test_all_labels_present(self) -> None:
        df = load_raw()
        assert set(df[TARGET_COLUMN].unique()) == set(LABEL_CLASSES)

    def test_no_nulls(self) -> None:
        df = load_raw()
        assert not df.isnull().any().any()

    def test_missing_column_raises(self, tmp_path: pathlib.Path) -> None:
        csv = tmp_path / "bad.csv"
        # Write a CSV missing the 'label' column
        pd.DataFrame({"destination": ["X"], "country": ["Y"]}).to_csv(csv, index=False)
        with pytest.raises(ValueError, match="missing required columns"):
            load_raw(csv)

    def test_unknown_label_raises(self, tmp_path: pathlib.Path) -> None:
        df = load_raw()
        df = df.copy()
        df.loc[0, TARGET_COLUMN] = "Unknown"
        csv = tmp_path / "bad_label.csv"
        df.to_csv(csv, index=False)
        with pytest.raises(ValueError, match="Unknown label values"):
            load_raw(csv)


class TestDatasetHash:
    def test_hash_is_16_chars(self) -> None:
        df = load_raw()
        h = compute_dataset_hash(df)
        assert len(h) == 16

    def test_hash_changes_on_modification(self) -> None:
        df = load_raw()
        h1 = compute_dataset_hash(df)
        df2 = df.copy()
        df2.loc[0, "cost_per_day_usd"] = 9999.0
        h2 = compute_dataset_hash(df2)
        assert h1 != h2

    def test_hash_is_deterministic(self) -> None:
        df = load_raw()
        assert compute_dataset_hash(df) == compute_dataset_hash(df)


class TestBuildPipeline:
    def test_returns_sklearn_pipeline(self, fitted_pipeline: Pipeline) -> None:
        assert isinstance(fitted_pipeline, Pipeline)

    def test_pipeline_has_two_steps(self, fitted_pipeline: Pipeline) -> None:
        assert list(dict(fitted_pipeline.steps).keys()) == ["preprocess", "classifier"]

    def test_transform_shape(self, synthetic_df: pd.DataFrame) -> None:
        """Preprocessor output should have 12 numeric + 1 OHE-expanded region cols."""
        from src.feature_pipeline import build_preprocessor

        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        preprocessor = build_preprocessor()
        X = preprocessor.fit_transform(synthetic_df[features])
        # 12 numeric + however many region OHE columns (at least 1)
        assert X.shape[0] == len(synthetic_df)
        assert X.shape[1] >= len(NUMERIC_FEATURES)

    def test_predict_returns_known_label(self, fitted_pipeline: Pipeline, synthetic_df: pd.DataFrame) -> None:
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        preds = fitted_pipeline.predict(synthetic_df[features])
        assert set(preds).issubset(set(LABEL_CLASSES))

    def test_predict_proba_shape(self, fitted_pipeline: Pipeline, synthetic_df: pd.DataFrame) -> None:
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        proba = fitted_pipeline.predict_proba(synthetic_df[features])
        assert proba.shape == (len(synthetic_df), len(LABEL_CLASSES))
        # Each row sums to ~1
        import numpy as np
        assert all(abs(row.sum() - 1.0) < 1e-6 for row in proba)

    def test_unseen_region_does_not_raise(self, fitted_pipeline: Pipeline, synthetic_df: pd.DataFrame) -> None:
        """handle_unknown='ignore' means an unseen region gets all-zeros, no error."""
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        df2 = synthetic_df.copy()
        df2["region"] = "Atlantis"
        preds = fitted_pipeline.predict(df2[features])
        assert len(preds) == len(df2)
