"""Output-budget guard for Claude 5.5 models: their hidden reasoning shares max_tokens with the visible reply."""

# Measured 5 Nov 2026 (preview): Haiku 5.5 honours thinking=disabled; Sonnet 5.5 ignores it but honours a (soft) budget.
SONNET_BUDGET = {False: 1024, True: 1500}
SONNET_MAX = {False: 2600, True: 4000}


def gen_params(model_id: str, max_tok: int, deep_think: bool = False) -> tuple:
    """Returns (max_tokens, extra litellm params) for a Lex reply. Model choice is unchanged."""
    if model_id == "claude-haiku-5-5":
        return max_tok, {"extra_body": {"thinking": {"type": "disabled"}}}
    if model_id == "claude-sonnet-5-5":
        return SONNET_MAX[bool(deep_think)], {"extra_body": {"thinking": {"type": "enabled", "budget_tokens": SONNET_BUDGET[bool(deep_think)]}}}
    return max_tok, {}


# Free-tier only: tested 5 Nov 2026 — 6/6 complete at the unchanged 1,200 cap (vs 3/6 without), ~11% fewer tokens.
CONCISE_SUFFIX = ("\n\n[Answer format for this reply: be concise — at most about 300 words (fewer in non-Latin scripts), short "
                  "bullets, the most urgent steps and any deadline first, then the disclaimer line and the [CONFIDENCE]/[SOURCES] "
                  "lines. If more detail would help, offer it in one closing sentence. A letter may be up to about 350 words.]")


def concise_suffix(model_id: str) -> str:
    return CONCISE_SUFFIX if model_id == "claude-haiku-5-5" else ""


def is_blank(text) -> bool:
    return not (text or "").strip()


class BlankReply(Exception):
    pass


FAILED_MSG = ("Lex couldn't finish an answer just now. Please send your question again — "
              "this attempt has not been counted against your daily messages.")
