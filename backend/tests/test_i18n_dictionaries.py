# i18n dictionary regression checks (static /i18n/*.json served by the frontend)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
LANGS = ["es-ES", "fr-FR", "ar-IQ", "pl-PL", "de-DE", "hi-IN", "ur-PK", "it-IT", "pt-PT", "zh-CN"]
KEYS = ["Will Writer", "Best & worst case", "Hide best & worst case", "Their argument",
        "Hide their argument", "not a law firm", "days left", "days overdue",
        "💾 My saved contracts", "Conveyancing Companion", "United Kingdom"]


@pytest.fixture(scope="module")
def dicts():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return {l: requests.get(f"{BASE_URL}/i18n/{l}.json", timeout=20).json() for l in LANGS}


@pytest.mark.parametrize("lang", LANGS)
def test_keys_present_and_translated(dicts, lang):
    d = dicts[lang]
    missing = [k for k in KEYS if not d.get(k) or d[k] == k]
    assert not missing, f"{lang} missing/untranslated: {missing}"


@pytest.mark.parametrize("lang", LANGS)
def test_days_left_and_overdue_differ(dicts, lang):
    d = dicts[lang]
    assert d.get("days left") != d.get("days overdue")
    assert "replaced" not in (d.get("days left") or "")
