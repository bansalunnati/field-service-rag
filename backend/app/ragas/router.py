"""
ragas/router.py

Admin-only RAGAS evaluation endpoints.

POST /api/ragas/evaluate/{query_log_id}  — run metrics, store result
GET  /api/ragas/scores                   — paginated list
GET  /api/ragas/summary                  — avg per metric
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.auth_service import TokenData, require_permission
from app.chat.database import get_db
from app.chat.models import QueryLog, RAGASScore

router = APIRouter(prefix="/api/ragas", tags=["ragas"])


def _require_admin(user: TokenData = Depends(require_permission("manage_users"))) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _run_ragas(question: str, answer: str, contexts: list[str], ground_truth: Optional[str]) -> dict:
    """
    Run RAGAS metrics synchronously. Returns a dict of metric_name -> float|None.
    Raises RuntimeError if RAGAS cannot be imported or the LLM is not configured.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
    except ImportError as e:
        raise RuntimeError(f"RAGAS dependencies not installed: {e}")

    metrics = [faithfulness, answer_relevancy, context_precision]

    has_ground_truth = bool(ground_truth and ground_truth.strip())

    if has_ground_truth:
        try:
            from ragas.metrics import context_recall
            metrics.append(context_recall)
        except ImportError:
            has_ground_truth = False

    row = {
        "question": [question],
        "answer": [answer],
        "contexts": [contexts if contexts else [""]],
    }
    if has_ground_truth:
        row["ground_truth"] = [ground_truth]

    ds = Dataset.from_dict(row)
    result = evaluate(ds, metrics=metrics)
    scores = result.to_pandas().iloc[0].to_dict()

    return {
        "faithfulness":      scores.get("faithfulness"),
        "answer_relevancy":  scores.get("answer_relevancy"),
        "context_precision": scores.get("context_precision"),
        "context_recall":    scores.get("context_recall") if has_ground_truth else None,
    }


# ── Evaluate one query log entry ────────────────────────────────────────────────

@router.post("/evaluate/{query_log_id}")
def evaluate_query(
    query_log_id: str,
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    log = db.query(QueryLog).filter(QueryLog.id == query_log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="QueryLog not found")
    if not log.answer:
        raise HTTPException(status_code=422, detail="QueryLog has no answer to evaluate")

    # Build contexts from chunk_ids stored as citation source strings
    contexts = [str(c) for c in (log.chunk_ids or [])] or [""]

    try:
        scores = _run_ragas(
            question=log.question,
            answer=log.answer,
            contexts=contexts,
            ground_truth=log.ground_truth,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Upsert — overwrite if already evaluated
    existing = db.query(RAGASScore).filter(RAGASScore.query_log_id == query_log_id).first()
    if existing:
        existing.faithfulness      = str(scores["faithfulness"])      if scores["faithfulness"]      is not None else None
        existing.answer_relevancy  = str(scores["answer_relevancy"])  if scores["answer_relevancy"]  is not None else None
        existing.context_precision = str(scores["context_precision"]) if scores["context_precision"] is not None else None
        existing.context_recall    = str(scores["context_recall"])    if scores["context_recall"]    is not None else None
        row = existing
    else:
        row = RAGASScore(
            query_log_id       = query_log_id,
            faithfulness       = str(scores["faithfulness"])      if scores["faithfulness"]      is not None else None,
            answer_relevancy   = str(scores["answer_relevancy"])  if scores["answer_relevancy"]  is not None else None,
            context_precision  = str(scores["context_precision"]) if scores["context_precision"] is not None else None,
            context_recall     = str(scores["context_recall"])    if scores["context_recall"]    is not None else None,
        )
        db.add(row)

    db.commit()
    db.refresh(row)

    return _score_to_dict(row, log)


# ── Paginated list ───────────────────────────────────────────────────────────────

@router.get("/scores")
def list_scores(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    q = (
        db.query(RAGASScore)
        .order_by(RAGASScore.created_at.desc())
    )
    total = q.count()
    rows = q.offset((page - 1) * limit).limit(limit).all()

    items = []
    for row in rows:
        log = db.query(QueryLog).filter(QueryLog.id == row.query_log_id).first()
        items.append(_score_to_dict(row, log))

    return {"total": total, "page": page, "items": items}


# ── Summary averages ─────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    def _avg(col):
        # Stored as string; cast to float in Python for portability
        rows = db.query(col).filter(col.isnot(None)).all()
        vals = []
        for (v,) in rows:
            try:
                vals.append(float(v))
            except (ValueError, TypeError):
                pass
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "total_evaluations":  db.query(func.count(RAGASScore.id)).scalar() or 0,
        "faithfulness":       _avg(RAGASScore.faithfulness),
        "answer_relevancy":   _avg(RAGASScore.answer_relevancy),
        "context_precision":  _avg(RAGASScore.context_precision),
        "context_recall":     _avg(RAGASScore.context_recall),
    }


# ── Helper ───────────────────────────────────────────────────────────────────────

def _score_to_dict(row: RAGASScore, log: Optional[QueryLog]) -> dict:
    def _f(v):
        try:
            return round(float(v), 4) if v is not None else None
        except (ValueError, TypeError):
            return None

    return {
        "id":                row.id,
        "query_log_id":      row.query_log_id,
        "question":          log.question if log else None,
        "pipeline":          log.pipeline if log else None,
        "faithfulness":      _f(row.faithfulness),
        "answer_relevancy":  _f(row.answer_relevancy),
        "context_precision": _f(row.context_precision),
        "context_recall":    _f(row.context_recall),
        "created_at":        row.created_at.isoformat() if row.created_at else None,
    }
