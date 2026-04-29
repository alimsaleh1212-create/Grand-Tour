"""Training package — scripts and modules used to build the classifier.

Pipeline (Stage 3):

    data_loader.py       Read labeled destinations CSV from ml/data/.
                         Compute and return the dataset hash for
                         reproducibility logging.
    feature_pipeline.py  Build a sklearn `Pipeline` whose first step is
                         a `ColumnTransformer` doing imputation +
                         scaling + one-hot encoding. Preprocessing is
                         INSIDE the pipeline — never pre-transformed —
                         so cross-validation cannot leak.
    train.py             Compare 3 classifiers (LogReg, RandomForest,
                         GradientBoosting) under StratifiedKFold(k=5).
                         Report accuracy + macro-F1 mean ± std + per-
                         class metrics. Compare against a stratified
                         DummyClassifier baseline.
    tune.py              GridSearchCV on the winner with the same CV
                         splitter; document search space.
    evaluate.py          Per-class precision / recall / F1, confusion
                         matrix on the held-out test split.
    persist_model.py     Save the final fitted Pipeline as joblib AND
                         append a row to results/results.csv with full
                         provenance (timestamp, params, metrics, dataset
                         hash, random_state).

`random_state=42` is set on every stochastic call (train_test_split,
cross-validation, model init) for reproducibility.
"""
