# Law monitoring (one-switch) admin API: overview auth, monitoring gate, emergency stop. Preview only.
# Run BEFORE the 17-law baseline is saved (expects baseline incomplete). Leaves emergency stop OFF afterwards.
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@aiadvocate.co.uk", "AdminLex2026!")
USER = ("test@advocate.app", "Test12345!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def user():
    return _login(*USER)


# --- overview access control
def test_overview_unauth_401():
    assert requests.get(f"{API}/admin/law-watch/overview", timeout=30).status_code == 401


def test_overview_non_admin_403(user):
    assert user.get(f"{API}/admin/law-watch/overview", timeout=30).status_code == 403


def test_monitoring_non_admin_403(user):
    r = user.post(f"{API}/admin/law-watch/monitoring", json={"enabled": True, "password": USER[1]}, timeout=30)
    assert r.status_code == 403


def test_emergency_non_admin_403(user):
    assert user.post(f"{API}/admin/law-watch/emergency-stop", json={"enabled": True}, timeout=30).status_code == 403


def test_overview_admin_shape(admin):
    r = admin.get(f"{API}/admin/law-watch/overview", timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("monitoring_on", "time", "emergency_stop", "baseline_complete", "records", "last_run",
              "last_successful_check", "last_failures", "awaiting_review", "pending_amendments", "alerts_to"):
        assert k in d, k
    assert d["time"] == "06:00 Europe/London"
    assert d["monitoring_on"] is False
    assert d["baseline_complete"] is False
    assert isinstance(d["alerts_to"], list) and d["alerts_to"]
    assert all("*" in e for e in d["alerts_to"]), d["alerts_to"]  # masked
    assert "admin@aiadvocate.co.uk" not in d["alerts_to"]


# --- monitoring switch gate
def test_monitoring_on_wrong_password_400(admin):
    r = admin.post(f"{API}/admin/law-watch/monitoring", json={"enabled": True, "password": "wrong-pass-1"}, timeout=30)
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()


def test_monitoring_on_missing_password_400(admin):
    r = admin.post(f"{API}/admin/law-watch/monitoring", json={"enabled": True}, timeout=30)
    assert r.status_code == 400


def test_monitoring_on_baseline_incomplete_409(admin):
    r = admin.post(f"{API}/admin/law-watch/monitoring", json={"enabled": True, "password": ADMIN[1]}, timeout=60)
    assert r.status_code == 409
    assert "incomplete" in r.json()["detail"].lower()
    assert admin.get(f"{API}/admin/law-watch/overview", timeout=30).json()["monitoring_on"] is False


def test_monitoring_off_no_password_200(admin):
    r = admin.post(f"{API}/admin/law-watch/monitoring", json={"enabled": False}, timeout=30)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


# --- emergency stop
def test_emergency_stop_cycle(admin):
    r = admin.post(f"{API}/admin/law-watch/emergency-stop", json={"enabled": True}, timeout=30)
    assert r.status_code == 200 and r.json()["emergency_stop"] is True
    ov = admin.get(f"{API}/admin/law-watch/overview", timeout=30).json()
    assert ov["emergency_stop"] is True and ov["monitoring_on"] is False
    # writes switch blocked while stopped
    assert admin.post(f"{API}/admin/law-watch/switch", json={"enabled": True}, timeout=30).status_code == 403
    # monitoring refused while stopped (even with password)
    r = admin.post(f"{API}/admin/law-watch/monitoring", json={"enabled": True, "password": ADMIN[1]}, timeout=30)
    assert r.status_code == 409 and "emergency" in r.json()["detail"].lower()
    # release needs password
    assert admin.post(f"{API}/admin/law-watch/emergency-stop", json={"enabled": False}, timeout=30).status_code == 400
    assert admin.post(f"{API}/admin/law-watch/emergency-stop", json={"enabled": False, "password": "nope-wrong"},
                      timeout=30).status_code == 400
    assert admin.get(f"{API}/admin/law-watch/overview", timeout=30).json()["emergency_stop"] is True
    r = admin.post(f"{API}/admin/law-watch/emergency-stop", json={"enabled": False, "password": ADMIN[1]}, timeout=30)
    assert r.status_code == 200 and r.json()["emergency_stop"] is False
    ov = admin.get(f"{API}/admin/law-watch/overview", timeout=30).json()
    assert ov["emergency_stop"] is False and ov["monitoring_on"] is False
