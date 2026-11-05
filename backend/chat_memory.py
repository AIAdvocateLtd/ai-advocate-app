"""Recent conversation memory for Lex chat (shared by regular and live-typed chat)."""
from typing import Callable, List, Tuple

MAX_EXCHANGES = 12          # most recent question+answer exchanges loaded
CHAR_BUDGET = 24000         # soft cap on history size sent to the AI
ALWAYS_KEEP = 4             # newest exchanges are never dropped for size


async def load_recent_history(db, user_id: str, session_id: str, decrypt: Callable[[str], str]) -> Tuple[List[dict], int]:
    """Returns (chronological list of {user, assistant} exchanges, number of earlier exchanges omitted).
    Filtered by BOTH user_id and session_id so history can never cross users or conversations."""
    q = {"user_id": user_id, "session_id": session_id}
    total = await db.conversations.count_documents(q)
    docs = await db.conversations.find(
        q, {"_id": 0, "user_message": 1, "assistant_response": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(length=MAX_EXCHANGES)
    newest_first = []
    for d in docs:
        try:
            um, ar = decrypt(d.get("user_message")) or "", decrypt(d.get("assistant_response")) or ""
        except Exception:
            continue
        if um or ar:
            newest_first.append({"user": um, "assistant": ar})
    kept, used = [], 0
    for i, ex in enumerate(newest_first):
        size = len(ex["user"]) + len(ex["assistant"])
        if i >= ALWAYS_KEEP and used + size > CHAR_BUDGET:
            break
        kept.append(ex)
        used += size
    kept.reverse()
    return kept, max(0, total - len(kept))


def history_note(omitted: int) -> str:
    if not omitted:
        return ""
    return (f"\n\nCONVERSATION MEMORY NOTE: {omitted} earlier exchange(s) in this conversation are not included above. "
            "If the user refers to something you cannot see, say plainly that you can't see that earlier part and ask "
            "them to repeat the key details. Never pretend to remember it.")


def to_messages(exchanges: List[dict]) -> List[dict]:
    out = []
    for ex in exchanges:
        if ex["user"]:
            out.append({"role": "user", "content": ex["user"]})
        if ex["assistant"]:
            out.append({"role": "assistant", "content": ex["assistant"]})
    return out
