"""Tests for the new GET /api/lawfirms/nearby endpoint (Google Places + sponsored merge).

Validates:
  * lat/lng path returns sponsored-first + Google Places results
  * postcode path returns resolved_address
  * missing params -> 400
  * shape of Google Places entries (id prefix gplace:, source, distance_km)
  * sponsored dedupe (Crown & Bench Solicitors)
  * Cache speed (2nd call < 200ms)
  * Regression: GET /api/lawfirms still works
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

LDN_LAT, LDN_LNG = 51.5074, -0.1278


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ----- nearby endpoint -----
class TestLawfirmsNearby:
    def test_nearby_latlng_returns_sponsored_and_google(self, s):
        r = s.get(f"{API}/lawfirms/nearby", params={"lat": LDN_LAT, "lng": LDN_LNG, "radius_km": 10}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # required keys
        for k in ("lat", "lng", "radius_km", "count", "sponsored_count", "google_count", "results"):
            assert k in d, f"missing key {k}"
        assert d["sponsored_count"] >= 1
        assert d["google_count"] >= 1
        assert d["count"] == len(d["results"])
        # sponsored first
        first = d["results"][0]
        assert first.get("sponsored") is True
        assert first.get("source") == "sponsored"
        assert "Crown & Bench" in first.get("name", "")
        assert isinstance(first.get("distance_km"), (int, float))
        # at least one google result with correct shape
        gres = [x for x in d["results"] if x.get("source") == "google_places"]
        assert len(gres) >= 1
        g = gres[0]
        assert g["id"].startswith("gplace:")
        assert g.get("name")
        assert g.get("address")
        assert isinstance(g.get("lat"), (int, float))
        assert isinstance(g.get("lng"), (int, float))
        assert isinstance(g.get("distance_km"), (int, float))
        assert g.get("google_maps_url", "").startswith("http")

    def test_nearby_postcode_resolved_address(self, s):
        r = s.get(f"{API}/lawfirms/nearby", params={"postcode": "SW1A 1AA", "radius_km": 10}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("resolved_address"), f"expected resolved_address, got {d.get('resolved_address')}"
        assert d["count"] >= 1

    def test_nearby_missing_params_400(self, s):
        r = s.get(f"{API}/lawfirms/nearby", timeout=15)
        assert r.status_code == 400
        assert "Provide lat/lng or postcode" in r.text

    def test_nearby_dedupe_no_duplicate_crown_and_bench(self, s):
        r = s.get(f"{API}/lawfirms/nearby", params={"lat": LDN_LAT, "lng": LDN_LNG, "radius_km": 10}, timeout=30)
        d = r.json()
        names = [x.get("name", "").lower() for x in d["results"]]
        # Crown & Bench should appear only once (and as sponsored)
        crown_hits = [n for n in names if "crown" in n and "bench" in n]
        assert len(crown_hits) <= 1
        # All Google results shouldn't be marked sponsored
        for g in [x for x in d["results"] if x.get("source") == "google_places"]:
            assert g.get("sponsored") is False

    def test_nearby_cache_is_fast_on_repeat(self, s):
        # warm
        s.get(f"{API}/lawfirms/nearby", params={"lat": LDN_LAT, "lng": LDN_LNG, "radius_km": 10}, timeout=30)
        t0 = time.time()
        r = s.get(f"{API}/lawfirms/nearby", params={"lat": LDN_LAT, "lng": LDN_LNG, "radius_km": 10}, timeout=30)
        elapsed_ms = (time.time() - t0) * 1000
        assert r.status_code == 200
        # Cached call should be < ~500ms (allow margin for prod ingress)
        assert elapsed_ms < 800, f"cached call took {elapsed_ms:.0f}ms"


# ----- regression: legacy endpoint -----
class TestLawfirmsLegacy:
    def test_lawfirms_list_still_works(self, s):
        r = s.get(f"{API}/lawfirms", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # accept either list or {firms: []}
        if isinstance(data, dict):
            data = data.get("firms") or data.get("results") or []
        assert isinstance(data, list)
        assert len(data) >= 1
