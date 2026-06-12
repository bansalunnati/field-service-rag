"""
pipelines/router.py
Routes a query to the correct pipeline by name.
Called by chat/router.py query endpoint.
"""

from typing import List, Dict, Any
from app.pipelines import technical_pipeline, policy_pipeline, general_pipeline

PIPELINE_MAP = {
    "technical":  technical_pipeline.run,
    "policy":     policy_pipeline.run,
    "compliance": policy_pipeline.run,   # alias
    "general":    general_pipeline.run,
    "faq":        general_pipeline.run,  # alias
}


def route_query(
    question: str,
    pipeline_name: str,
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    handler = PIPELINE_MAP.get(pipeline_name.lower(), policy_pipeline.run)
    return handler(question=question, history=history)
