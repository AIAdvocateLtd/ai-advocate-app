"""Central AI usage meter. Records one row per AI/research call in db.llm_usage (same collection and core
fields the existing admin spend report reads). Never stores message or document text — only sizes/counts.
Recording failures are swallowed so they can never block a customer request."""
import asyncio
import contextvars
import logging
import re
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
SCHEMA = 2
_feature = contextvars.ContextVar("ai_feature", default="unknown")
_request_id = contextvars.ContextVar("ai_request_id", default=None)
_user = contextvars.ContextVar("ai_user", default=(None, None))
_attempt = contextvars.ContextVar("ai_attempt", default="primary")
_state = {"db": None, "rates": {}, "default_rate": (2.50, 12.00), "installed": False}
TAVILY_GBP_PER_CREDIT = 0.0063  # estimate (~$0.008/credit pay-as-you-go); confirm against your Tavily plan
_UUIDISH = re.compile(r"^[0-9a-f]{8,}(-[0-9a-f]{4,})*$|^\d+$", re.I)


def feature_from_path(path: str) -> str:
    parts = [p for p in (path or "").split("/") if p and p != "api" and not _UUIDISH.match(p)]
    return "_".join(parts)[:60] or "unknown"


def begin_request(path: str) -> None:
    _feature.set(feature_from_path(path))
    _request_id.set(str(uuid.uuid4()))
    _attempt.set("primary")


def set_user(user: dict) -> None:
    if user:
        _user.set((user.get("id"), user.get("tier")))


def mark_fallback() -> None:
    _attempt.set("fallback")


def _cost(provider: str, model: str, tin: int, tout: int):
    rate = _state["rates"].get((provider, model))
    if rate is None:
        rate = _state["default_rate"]
    return round((tin * rate[0] + tout * rate[1]) / 1_000_000, 6)


def _call_site(session_id: str) -> str:
    s = (session_id or "").strip()
    if not s or _UUIDISH.match(s):
        return ""
    return re.split(r"[-_:][0-9a-f]{6,}", s, maxsplit=1)[0][:40]


def record(*, provider: str, model_requested: str, model_actual: str = None, input_chars: int = 0,
           output_chars: int = 0, tokens_in: int = None, tokens_out: int = None, latency_ms: int = 0,
           status: str = "ok", call_site: str = "", cost_gbp: float = None, cost_source: str = None,
           units: dict = None) -> None:
    db = _state["db"]
    if db is None:
        return
    try:
        if provider == "tavily":
            tokens_in, tokens_out = 0, 0
        measured = tokens_in is not None and tokens_out is not None
        tin = tokens_in if measured else max(1, input_chars // 4)
        tout = tokens_out if measured else max(0, output_chars // 4)
        model_actual = model_actual or model_requested
        if cost_gbp is None:
            cost_gbp = _cost(provider, model_actual, tin, tout) if status == "ok" else 0.0
            cost_source = cost_source or "estimated_from_rate_table"
        uid, tier = _user.get()
        doc = {
            "schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(), "request_id": _request_id.get(),
            "user_id": uid, "tier": tier, "feature": _feature.get(), "call_site": call_site,
            "provider": provider, "model": model_actual, "model_requested": model_requested, "model_actual": model_actual,
            "attempt": _attempt.get(), "status": status, "latency_ms": int(latency_ms),
            "input_chars": int(input_chars), "output_chars": int(output_chars),
            "tokens_in": tin, "tokens_out": tout, "tokens_source": ("not_applicable" if provider == "tavily" else "provider") if measured else "estimated_chars_div_4",
            "cost_gbp": cost_gbp, "cost_source": cost_source, "units": units or None,
        }
        asyncio.get_running_loop().create_task(_insert(doc))
    except Exception as e:
        logger.warning(f"ai_usage record skipped: {e!r}")


async def _insert(doc):
    try:
        await _state["db"].llm_usage.insert_one(doc)
    except Exception as e:
        logger.warning(f"ai_usage insert failed (non-fatal): {e!r}")


def _msg_chars(msg) -> int:
    n = len(getattr(msg, "text", "") or "")
    files = getattr(msg, "file_contents", None) or []
    return n + 4000 * len(files)  # attached files: unknown size → flat estimate per file


def install(db, rates: dict) -> None:
    """Patch the AI client classes once so every call site in the app is metered automatically."""
    _state["db"], _state["rates"] = db, rates
    if _state["installed"]:
        return
    from emergentintegrations.llm.chat import LlmChat
    from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText
    from emergentintegrations.llm.openai.text_to_speech import OpenAITextToSpeech

    orig_send = LlmChat.send_message

    async def send_message(self, user_message):
        t0 = time.monotonic()
        msgs = getattr(self, "messages", None) or [{"content": getattr(self, "system_message", "") or ""}]
        in_chars = sum(len(str(m.get("content", ""))) for m in msgs if isinstance(m, dict)) + _msg_chars(user_message)
        try:
            out = await orig_send(self, user_message)
        except Exception:
            record(provider=self.provider, model_requested=self.model, input_chars=in_chars, status="error",
                   latency_ms=(time.monotonic() - t0) * 1000, call_site=_call_site(getattr(self, "session_id", "")))
            raise
        record(provider=self.provider, model_requested=self.model, input_chars=in_chars,
               output_chars=len(out or "") if isinstance(out, str) else 0,
               latency_ms=(time.monotonic() - t0) * 1000, call_site=_call_site(getattr(self, "session_id", "")))
        return out

    LlmChat.send_message = send_message

    def _wrap_audio(cls, name, provider, model):
        orig = getattr(cls, name, None)
        if orig is None:
            return

        async def wrapped(self, *a, **kw):
            t0 = time.monotonic()
            status = "ok"
            try:
                return await orig(self, *a, **kw)
            except Exception:
                status = "error"
                raise
            finally:
                record(provider=provider, model_requested=kw.get("model") or model, status=status,
                       latency_ms=(time.monotonic() - t0) * 1000, cost_gbp=0.0, cost_source="unpriced_audio",
                       units={"chars": len(str(kw.get("text") or ""))} if "text" in kw else None)
        setattr(cls, name, wrapped)

    _wrap_audio(OpenAISpeechToText, "transcribe", "openai", "whisper-1")
    _wrap_audio(OpenAITextToSpeech, "generate_speech", "openai", "tts-1")
    _state["installed"] = True
