from datetime import timedelta

import pytest

from app.core import security
from app.core.errors import AppError
from app.core.geo import (
    fmt_hhmm,
    haversine_km,
    nearest_neighbor_order,
    parse_hhmm,
    path_length_km,
    travel_minutes,
    two_opt,
)
from app.core.ratelimit import RateLimiter
from app.services import budget
from app.services.companion_engine import evaluate_progress, rank_suggestions, shift_schedule
from app.services.schedule import schedule_stops


def test_haversine_one_degree_of_longitude_at_equator():
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.2)


def test_haversine_known_city_pair():
    # Lahore to Islamabad is roughly 270 km in a straight line.
    assert 250 < haversine_km(31.5204, 74.3587, 33.6844, 73.0479) < 290


def test_travel_minutes_and_time_helpers():
    assert travel_minutes(0, 30) == 0
    assert travel_minutes(1, 30) == 8  # 1 * 1.3 / 30 * 60 = 2.6 min + 5 buffer, rounded up
    assert parse_hhmm("09:30") == 570
    assert fmt_hhmm(570) == "09:30"
    assert fmt_hhmm(99999) == "23:59"


def test_two_opt_never_makes_the_path_longer():
    pts = [(0, 0), (0, 3), (0, 1), (0, 2), (0, 4)]
    nn = nearest_neighbor_order(pts, 0)
    improved = two_opt([0, 1, 2, 3, 4], pts)
    assert path_length_km(improved, pts) <= path_length_km([0, 1, 2, 3, 4], pts)
    assert improved[0] == 0
    assert sorted(nn) == [0, 1, 2, 3, 4]


def test_schedule_skips_lunch_and_drops_stops_that_do_not_fit():
    here = {"lat": 31.58, "lng": 74.31}
    stops = [{**here, "duration_min": 210}, {**here, "duration_min": 90}, {**here, "duration_min": 400}]
    slots = schedule_stops(stops, 9 * 60, 30)
    assert slots[0] == (540, 750)  # 09:00 to 12:30
    assert slots[1][0] == 13 * 60 + 30  # 12:30 falls in the lunch window, so it starts at 13:30
    assert len(slots) == 2  # the 400 minute stop would end after 21:30


def test_schedule_always_keeps_the_first_stop():
    slots = schedule_stops([{"lat": 1, "lng": 1, "duration_min": 900}], 9 * 60, 30)
    assert len(slots) == 1


def test_rate_limiter_blocks_then_recovers(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr("app.core.ratelimit.time.monotonic", lambda: t[0])
    rl = RateLimiter()
    assert all(rl.allow("k", 3, 60)[0] for _ in range(3))
    ok, retry = rl.allow("k", 3, 60)
    assert not ok and retry > 0
    t[0] += 61
    assert rl.allow("k", 3, 60)[0]
    assert rl.allow("other", 3, 60)[0]


def test_password_hash_and_verify():
    h = security.hash_password("Passw0rd123")
    assert h != "Passw0rd123"
    assert security.verify_password(h, "Passw0rd123")
    assert not security.verify_password(h, "wrong")
    assert not security.verify_password("not-a-hash", "x")


def test_tokens_have_types_and_expire():
    secret = "s" * 40
    access = security.create_token(secret, "u1", "user", "access", timedelta(minutes=5))
    assert security.decode_token(secret, access, "access")["sub"] == "u1"
    with pytest.raises(AppError) as e:
        security.decode_token(secret, access, "refresh")
    assert e.value.code == "invalid_token"
    expired = security.create_token(secret, "u1", "user", "access", timedelta(seconds=-5))
    with pytest.raises(AppError) as e:
        security.decode_token(secret, expired, "access")
    assert e.value.code == "token_expired"
    with pytest.raises(AppError):
        security.decode_token("other" * 10, access, "access")


def _itinerary():
    return [
        {"stops": [{"price_level": 0}, {"price_level": 1}]},
        {"stops": [{"price_level": 2}]},
    ]


def test_budget_numbers_match_the_cost_model():
    est = budget.estimate(_itinerary(), days=3, travelers=2, level="mid")
    assert est["breakdown"] == {
        "accommodation": 20000, "food": 24000, "local_transport": 18000, "entry_fees": 4000,
    }
    assert est["total"] == 66000
    assert (est["low"], est["high"]) == (49500, 82500)
    assert est["per_person"] == 33000
    assert est["fit"] is None


def test_budget_fit_labels():
    base = dict(itinerary=_itinerary(), days=3, travelers=2, level="mid")
    assert budget.estimate(**base, budget_total=90000)["fit"] == "within"
    assert budget.estimate(**base, budget_total=70000)["fit"] == "borderline"
    assert budget.estimate(**base, budget_total=40000)["fit"] == "over"


def _stops():
    return [
        {"place_id": "a", "name": "A", "lat": 31.0, "lng": 74.0, "start_time": "09:00", "duration_min": 60, "visited_at": None},
        {"place_id": "b", "name": "B", "lat": 31.1, "lng": 74.0, "start_time": "11:00", "duration_min": 60, "visited_at": None},
    ]


def test_progress_marks_arrival_and_picks_next_stop():
    kw = dict(arrival_radius_m=150, speed_kmh=30, detour=1.3)
    p = evaluate_progress(_stops(), 31.0005, 74.0, 9 * 60, **kw)
    assert p["arrived"] == [0]
    assert p["next"]["name"] == "B"
    assert p["done"] == 1 and p["total"] == 2
    assert p["next"]["distance_km"] == pytest.approx(10.9, abs=0.3)


def test_progress_reports_delay_and_completion():
    kw = dict(arrival_radius_m=150, speed_kmh=30, detour=1.3)
    late = evaluate_progress(_stops(), 31.0, 74.0, 10 * 60 + 30, **kw)
    assert late["next"]["name"] == "B" or late["arrived"] == [0]
    done = [{**s, "visited_at": "x"} for s in _stops()]
    finished = evaluate_progress(done, 31.0, 74.0, 12 * 60, **kw)
    assert finished["next"] is None and finished["delay_min"] is None and finished["done"] == 2


def test_shift_schedule_only_when_late_and_flags_overflow():
    stops = _stops()
    assert shift_schedule(stops, 1, 0)["changes"] == []
    s = shift_schedule(stops, 1, 22)
    assert s["shift_min"] == 25  # rounded up to 5 minutes
    assert s["changes"] == [{"index": 1, "start_time": "11:25"}]
    late = shift_schedule(stops, 0, 700)
    assert late["at_risk"] == [0, 1]


def _cand(pid, name, lat, indoor=False, cat="heritage", minutes=60):
    return {"_id": pid, "name": name, "lat": lat, "lng": 74.0, "indoor": indoor, "category": cat, "avg_visit_minutes": minutes}


def test_suggestions_prefer_indoor_places_when_it_rains_and_respect_time():
    cands = [_cand("o", "Outdoor", 31.001), _cand("i", "Indoor", 31.002, indoor=True), _cand("far", "Far", 40.0)]
    kw = dict(interests=["heritage"], remaining_min=300, speed_kmh=30, detour=1.3)
    dry = rank_suggestions(31.0, 74.0, cands, wet=False, **kw)
    wet = rank_suggestions(31.0, 74.0, cands, wet=True, **kw)
    assert [s["place_id"] for s in dry][0] == "o"  # closer wins when dry
    assert [s["place_id"] for s in wet][0] == "i"  # indoor wins when wet
    assert all(s["place_id"] != "far" for s in dry)  # beyond 25 km is excluded
    short = rank_suggestions(31.0, 74.0, cands, wet=False, **{**kw, "remaining_min": 30})
    assert short == []  # nothing fits in 30 minutes
