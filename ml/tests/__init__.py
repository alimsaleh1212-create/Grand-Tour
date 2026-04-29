"""ML training tests.

What we test (per AIE §9 + the project brief):
    * Pipeline transforms a synthetic sample correctly (no NaN out, no
      leakage).
    * Each candidate classifier predicts a sample without crashing.
    * results.csv format is parseable and contains every required column.
    * Joblib loads, model.predict_proba is deterministic given a fixed
      random_state.
    * Re-running training on the same dataset yields identical metrics
      (reproducibility).
"""
