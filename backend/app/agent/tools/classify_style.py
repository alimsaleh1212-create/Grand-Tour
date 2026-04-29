"""Tool 2 — classify_style (trained sklearn Pipeline).

Implemented in Stage 5 (after Stage 3 produces the joblib).

Schemas (planned):
    class DestinationFeatures(BaseModel):
        country: str
        region: str
        avg_temp_c: float
        cost_per_day_usd: float
        safety_index: float
        activity_density_index: float
        nightlife_score: float
        cultural_sites_count: int
        nature_score: float
        # ... finalised in Stage 3.2

    class ClassifyInput(BaseModel):
        destination_name: str
        features: DestinationFeatures

    class ClassifyResult(BaseModel):
        destination_name: str
        predicted_style: Literal[
            "Adventure", "Relaxation", "Culture", "Budget", "Luxury", "Family",
        ]
        confidence: float = Field(ge=0.0, le=1.0)
        all_probabilities: dict[str, float]

Class (planned):
    class ClassifyStyleTool(BaseTool[ClassifyInput, ClassifyResult]):
        name = "classify_style"

        def __init__(self, classifier: Pipeline, label_classes: list[str]): ...

        async def run(self, args: ClassifyInput) -> ClassifyResult:
            # Wrap the synchronous predict_proba in a thread executor so
            # we don't block the event loop. The model is the lifespan
            # singleton — never re-loaded here.
            ...

Notes:
    * Feature extraction from RAG output happens in the cheap-model node
      BEFORE this tool — that's why classify_style takes a typed
      DestinationFeatures, not raw text.
"""
