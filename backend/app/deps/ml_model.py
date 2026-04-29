"""ML classifier dependency.

Implemented in Stage 3 (loader); used from Stage 5 onwards.

Public surface (planned):
    async def get_classifier(request: Request) -> Pipeline:
        return request.app.state.classifier

The joblib is loaded ONCE in lifespan startup (see
`ml/classifier_loader.py`) and parked on `app.state.classifier`. Loading
per request is the brief's named anti-pattern.
"""
