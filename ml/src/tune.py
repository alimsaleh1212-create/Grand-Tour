"""Hyperparameter tuning on the winning model via GridSearchCV.

HOW TO RUN
----------
    cd ml/
    uv run python src/tune.py

WHAT THIS DOES
--------------
1. Loads the dataset.
2. Splits 80% train / 20% held-out test (stratified, random_state=42).
3. Runs GridSearchCV on the training split with StratifiedKFold(5).
4. Prints the best params and CV score.
5. Evaluates the best pipeline on the held-out test set.
6. Persists the fitted pipeline to ml/models/.
7. Appends a result row to ml/results/results.csv.

SEARCH SPACES AND WHY
----------------------

LogisticRegression search space:
    C (regularisation strength): [0.01, 0.1, 1.0, 10.0]
        We search C because the dataset (160 rows, 18 features after OHE)
        is small enough to overfit with weak regularisation (large C).
        Typical search covers 3 orders of magnitude to identify the cliff.

    solver: ["lbfgs", "saga"]
        lbfgs is efficient for small datasets with L2 penalty.
        saga supports L1 which may zero out irrelevant features.

RandomForestClassifier search space:
    n_estimators: [100, 200, 400]
        More trees reduces variance; 400 is the practical limit before
        diminishing returns on a 160-row dataset.
    max_depth: [None, 5, 10]
        None = full depth (low bias, high variance). Shallow trees reduce
        overfit on small datasets.
    min_samples_leaf: [1, 3, 5]
        Controls leaf size — small datasets benefit from larger leaves.

HistGradientBoostingClassifier search space:
    max_iter: [100, 200, 300]
        More iterations reduces bias but risks overfit.
    max_depth: [None, 3, 5]
        Shallow trees generalise better on small datasets.
    learning_rate: [0.05, 0.1, 0.2]
        Classic learning_rate / n_estimators tradeoff.
    min_samples_leaf: [10, 20, 30]
        HistGB uses a different internal mechanism; larger leaves help.

The script auto-selects the search space based on which model is declared
WINNER_MODEL below. Change WINNER_MODEL after running train.py.
"""

from __future__ import annotations

import pathlib

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split

from src.data_loader import LABEL_CLASSES, TARGET_COLUMN, compute_dataset_hash, load_raw
from src.feature_pipeline import CATEGORICAL_FEATURES, NUMERIC_FEATURES, build_pipeline
from src.persist_model import persist_model

RANDOM_STATE = 42
N_SPLITS = 5

# ── Change this to the winner from train.py output ────────────────────────────
# Options: "LogisticRegression" | "RandomForestClassifier" | "HistGradientBoosting"
WINNER_MODEL = "LogisticRegression"

_PARAM_GRIDS: dict[str, tuple[object, dict[str, list[object]]]] = {
    "LogisticRegression": (
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_STATE,
        ),
        {
            "classifier__C": [0.01, 0.1, 1.0, 10.0],
            "classifier__solver": ["lbfgs", "saga"],
        },
    ),
    "RandomForestClassifier": (
        RandomForestClassifier(
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        {
            "classifier__n_estimators": [100, 200, 400],
            "classifier__max_depth": [None, 5, 10],
            "classifier__min_samples_leaf": [1, 3, 5],
        },
    ),
    "HistGradientBoosting": (
        HistGradientBoostingClassifier(random_state=RANDOM_STATE),
        {
            "classifier__max_iter": [100, 200, 300],
            "classifier__max_depth": [None, 3, 5],
            "classifier__learning_rate": [0.05, 0.1, 0.2],
            "classifier__min_samples_leaf": [10, 20, 30],
        },
    ),
}


def tune() -> pathlib.Path:
    """Run GridSearchCV, evaluate on held-out test, persist the best pipeline."""
    df = load_raw()
    dataset_hash = compute_dataset_hash(df)
    features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[features]
    y = df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    estimator, param_grid = _PARAM_GRIDS[WINNER_MODEL]
    pipe = build_pipeline(estimator)

    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        pipe,
        param_grid,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
        verbose=1,
    )
    search.fit(X_train, y_train)

    print(f"\nBest params: {search.best_params_}")
    print(f"Best CV F1-macro: {search.best_score_:.4f}")

    # Evaluate the best pipeline on the held-out test set.
    from src.evaluate import evaluate_on_holdout

    baseline = DummyClassifier(strategy="stratified", random_state=RANDOM_STATE)
    baseline.fit(X_train, y_train)

    test_eval = evaluate_on_holdout(
        search.best_estimator_, X_test, y_test, baseline, LABEL_CLASSES
    )
    print(f"\nTest-set accuracy: {test_eval['accuracy']:.4f}")
    print(f"Test-set F1-macro: {test_eval['f1_macro']:.4f}")
    print(f"Baseline accuracy: {test_eval['baseline_accuracy']:.4f}")

    # Persist.
    out_path = persist_model(
        fitted_pipeline=search.best_estimator_,
        model_name=WINNER_MODEL,
        best_params=search.best_params_,
        cv_f1_macro=search.best_score_,
        test_eval=test_eval,
        dataset_hash=dataset_hash,
    )
    print(f"\nModel saved → {out_path}")
    return out_path


if __name__ == "__main__":
    tune()
