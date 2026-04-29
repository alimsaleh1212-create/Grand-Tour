"""Runtime ML — loader for the trained classifier joblib.

The training pipeline lives in the top-level `ml/` package; this submodule
is the runtime-side counterpart that the FastAPI app uses to load and
serve predictions from the saved model.

Modules:
    classifier_loader.py   load_classifier() — called once in lifespan
                           startup. Returns the sklearn Pipeline (joblib)
                           which the agent's classify_style tool calls.
"""
