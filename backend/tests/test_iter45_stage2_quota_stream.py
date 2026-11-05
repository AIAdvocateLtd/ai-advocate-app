"""Iter45 extra: streaming + quota exhausted + high-risk keyword (1 Lex call). Restores tavily count."""
from datetime import datetime, timezone
from tests.test_iter45_stage2_live import DB, chat, MARK, users  # noqa: F401


def test_stream_quota_exhausted_high_risk_keyword(users):  # noqa: F811
    _, h = users["a"]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    orig = DB.tavily_usage.find_one({"month": month}, {"_id": 0})
    DB.tavily_usage.update_one({"month": month}, {"$set": {"count": 100000}}, upsert=True)
    try:
        r = chat(h, "Fictional test: my landlord in Leeds served me a section 21 notice and says I must leave by Friday "
                    "or he will evict me. Is the notice valid?", stream=True)
    finally:
        if orig:
            DB.tavily_usage.update_one({"month": month}, {"$set": {"count": orig.get("count", 0)}})
        else:
            DB.tavily_usage.delete_one({"month": month})
    t = r["response"]
    print("STATUS", r["research_status"], "\nHEAD", t[:300], "\nTAIL", t[-600:])
    assert r["research_status"] == "quota_exhausted"
    assert "couldn't check current official sources" in t
    assert not MARK.search(t)
    assert "[CONFIDENCE: HIGH]" not in t
    assert r["citations"] == []
