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
_site = contextvars.ContextVar("ai_call_site", default="")
_state = {"db": None, "rates": {}, "default_rate": (2.50, 12.00), "installed": False}
# Estimator calibrated 5 Nov 2026 against provider-measured prompt tokens (see /app/memory/stage2_token_calibration.md):
# Claude 5.5 counts ~1.3-1.6x the o200k tokenizer for English/legal/JSON, ~1.9x Welsh, ~2.3x Urdu/Arabic; GPT-5.2 ~1.0x.
TOKEN_FACTORS = {"anthropic": 1.7, "openai": 1.05, "gemini": 1.3}
NON_LATIN_FACTOR = {"anthropic": 2.4, "openai": 1.1, "gemini": 1.5}
PER_MESSAGE_OVERHEAD = 8
ESTIMATE_SOURCE = "estimated_tokenizer_v2"
_enc = {}
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


def mark_fallback(call_site: str = "") -> None:
    _attempt.set("fallback")
    if call_site:
        _site.set(call_site)


def estimate_tokens(chars_or_text, provider: str, n_messages: int = 1) -> int:
    """Conservative token estimate when the provider did not report usage."""
    if isinstance(chars_or_text, int):
        base, non_latin = chars_or_text / 4, 0.0
    else:
        text = chars_or_text or ""
        try:
            if "e" not in _enc:
                import tiktoken
                _enc["e"] = tiktoken.get_encoding("o200k_base")
            base = len(_enc["e"].encode(text, disallowed_special=()))
        except Exception:
            base = len(text) / 4
        non_latin = sum(1 for ch in text if ord(ch) > 0x24F) / max(1, len(text))
    table = NON_LATIN_FACTOR if non_latin > 0.3 else TOKEN_FACTORS
    return int(base * table.get(provider, 1.7) + 0.999) + PER_MESSAGE_OVERHEAD * max(0, n_messages)


def _cost(provider: str, model: str, tin: int, tout: int, alt_model: str = None):
    rate = _state["rates"].get((provider, model))
    if rate is None and alt_model:
        rate = _state["rates"].get((provider, alt_model))
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
           units: dict = None, input_text: str = None, output_text: str = None, n_messages: int = 1,
           finish_reason: str = None, reasoning_tokens: int = None) -> None:
    db = _state["db"]
    if db is None:
        return
    try:
        no_tokens = provider == "tavily" or (cost_source or "").startswith("unpriced_audio")
        if no_tokens:
            tokens_in, tokens_out = 0, 0
        measured = tokens_in is not None and tokens_out is not None
        if measured:
            tin, tout = tokens_in, tokens_out
        else:
            tin = max(1, estimate_tokens(input_text if input_text is not None else int(input_chars), provider, n_messages))
            tout = estimate_tokens(output_text if output_text is not None else int(output_chars), provider, 0) \
                if (output_text or output_chars) else 0
        model_actual = model_actual or model_requested
        if cost_gbp is None:
            cost_gbp = _cost(provider, model_actual, tin, tout, model_requested) if status == "ok" else 0.0
            cost_source = cost_source or ("measured_tokens_x_rate_table" if measured else "estimated_tokens_x_rate_table")
        uid, tier = _user.get()
        doc = {
            "schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(), "request_id": _request_id.get(),
            "user_id": uid, "tier": tier, "feature": _feature.get(), "call_site": call_site or _site.get(),
            "provider": provider, "model": model_actual, "model_requested": model_requested, "model_actual": model_actual,
            "attempt": _attempt.get(), "status": status, "latency_ms": int(latency_ms),
            "input_chars": int(input_chars), "output_chars": int(output_chars),
            "tokens_in": tin, "tokens_out": tout, "tokens_source": ("not_applicable" if no_tokens else "provider") if measured else ESTIMATE_SOURCE,
            "measured": bool(measured and not no_tokens),
            "cost_gbp": cost_gbp, "cost_source": cost_source, "units": units or None,
            "finish_reason": finish_reason, "reasoning_tokens": reasoning_tokens,
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
    orig_exec = LlmChat._execute_completion

    async def _execute_completion(self, messages):
        resp = await orig_exec(self, messages)
        try:
            u = getattr(resp, "usage", None)
            det = getattr(u, "completion_tokens_details", None)
            self._aiu_usage = (getattr(u, "prompt_tokens", None), getattr(u, "completion_tokens", None), getattr(resp, "model", None),
                               getattr(resp.choices[0], "finish_reason", None) if getattr(resp, "choices", None) else None,
                               getattr(det, "reasoning_tokens", None) if det else None)
        except Exception:
            self._aiu_usage = None
        return resp

    LlmChat._execute_completion = _execute_completion

    async def send_message(self, user_message):
        t0 = time.monotonic()
        self._aiu_usage = None
        msgs = getattr(self, "messages", None) or [{"content": getattr(self, "system_message", "") or ""}]
        msgs = [m for m in msgs if isinstance(m, dict)]
        in_text = "\n".join(str(m.get("content", "")) for m in msgs) + "\n" + (getattr(user_message, "text", "") or "") \
            + " x" * (1000 * len(getattr(user_message, "file_contents", None) or []))
        in_chars = sum(len(str(m.get("content", ""))) for m in msgs) + _msg_chars(user_message)
        site = _call_site(getattr(self, "session_id", ""))
        try:
            out = await orig_send(self, user_message)
        except Exception:
            record(provider=self.provider, model_requested=self.model, input_chars=in_chars, status="error",
                   latency_ms=(time.monotonic() - t0) * 1000, call_site=site, input_text=in_text, n_messages=len(msgs) + 1)
            raise
        tin, tout, model_actual, finish, reasoning = (getattr(self, "_aiu_usage", None) or (None,) * 5)
        out_text = out if isinstance(out, str) else ""
        record(provider=self.provider, model_requested=self.model, model_actual=model_actual, input_chars=in_chars,
               output_chars=len(out_text), tokens_in=tin, tokens_out=tout, latency_ms=(time.monotonic() - t0) * 1000,
               call_site=site, input_text=in_text, output_text=out_text, n_messages=len(msgs) + 1,
               finish_reason=finish, reasoning_tokens=reasoning)
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
