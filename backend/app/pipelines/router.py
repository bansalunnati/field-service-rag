"""
pipelines/router.py

Routes a query to the correct pipeline module by name.
Called by chat/router.py for every query the user sends.

Pipeline keys (updated in Phase 1):
  equipment    → equipment_pipeline.run
  safety       → safety_pipeline.run
  field_reports → field_reports_pipeline.run

The comparison agent (Phase 7) will extend this router to support
multi-pipeline queries when the admin uses Compare mode.
"""

from typing import List, Dict, Any
from app.pipelines import equipment_pipeline, safety_pipeline, field_reports_pipeline

PIPELINE_MAP = {
    "equipment":     equipment_pipeline.run,
    "safety":        safety_pipeline.run,
    "field_reports": field_reports_pipeline.run,
}

# Human-readable display names used in API responses and frontend labels.
PIPELINE_LABELS = {
    "equipment":     "Equipment & Assets",
    "safety":        "Safety & Compliance",
    "field_reports": "Field Reports",
}

# Valid pipeline keys — used by access control checks in chat/router.py.
VALID_PIPELINES = set(PIPELINE_MAP.keys())


def route_query(
    question: str,
    pipeline_name: str,
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Dispatches a question to the correct pipeline handler.

    Args:
        question      : The user's query string.
        pipeline_name : One of 'equipment', 'safety', 'field_reports'.
        history       : Recent conversation turns for multi-turn memory.

    Returns:
        dict with keys 'answer' (str) and 'citations' (list).

    Raises:
        ValueError if pipeline_name is not in VALID_PIPELINES.
    """
    handler = PIPELINE_MAP.get(pipeline_name.lower())

    if not handler:
        raise ValueError(
            f"Unknown pipeline '{pipeline_name}'. "
            f"Valid options are: {', '.join(sorted(VALID_PIPELINES))}"
        )

    return handler(question=question, history=history)


def get_pipeline_label(pipeline_name: str) -> str:
    """Returns the human-readable label for a pipeline key."""
    return PIPELINE_LABELS.get(pipeline_name.lower(), pipeline_name.title())
