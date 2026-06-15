"""
reports/reviewer.py

Agentic review of employee-submitted field reports.

Called as a FastAPI BackgroundTask immediately after submission.

Flow:
  1. Load the submitted file from disk using existing document loaders.
  2. Query the field_reports RAG pipeline to retrieve the relevant template/SOP.
  3. Send both to the LLM with a structured evaluation prompt.
  4. Parse the verdict: passed | failed | needs_hitl
  5. Update FieldReport.status + create Notifications for employee and all admins.
  6. If needs_hitl, create a HITLReview row so the admin queue surfaces it.
"""

import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.chat.database import SessionLocal
from app.chat.models import FieldReport, HITLReview, Notification, User
from app.retrieval.retriever import retrieve_with_parent_expansion
from app.llm.llm_config import llm
from app.ingestion.document_loader import _load_pdf, _load_docx, _load_txt


def run_agentic_review(report_id: str, file_path: str, report_type: str) -> None:
    """
    Entry point called by BackgroundTask.
    Opens its own DB session since it runs outside the request lifecycle.
    """
    db = SessionLocal()
    try:
        _review(db, report_id, file_path, report_type)
    except Exception as e:
        # Don't crash the server — mark the report as needs_hitl so a human picks it up.
        _fallback_to_hitl(db, report_id, reason=f"Reviewer error: {str(e)}")
    finally:
        db.close()


# ── Core review logic ─────────────────────────────────────────────────────────

def _review(db: Session, report_id: str, file_path: str, report_type: str) -> None:
    report = db.query(FieldReport).filter(FieldReport.id == report_id).first()
    if not report:
        return

    # Step 1 — Extract text from the uploaded file
    submitted_text = _extract_text(file_path)
    if not submitted_text.strip():
        _fallback_to_hitl(db, report_id, reason="Could not extract text from the uploaded file.")
        return

    # Step 2 — Retrieve the relevant template/SOP from RAG
    template_docs = retrieve_with_parent_expansion(
        question=f"{report_type} inspection report template required fields checklist",
        pipeline="field_reports",
        top_k=4,
    )

    if not template_docs:
        # No template found — can't auto-review, escalate immediately
        _fallback_to_hitl(
            db, report_id,
            reason="No matching template or SOP found in the document store for this report type."
        )
        return

    template_text = "\n\n".join(
        f"[Template Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
        for d in template_docs
    )

    # Step 3 — Build evaluation prompt and call LLM
    prompt = f"""You are a compliance reviewer for a field operations team.

An employee has submitted a completed field inspection report.
Your job is to evaluate it against the official template and SOPs retrieved below.

EVALUATION CRITERIA:
1. All mandatory fields and sections present in the template must be filled in the submission.
2. Observations, readings, or checklist items must be recorded (not left blank or marked N/A without justification).
3. No obvious internal inconsistencies (e.g. date mismatch, site ID mismatch, contradictory readings).
4. Signature or technician ID must be present.

OFFICIAL TEMPLATE / SOP REFERENCE:
{template_text}

SUBMITTED REPORT:
{submitted_text[:6000]}

Respond ONLY with a JSON object in this exact structure — no prose before or after:
{{
  "verdict": "passed" | "failed" | "needs_hitl",
  "confidence": "high" | "medium" | "low",
  "summary": "One sentence summary of the decision.",
  "issues": ["Issue 1", "Issue 2"]
}}

Rules for verdict:
- "passed": Report is complete, consistent, and meets all template requirements.
- "failed": Report has clear, specific gaps or errors that make it non-compliant.
- "needs_hitl": You are uncertain due to poor scan quality, ambiguous fields, or conflicting information.
"""

    raw = llm.invoke(prompt).content.strip()
    verdict, confidence, summary, issues = _parse_verdict(raw)

    # Step 4 — Apply verdict
    if verdict == "passed":
        _set_status(db, report, "approved", summary)
        _notify_employee(db, report, "approved", summary)
        _notify_admins(db, report, "approved", summary)

    elif verdict == "failed":
        _set_status(db, report, "rejected", summary)
        _notify_employee(db, report, "rejected", summary)
        _notify_admins(db, report, "rejected", summary)

    else:
        # needs_hitl or any unexpected value — escalate
        _fallback_to_hitl(db, report_id, reason=summary or "AI review was inconclusive.")


def _fallback_to_hitl(db: Session, report_id: str, reason: str) -> None:
    """Escalates a report to human review. Safe to call from exception handlers."""
    report = db.query(FieldReport).filter(FieldReport.id == report_id).first()
    if not report:
        return

    # Avoid creating duplicate HITLReview rows if already escalated
    existing = db.query(HITLReview).filter(HITLReview.report_id == report_id).first()
    if not existing:
        db.add(HITLReview(report_id=report_id, notes=reason))

    report.status = "needs_hitl"
    report.metadata_json = {**(report.metadata_json or {}), "hitl_reason": reason}
    db.commit()

    _notify_employee(db, report, "needs_hitl", "Your report requires manual review by an admin.")
    _notify_admins(db, report, "needs_hitl", f"Report requires manual review: {reason}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    loader_map = {
        ".pdf":  _load_pdf,
        ".docx": _load_docx,
        ".txt":  _load_txt,
        ".md":   _load_txt,
    }
    loader = loader_map.get(ext)
    if not loader:
        return ""
    docs = loader(file_path)
    return "\n\n".join(d.page_content for d in docs)


def _parse_verdict(raw: str) -> tuple:
    """Parses the LLM JSON verdict. Falls back to needs_hitl if malformed."""
    import json, re
    try:
        # Strip any accidental markdown fences
        cleaned = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(cleaned)
        return (
            data.get("verdict", "needs_hitl"),
            data.get("confidence", "low"),
            data.get("summary", ""),
            data.get("issues", []),
        )
    except Exception:
        return "needs_hitl", "low", "Could not parse AI review response.", []


def _set_status(db: Session, report: FieldReport, status: str, summary: str) -> None:
    report.status = status
    report.metadata_json = {**(report.metadata_json or {}), "ai_summary": summary}
    report.updated_at = datetime.utcnow()
    db.commit()


def _notify_employee(db: Session, report: FieldReport, event: str, message: str) -> None:
    messages = {
        "approved":   f"Your report '{report.title}' was approved by the AI reviewer.",
        "rejected":   f"Your report '{report.title}' was rejected. Reason: {message}",
        "needs_hitl": f"Your report '{report.title}' is under manual review by an admin.",
    }
    db.add(Notification(
        user_id=report.submitted_by,
        notification_type=f"report_{event}",
        message=messages.get(event, message),
        ref_type="field_report",
        ref_id=report.id,
    ))
    db.commit()


def _notify_admins(db: Session, report: FieldReport, event: str, message: str) -> None:
    admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            notification_type=f"report_{event}",
            message=f"Report '{report.title}' by {report.submitted_by_user.email}: {message}",
            ref_type="field_report",
            ref_id=report.id,
        ))
    db.commit()