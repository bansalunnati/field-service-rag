"""
One-off backfill for the "Jan 1" chat sidebar bug.

append_message() used to write msg.created_at into chat_sessions.updated_at
before the insert was flushed, so it wrote NULL instead of the real
timestamp (see history_service.py). That left chat_sessions.updated_at NULL
for any session that ever received a message, which the frontend's
`new Date(null)` rendered as the epoch ("Jan 1").

The fix in history_service.py stops new rows from getting corrupted; this
script repairs rows already in the database. Safe to re-run — it's a no-op
once every session has a non-null updated_at.

Run from backend/: python -m scripts.backfill_chat_session_timestamps
"""

from sqlalchemy import text
from app.chat.database import engine


def main():
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE chat_sessions
            SET updated_at = COALESCE(
                (SELECT MAX(created_at) FROM chat_messages WHERE chat_messages.session_id = chat_sessions.id),
                chat_sessions.created_at
            )
            WHERE updated_at IS NULL
        """))
        print(f"Backfilled {result.rowcount} chat_sessions row(s) with NULL updated_at.")


if __name__ == "__main__":
    main()
