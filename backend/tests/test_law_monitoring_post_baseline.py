# Post-baseline: monitoring ON -> emergency stop forces OFF -> release keeps OFF (preview; needs 17-law baseline saved)
import os
import requests

URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0] + "/api"
PW = "AdminLex2026!"


def test_estop_from_on_stays_off_after_release():
    tok = requests.post(f"{URL}/auth/login", json={"email": "admin@aiadvocate.co.uk", "password": PW}).json()["access_token"]
    s = requests.Session(); s.headers["Authorization"] = f"Bearer {tok}"
    r = s.post(f"{URL}/admin/law-watch/monitoring", json={"enabled": True, "password": PW}, timeout=120)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True
    ov = s.get(f"{URL}/admin/law-watch/overview").json()
    assert ov["monitoring_on"] and ov["baseline_complete"] and ov["records"] == 17 and ov["pending_amendments"] == 5
    assert s.post(f"{URL}/admin/law-watch/emergency-stop", json={"enabled": True}).json()["emergency_stop"] is True
    assert s.get(f"{URL}/admin/law-watch/overview").json()["monitoring_on"] is False
    assert s.post(f"{URL}/admin/law-watch/emergency-stop", json={"enabled": False, "password": PW}).status_code == 200
    ov = s.get(f"{URL}/admin/law-watch/overview").json()
    assert ov["emergency_stop"] is False and ov["monitoring_on"] is False
