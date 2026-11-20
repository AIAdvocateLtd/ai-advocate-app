import os
from urllib.parse import urlparse

import pytest

# Automated tests deliberately simulate failures; keep them out of Sentry alerting.
os.environ["SENTRY_DSN"] = ""

# AIA_NO_PAID=1 blocks every paid or live-app call: real AI models, Tavily search, and HTTP to the preview/live app.
# Free public sources (legislation.gov.uk, acas.org.uk) stay allowed. Tests that mock these calls are unaffected.
NO_PAID = os.environ.get("AIA_NO_PAID") == "1"
LEGACY_LIVE = {"test_lex_routing.py", "test_deep_think_auto_router.py"}


def _blocked_hosts():
    hosts = {"api.tavily.com", "aiadvocate.co.uk", "www.aiadvocate.co.uk", "localhost", "127.0.0.1", "0.0.0.0"}
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                hosts.add(urlparse(line.split("=", 1)[1].strip()).hostname)
    except OSError:
        pass
    return hosts


def pytest_ignore_collect(collection_path, config):
    return NO_PAID and collection_path.name in LEGACY_LIVE


@pytest.fixture(autouse=True)
def _no_paid_calls(monkeypatch):
    if not NO_PAID:
        yield
        return
    import httpx
    import requests
    from emergentintegrations.llm.chat import LlmChat

    blocked = _blocked_hosts()

    async def no_llm(self, *a, **kw):
        raise RuntimeError("AIA_NO_PAID: real AI call blocked in tests")

    def guard(url):
        if urlparse(str(url)).hostname in blocked:
            raise RuntimeError(f"AIA_NO_PAID: call to {url} blocked in tests")

    orig_async, orig_sync, orig_req = httpx.AsyncClient.send, httpx.Client.send, requests.Session.send

    async def a_send(self, request, *a, **kw):
        guard(request.url)
        return await orig_async(self, request, *a, **kw)

    def s_send(self, request, *a, **kw):
        guard(request.url)
        return orig_sync(self, request, *a, **kw)

    def r_send(self, request, *a, **kw):
        guard(request.url)
        return orig_req(self, request, *a, **kw)

    monkeypatch.setattr(LlmChat, "send_message", no_llm)
    monkeypatch.setattr(LlmChat, "send_message_multimodal_response", no_llm)
    monkeypatch.setattr(httpx.AsyncClient, "send", a_send)
    monkeypatch.setattr(httpx.Client, "send", s_send)
    monkeypatch.setattr(requests.Session, "send", r_send)
    yield


@pytest.fixture(autouse=True)
def _stub_new_official_research(request, monkeypatch):
    """Older suites assert exact source lists; topic/EU research is covered by tests/test_legal_research.py."""
    if request.module.__name__.endswith(("test_legal_research", "test_global_research")):
        yield
        return
    try:
        import legal_research, eu_law, rag, global_law
    except Exception:
        yield
        return

    async def no_global(*a, **k):
        return {"sources": [], "notes": [], "tavily_calls": 0, "national_ok": {}, "meta": {}}
    monkeypatch.setattr(global_law, "research", no_global)
    monkeypatch.setattr(global_law, "plan_for", lambda m, c, s: {"primary": "GB", "all": [], "us_state": None})

    async def no_topic(*a, **k):
        return {"sources": [], "topics": [], "status": "not_uk"}

    async def no_eu(*a, **k):
        return {"sources": [], "status": "not_wanted", "note": ""}
    monkeypatch.setattr(legal_research, "topic_sources", no_topic)
    monkeypatch.setattr(legal_research, "match_topics", lambda t: [])
    monkeypatch.setattr(eu_law, "eu_sources", no_eu)
    monkeypatch.setattr(eu_law, "national_gap_note", lambda c: "")
    rag._quota_until[0] = 0
    yield
    rag._quota_until[0] = 0
