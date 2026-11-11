from datetime import timedelta

import httpx

from app.core.timeutil import utcnow
from tests.conftest import OVERPASS_JSON, build_ctx, make_settings, register


def test_weather_is_normalized_and_cached(ctx):
    c = ctx.client
    r = c.get("/api/v1/weather", params={"lat": 31.5204, "lng": 74.3587, "days": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["label"] == "Mainly clear" and body["current"]["is_wet"] is False
    assert body["daily"][2]["label"] == "Rain" and body["daily"][2]["is_wet"] is True
    assert body["stale"] is False and ctx.weather.call_count == 1
    again = c.get("/api/v1/weather", params={"lat": 31.5210, "lng": 74.3590, "days": 3})
    assert again.json()["current"] == body["current"]
    assert ctx.weather.call_count == 1  # same ~1 km cell, served from the cache
    request = ctx.weather.calls[0].request
    assert "latitude=31.52" in str(request.url)


def test_weather_serves_stale_data_when_upstream_fails_and_errors_cleanly_otherwise(ctx):
    c = ctx.client
    params = {"lat": 31.52, "lng": 74.36, "days": 3}
    ctx.weather.mock(side_effect=httpx.ConnectError("down"))
    cold = c.get("/api/v1/weather", params=params)
    assert cold.status_code == 503 and cold.json()["error"]["code"] == "weather_unavailable"

    ctx.weather.mock(return_value=httpx.Response(200, json=__import__("tests.conftest", fromlist=["x"]).WEATHER_JSON))
    assert c.get("/api/v1/weather", params=params).status_code == 200
    past = utcnow() - timedelta(minutes=5)
    ctx.run(ctx.db.cache.update_one({"_id": "wx:31.52:74.36:3"}, {"$set": {"fresh_until": past}}))
    ctx.weather.mock(side_effect=httpx.ConnectError("down"))
    stale = c.get("/api/v1/weather", params=params)
    assert stale.status_code == 200 and stale.json()["stale"] is True


def test_weather_validates_coordinates(ctx):
    assert ctx.client.get("/api/v1/weather", params={"lat": 120, "lng": 0}).status_code == 422


def test_geocode_needs_login_identifies_the_app_and_caches(ctx):
    c = ctx.client
    assert c.get("/api/v1/geocode/search", params={"q": "badshahi"}).status_code == 401
    headers, _ = register(c)
    r = c.get("/api/v1/geocode/search", params={"q": "Badshahi Mosque"}, headers=headers)
    assert r.status_code == 200
    assert r.json()[0]["lat"] == 31.5883 and r.json()[0]["lng"] == 74.3107
    request = ctx.nominatim.calls[0].request
    assert "test@example.com" in request.headers["user-agent"]
    assert "countrycodes=pk" in str(request.url)
    c.get("/api/v1/geocode/search", params={"q": "  badshahi   mosque "}, headers=headers)
    assert ctx.nominatim.call_count == 1  # normalized query hit the cache
    assert c.get("/api/v1/geocode/search", params={"q": "ab"}, headers=headers).status_code == 422


def test_geocode_is_disabled_without_a_contact_email():
    for ctx in build_ctx(make_settings(nominatim_contact_email="")):
        headers, _ = register(ctx.client)
        r = ctx.client.get("/api/v1/geocode/search", params={"q": "Lahore"}, headers=headers)
        assert r.status_code == 503 and r.json()["error"]["code"] == "geocoding_not_configured"
        assert ctx.nominatim.call_count == 0


def test_nearby_help_filters_by_distance_and_caches(ctx):
    c = ctx.client
    params = {"lat": 31.5700, "lng": 74.3105, "kind": "hospital", "radius_m": 5000}
    r = c.get("/api/v1/safety/nearby", params=params)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "live"
    assert [i["name"] for i in body["items"]] == ["Test Hospital", "Far Hospital"]
    assert body["items"][0]["distance_km"] < body["items"][1]["distance_km"]
    assert body["emergency_numbers"][0]["number"] == "15"
    assert c.get("/api/v1/safety/nearby", params=params).json()["source"] == "cache"
    assert ctx.overpass.call_count == 1
    query = ctx.overpass.calls[0].request.content.decode()
    assert "amenity" in query and "hospital" in query


def test_nearby_help_falls_back_to_emergency_numbers_when_overpass_is_down(ctx):
    ctx.overpass.mock(side_effect=httpx.ConnectError("down"))
    ctx.nominatim.mock(side_effect=httpx.ConnectError("down"))
    r = ctx.client.get("/api/v1/safety/nearby", params={"lat": 33.0, "lng": 73.0, "kind": "police"})
    body = r.json()
    assert r.status_code == 200 and body["source"] == "unavailable" and body["items"] == []
    assert len(body["emergency_numbers"]) >= 3
    assert ctx.overpass.call_count == 3  # every mirror was tried
    assert "police%20station/@33.00000,73.00000" in body["fallback"]["search_url"]
    assert ctx.client.get("/api/v1/safety/nearby", params={"lat": 33, "lng": 73, "kind": "bank"}).status_code == 422


def test_nearby_help_uses_the_next_server_and_always_offers_named_hospitals(ctx):
    answers = iter([httpx.Response(504)])
    ctx.overpass.mock(side_effect=lambda request: next(answers, httpx.Response(200, json=OVERPASS_JSON)))
    r = ctx.client.get("/api/v1/safety/nearby", params={"lat": 31.57, "lng": 74.3105, "kind": "hospital"})
    body = r.json()
    assert body["source"] == "live" and ctx.overpass.call_count == 2
    fb = body["fallback"]
    assert fb["destination"] == "Lahore" and "Mayo Hospital" in [n["name"] for n in fb["named"]]
    assert all(n["maps_url"].startswith("https://www.google.com/maps/search/") for n in fb["named"])
    # pharmacies and police have no named list, only the map search
    ph = ctx.client.get("/api/v1/safety/nearby", params={"lat": 31.57, "lng": 74.3105, "kind": "pharmacy"}).json()
    assert ph["fallback"]["named"] == [] and "pharmacy" in ph["fallback"]["search_url"]


def test_sos_builds_whatsapp_links_for_each_contact(ctx):
    c = ctx.client
    assert c.post("/api/v1/safety/sos", json={"lat": 1, "lng": 2}).status_code == 401
    headers, _ = register(c, name="Ali Khan")
    c.patch("/api/v1/auth/me", headers=headers, json={"emergency_contacts": [{"name": "Dad", "phone": "03001234567"}]})
    r = c.post("/api/v1/safety/sos", headers=headers, json={"lat": 31.5883, "lng": 74.3107, "note": "lost & alone"})
    assert r.status_code == 200
    body = r.json()
    link = body["contacts"][0]["whatsapp_url"]
    assert link.startswith("https://wa.me/923001234567?text=")
    assert "openstreetmap.org" in body["map_url"] and "31.588300" in body["map_url"]
    assert "lost%20%26%20alone" in link  # the note is URL-encoded
    assert "Ali Khan" in body["message"]
    assert ctx.run(ctx.db.sos_events.count_documents({})) == 1
    assert c.post("/api/v1/safety/sos", headers=headers, json={"lat": 100, "lng": 2}).status_code == 422


def test_nearby_help_uses_openstreetmap_search_when_every_overpass_server_is_down(ctx):
    ctx.overpass.mock(side_effect=httpx.ConnectError("down"))
    ctx.nominatim.mock(return_value=httpx.Response(200, json=[
        {"name": "City Hospital", "display_name": "City Hospital, Lahore", "lat": "31.5705", "lon": "74.3110"},
        {"display_name": "Far Clinic, Lahore", "lat": "35.0", "lon": "80.0"},
        {"name": "No coordinates"},
    ]))
    body = ctx.client.get("/api/v1/safety/nearby", params={"lat": 31.57, "lng": 74.3105, "kind": "hospital"}).json()
    assert body["source"] == "live" and [i["name"] for i in body["items"]] == ["City Hospital"]
    request = ctx.nominatim.calls[0].request
    assert "bounded=1" in str(request.url) and "viewbox=" in str(request.url) and "q=hospital" in str(request.url)
    assert ctx.client.get("/api/v1/safety/nearby", params={"lat": 31.57, "lng": 74.3105, "kind": "hospital"}).json()["source"] == "cache"
