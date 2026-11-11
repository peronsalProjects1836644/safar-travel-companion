from datetime import date, timedelta

import httpx
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.geo import haversine_km
from tests.conftest import Clock, plan_body, register, utc

WS = "/api/v1/ws/companion"
API = "/api/v1"


@pytest.fixture
def clock(monkeypatch):
    # Tomorrow 08:00 in Pakistan (UTC+5). It must be in the future: mongomock applies TTL indexes
    # against the real clock, so a past date would purge shares and sessions mid-test.
    d = date.today() + timedelta(days=1)
    clk = Clock(utc(d.year, d.month, d.day, 3, 0))
    monkeypatch.setattr("app.services.companion.utcnow", clk)
    return clk


def start_trip(ctx, **overrides):
    c = ctx.client
    headers, user = register(c, name="Ali Khan")
    trip = c.post(f"{API}/trips/plan", json=plan_body(days=1, pace="relaxed", **overrides), headers=headers).json()
    started = c.post(f"{API}/trips/{trip['id']}/start", json={"day": 1}, headers=headers)
    assert started.status_code == 200 and started.json()["status"] == "active"
    return headers, trip, user


def connect(ctx, headers):
    token = headers["Authorization"].split()[1]
    ws = ctx.client.websocket_connect(WS)
    sock = ws.__enter__()
    sock.send_json({"type": "auth", "token": token})
    return ws, sock


def near(stops, i, radius_m=150):
    """Indexes of every stop within the arrival radius of stop i (nearby stops are visited together)."""
    return [j for j, s in enumerate(stops) if haversine_km(stops[i]["lat"], stops[i]["lng"], s["lat"], s["lng"]) * 1000 <= radius_m]


def loc(stop, **extra):
    return {"type": "location", "lat": stop["lat"], "lng": stop["lng"], **extra}


def test_arriving_at_a_stop_marks_it_visited_and_points_to_the_next(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    stops = trip["itinerary"][0]["stops"]
    here = near(stops, 0)
    assert len(here) >= 2  # the test data has two stops about 100 m apart, as real cities do
    ws, sock = connect(ctx, headers)
    try:
        assert sock.receive_json()["type"] == "ready"
        sock.send_json(loc(stops[0], accuracy_m=12))
        state = sock.receive_json()
    finally:
        ws.__exit__(None, None, None)
    rest = [s for j, s in enumerate(stops) if j not in here]
    assert state["type"] == "state" and state["arrived"] == [stops[j]["name"] for j in here]
    assert state["next_stop"]["name"] == rest[0]["name"] and state["next_stop"]["eta_min"] >= 5
    assert state["progress"] == {"done": len(here), "total": len(stops)} and state["day_complete"] is False
    assert state["weather"]["label"] == "Mainly clear"
    planned = {s["place_id"] for s in stops}
    assert state["suggestions"] and all(s["place_id"] not in planned for s in state["suggestions"])
    saved = ctx.client.get(f"{API}/trips/{trip['id']}", headers=headers).json()
    assert all(saved["itinerary"][0]["stops"][j]["visited_at"] is not None for j in here)


def test_running_late_pushes_the_rest_of_the_day_later(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    stops = trip["itinerary"][0]["stops"]
    original = [s["start_time"] for s in stops]
    here = near(stops, 0)
    later = [j for j in range(len(stops)) if j not in here]
    clock.now = clock.now.replace(hour=9, minute=30)  # 14:30 local, well after the next stop was due
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        sock.send_json(loc(stops[0]))
        state = sock.receive_json()
    finally:
        ws.__exit__(None, None, None)
    assert state["delay_min"] >= 15 and state["schedule_updated"] is True
    saved = ctx.client.get(f"{API}/trips/{trip['id']}", headers=headers).json()["itinerary"][0]["stops"]
    assert all(saved[j]["start_time"] == original[j] for j in here)  # visited stops are untouched
    assert saved[later[0]]["start_time"] > original[later[0]]


def test_pings_are_throttled_and_only_the_latest_position_is_stored(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    stops = trip["itinerary"][0]["stops"]
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        sock.send_json(loc(stops[0]))
        first = sock.receive_json()
        sock.send_json({"type": "location", "lat": 31.5, "lng": 74.3})
        second = sock.receive_json()
        assert second.get("throttled") is True and second["next_stop"] == first["next_stop"]
        clock.advance(10)
        sock.send_json({"type": "location", "lat": 31.5, "lng": 74.3})
        third = sock.receive_json()
        assert "throttled" not in third
    finally:
        ws.__exit__(None, None, None)
    assert ctx.run(ctx.db.live_sessions.count_documents({})) == 1  # no location history


def test_finishing_every_stop_completes_the_day_and_the_trip(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    stops = trip["itinerary"][0]["stops"]
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        state = None
        for s in stops:
            clock.advance(10)
            sock.send_json(loc(s))
            state = sock.receive_json()
    finally:
        ws.__exit__(None, None, None)
    assert state["day_complete"] is True and state["trip_complete"] is True and state["next_stop"] is None
    assert ctx.client.get(f"{API}/trips/{trip['id']}", headers=headers).json()["status"] == "completed"


def test_wet_weather_is_reported(ctx_no_ai, clock):
    ctx = ctx_no_ai
    wet = {
        "current": {"temperature_2m": 18, "weather_code": 63, "wind_speed_10m": 5, "precipitation": 2.0},
        "daily": {"time": ["2026-10-26"], "weather_code": [63], "temperature_2m_max": [20], "temperature_2m_min": [12], "precipitation_probability_max": [90]},
    }
    ctx.weather.mock(return_value=httpx.Response(200, json=wet))
    headers, trip, _ = start_trip(ctx)
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        sock.send_json(loc(trip["itinerary"][0]["stops"][0]))
        state = sock.receive_json()
    finally:
        ws.__exit__(None, None, None)
    assert state["weather"] == {"label": "Rain", "temp_c": 18, "is_wet": True}


def test_the_companion_still_works_when_weather_is_down(ctx_no_ai, clock):
    ctx = ctx_no_ai
    ctx.weather.mock(side_effect=httpx.ConnectError("down"))
    headers, trip, _ = start_trip(ctx)
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        sock.send_json(loc(trip["itinerary"][0]["stops"][0]))
        state = sock.receive_json()
    finally:
        ws.__exit__(None, None, None)
    assert state["type"] == "state" and state["weather"] is None and state["next_stop"]


def test_websocket_rejects_bad_credentials(ctx_no_ai):
    ctx = ctx_no_ai
    with ctx.client.websocket_connect(WS) as sock:
        sock.send_json({"type": "auth", "token": "garbage"})
        assert sock.receive_json()["code"] == "invalid_token"
        with pytest.raises(WebSocketDisconnect) as e:
            sock.receive_json()
        assert e.value.code == 4401
    with ctx.client.websocket_connect(WS) as sock:
        sock.send_json({"type": "location", "lat": 1, "lng": 1})
        assert sock.receive_json()["code"] == "not_authenticated"
        with pytest.raises(WebSocketDisconnect) as e:
            sock.receive_json()
        assert e.value.code == 4401


def test_websocket_needs_an_active_trip(ctx_no_ai):
    ctx = ctx_no_ai
    headers, _ = register(ctx.client)
    token = headers["Authorization"].split()[1]
    with ctx.client.websocket_connect(WS) as sock:
        sock.send_json({"type": "auth", "token": token})
        assert sock.receive_json()["code"] == "no_active_trip"
        with pytest.raises(WebSocketDisconnect) as e:
            sock.receive_json()
        assert e.value.code == 4404


def test_websocket_handles_bad_messages_without_dropping_the_connection(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    ws, sock = connect(ctx, headers)
    try:
        sock.receive_json()
        sock.send_text("this is not json")
        assert sock.receive_json()["code"] == "bad_message"
        sock.send_json({"type": "location", "lat": 999, "lng": 0})
        assert sock.receive_json()["code"] == "bad_location"
        sock.send_json({"type": "location", "lat": 31.5, "lng": 74.3, "extra": 1})
        assert sock.receive_json()["code"] == "bad_location"
        sock.send_json({"type": "dance"})
        assert sock.receive_json()["code"] == "unknown_type"
        sock.send_text("x" * 3000)
        assert sock.receive_json()["code"] == "message_too_large"
        sock.send_json({"type": "ping"})
        assert sock.receive_json()["type"] == "pong"
    finally:
        ws.__exit__(None, None, None)


def test_rest_fallback_matches_the_websocket(ctx_no_ai, clock):
    ctx = ctx_no_ai
    headers, trip, _ = start_trip(ctx)
    stop = trip["itinerary"][0]["stops"][0]
    r = ctx.client.post(f"{API}/companion/location", json={"lat": stop["lat"], "lng": stop["lng"]}, headers=headers)
    assert r.status_code == 200 and r.json()["arrived"][0] == stop["name"]
    nobody, _ = register(ctx.client)
    none = ctx.client.post(f"{API}/companion/location", json={"lat": 1, "lng": 1}, headers=nobody)
    assert none.status_code == 404 and none.json()["error"]["code"] == "no_active_trip"
    assert ctx.client.post(f"{API}/companion/location", json={"lat": 1, "lng": 1}).status_code == 401


def test_start_and_complete_validation(ctx_no_ai, clock):
    ctx = ctx_no_ai
    c = ctx.client
    headers, trip, _ = start_trip(ctx)
    other, _ = register(c)
    assert c.post(f"{API}/trips/{trip['id']}/start", json={"day": 1}, headers=other).status_code == 404
    assert c.post(f"{API}/trips/{trip['id']}/start", json={"day": 2}, headers=headers).status_code == 422
    done = c.post(f"{API}/trips/{trip['id']}/complete", headers=headers)
    assert done.status_code == 200 and done.json()["status"] == "completed"
    token = headers["Authorization"].split()[1]
    with c.websocket_connect(WS) as sock:
        sock.send_json({"type": "auth", "token": token})
        assert sock.receive_json()["code"] == "no_active_trip"


def test_share_link_shows_only_a_first_name_the_trip_title_and_the_latest_position(ctx_no_ai, clock):
    ctx = ctx_no_ai
    c = ctx.client
    headers, trip, user = start_trip(ctx)
    created = c.post(f"{API}/share", json={"hours": 2}, headers=headers)
    assert created.status_code == 201
    token = created.json()["token"]
    assert len(token) >= 20

    before = c.get(f"{API}/share/{token}")  # public: no login needed
    assert before.status_code == 200 and before.json()["location"] is None and before.json()["name"] == "Ali"

    stop = trip["itinerary"][0]["stops"][0]
    c.post(f"{API}/companion/location", json={"lat": stop["lat"], "lng": stop["lng"], "accuracy_m": 8}, headers=headers)
    after = c.get(f"{API}/share/{token}").json()
    assert after["location"]["lat"] == stop["lat"] and after["trip_title"] == trip["title"]
    text = str(after)
    assert user["user"]["email"] not in text and user["user"]["id"] not in text and "Khan" not in text

    assert c.post(f"{API}/share", json={"hours": 25}, headers=headers).status_code == 422
    assert c.post(f"{API}/share", json={"hours": 2}).status_code == 401


def test_share_link_expires_and_can_be_revoked_only_by_its_owner(ctx_no_ai, clock):
    ctx = ctx_no_ai
    c = ctx.client
    headers, _, _ = start_trip(ctx)
    token = c.post(f"{API}/share", json={"hours": 1}, headers=headers).json()["token"]
    other, _ = register(c)
    assert c.delete(f"{API}/share/{token}", headers=other).status_code == 404
    assert c.get(f"{API}/share/{token}").status_code == 200
    assert c.delete(f"{API}/share/{token}", headers=headers).status_code == 204
    assert c.get(f"{API}/share/{token}").status_code == 404

    token2 = c.post(f"{API}/share", json={"hours": 1}, headers=headers).json()["token"]
    clock.advance(2 * 3600)
    expired = c.get(f"{API}/share/{token2}")
    assert expired.status_code == 404 and expired.json()["error"]["code"] == "share_not_found"
    assert c.get(f"{API}/share/{'a' * 22}").status_code == 404
