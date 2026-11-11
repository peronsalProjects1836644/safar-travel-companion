import json

from tests.conftest import build_ctx, make_settings, plan_body, register

LAHORE_IDS = [
    "badshahi-mosque-lahore", "lahore-fort-lahore", "shalimar-gardens-lahore", "minar-e-pakistan-lahore",
    "lahore-museum-lahore", "wazir-khan-mosque-lahore", "jahangir-s-tomb-lahore", "fort-road-food-street-lahore",
]


def ai_plan(day1, day2, title="Lahore in two days", tip="Go early"):
    def stops(ids):
        return [{"place_id": i, "tip": tip} for i in ids]

    return json.dumps(
        {
            "title": title, "summary": "A nice plan.", "tips": ["Drink water", "Carry cash"],
            "days": [
                {"day": 1, "theme": "Old city", "day_start": "09:00", "stops": stops(day1)},
                {"day": 2, "theme": "Gardens and food", "day_start": "10:00", "stops": stops(day2)},
            ],
        }
    )


GOOD = ai_plan(["lahore-fort-lahore", "badshahi-mosque-lahore"], ["wazir-khan-mosque-lahore", "fort-road-food-street-lahore"])


def test_rule_based_plan_without_ai(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    r = c.post("/api/v1/trips/plan", json=plan_body(days=2, pace="balanced"), headers=headers)
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["source"] == "rules" and trip["notice"] is None
    assert len(trip["itinerary"]) == 2 and trip["status"] == "planned"
    ids = [s["place_id"] for d in trip["itinerary"] for s in d["stops"]]
    assert len(ids) == len(set(ids)) and set(ids) <= set(LAHORE_IDS)
    for day in trip["itinerary"]:
        times = [s["start_time"] for s in day["stops"]]
        assert times == sorted(times) and 1 <= len(times) <= 4
        assert day["distance_km"] >= 0 and day["theme"]
    assert trip["itinerary"][0]["date"] == plan_body()["start_date"]
    assert trip["budget"]["low"] < trip["budget"]["total"] < trip["budget"]["high"]
    assert trip["budget"]["breakdown"]["accommodation"] == 10000  # 1 room, 1 night, mid level


def test_interests_steer_the_rule_based_plan(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    trip = c.post("/api/v1/trips/plan", json=plan_body(days=1, interests=["museums"], pace="relaxed"), headers=headers).json()
    assert "lahore-museum-lahore" in [s["place_id"] for s in trip["itinerary"][0]["stops"]]


def test_ai_plan_is_validated_and_assembled_in_code(ctx):
    ctx.ai.queue.append(GOOD)
    headers, _ = register(ctx.client)
    r = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers)
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["source"] == "ai" and trip["title"] == "Lahore in two days" and trip["notice"] is None
    first = trip["itinerary"][0]["stops"]
    assert [s["place_id"] for s in first] == ["lahore-fort-lahore", "badshahi-mosque-lahore"]
    assert first[0]["start_time"] == "09:00" and first[0]["duration_min"] == 90  # from our data, not the AI
    assert first[0]["tip"] == "Go early"
    assert trip["itinerary"][1]["stops"][0]["start_time"] == "10:00"
    assert trip["tips"] == ["Drink water", "Carry cash"]


def test_ai_request_contains_only_places_and_no_personal_data(ctx):
    ctx.ai.queue.append(GOOD)
    headers, body = register(ctx.client, "private.person@example.com", name="Private Person")
    ctx.client.post("/api/v1/trips/plan", json=plan_body(notes="I love old buildings"), headers=headers)
    call = ctx.ai.calls[0]
    text = json.dumps(call["messages"])
    assert "private.person@example.com" not in text and "Private Person" not in text
    assert body["user"]["id"] not in text and call["user"] != body["user"]["id"]
    assert "I love old buildings" in text and "traveler_notes" in text
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["model"] == ctx.settings.openai_model
    payload = json.loads(call["messages"][1]["content"])
    assert {p["id"] for p in payload["places"]} <= set(LAHORE_IDS)


def test_invalid_ai_answer_is_retried_with_the_reason_then_accepted(ctx):
    bad = ai_plan(["not-a-real-place"], ["lahore-fort-lahore"])
    ctx.ai.queue.extend([bad, GOOD])
    headers, _ = register(ctx.client)
    trip = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers).json()
    assert trip["source"] == "ai" and len(ctx.ai.calls) == 2
    retry_text = ctx.ai.calls[1]["messages"][-1]["content"]
    assert "unknown place_id" in retry_text


def test_ai_that_keeps_inventing_places_falls_back_to_rules(ctx):
    bad = ai_plan(["made-up"], ["also-made-up"])
    ctx.ai.queue.extend([bad, bad])
    headers, _ = register(ctx.client)
    trip = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers).json()
    assert trip["source"] == "rules" and "standard planner" in trip["notice"]
    assert len(ctx.ai.calls) == 2


def test_ai_outage_falls_back_to_rules(ctx):
    ctx.ai.queue.append(RuntimeError("openai is down"))
    headers, _ = register(ctx.client)
    r = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers)
    assert r.status_code == 201 and r.json()["source"] == "rules" and r.json()["notice"]


def test_wrong_day_count_or_malformed_json_is_rejected(ctx):
    one_day = json.dumps({"title": "x", "summary": "", "tips": [], "days": [{"day": 1, "theme": "t", "day_start": "09:00", "stops": [{"place_id": "lahore-fort-lahore", "tip": ""}]}]})
    ctx.ai.queue.extend([one_day, "this is not json"])
    headers, _ = register(ctx.client)
    trip = ctx.client.post("/api/v1/trips/plan", json=plan_body(days=2), headers=headers).json()
    assert trip["source"] == "rules"


def test_identical_requests_reuse_the_cached_plan_and_cost_one_ai_call(ctx):
    ctx.ai.queue.append(GOOD)
    h1, _ = register(ctx.client)
    h2, _ = register(ctx.client)
    a = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=h1).json()
    b = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=h2).json()
    assert a["source"] == b["source"] == "ai" and len(ctx.ai.calls) == 1
    assert a["id"] != b["id"]
    quota = ctx.client.get("/api/v1/ai/status", headers=h2).json()
    assert quota["remaining_today"] == ctx.settings.ai_daily_limit_per_user  # the cached plan was free


def test_daily_ai_quota_degrades_to_the_rule_planner():
    for ctx in build_ctx(make_settings(openai_api_key="", ai_daily_limit_per_user=1)):
        ctx.ai.queue.append(GOOD)
        headers, _ = register(ctx.client)
        first = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers).json()
        second = ctx.client.post("/api/v1/trips/plan", json=plan_body(pace="packed"), headers=headers).json()
        assert first["source"] == "ai"
        assert second["source"] == "rules" and "limit" in second["notice"]
        assert len(ctx.ai.calls) == 1


def test_global_ai_budget_cap():
    for ctx in build_ctx(make_settings(ai_daily_limit_global=1)):
        ctx.ai.queue.extend([GOOD, GOOD])
        h1, _ = register(ctx.client)
        h2, _ = register(ctx.client)
        a = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=h1).json()
        b = ctx.client.post("/api/v1/trips/plan", json=plan_body(pace="packed"), headers=h2).json()
        assert a["source"] == "ai" and b["source"] == "rules"


def test_plan_validation_and_destination_errors(ctx):
    c = ctx.client
    headers, _ = register(c)
    assert c.post("/api/v1/trips/plan", json=plan_body()).status_code == 401
    unknown = c.post("/api/v1/trips/plan", json=plan_body(destination="Atlantis"), headers=headers)
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "unknown_destination"


def test_plan_request_validation(ctx):
    c = ctx.client
    headers, _ = register(c)
    for bad in (
        plan_body(days=8), plan_body(interests=[]), plan_body(start_date="2001-01-01"),
        plan_body(notes="x" * 201), plan_body(extra="field"),
    ):
        assert c.post("/api/v1/trips/plan", json=bad, headers=headers).status_code == 422


def test_plan_endpoint_is_rate_limited(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    codes = [c.post("/api/v1/trips/plan", json=plan_body(), headers=headers).status_code for _ in range(7)]
    assert codes[:6] == [201] * 6 and codes[6] == 429


def test_budget_fit_is_reported_when_a_budget_is_given(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    cheap = c.post("/api/v1/trips/plan", json=plan_body(budget_total_pkr=5000), headers=headers).json()
    rich = c.post("/api/v1/trips/plan", json=plan_body(budget_total_pkr=5_000_000), headers=headers).json()
    assert cheap["budget"]["fit"] == "over" and rich["budget"]["fit"] == "within"


def test_trip_crud_and_ownership(ctx_no_ai):
    c = ctx_no_ai.client
    mine, _ = register(c)
    other, _ = register(c)
    trip = c.post("/api/v1/trips/plan", json=plan_body(), headers=mine).json()
    tid = trip["id"]
    assert [t["id"] for t in c.get("/api/v1/trips", headers=mine).json()] == [tid]
    assert c.get("/api/v1/trips", headers=other).json() == []
    assert c.get(f"/api/v1/trips/{tid}", headers=other).status_code == 404
    assert c.delete(f"/api/v1/trips/{tid}", headers=other).status_code == 404
    assert c.get("/api/v1/trips/not-an-id", headers=mine).status_code == 404

    renamed = c.patch(f"/api/v1/trips/{tid}", json={"title": "My Lahore trip"}, headers=mine)
    assert renamed.status_code == 200 and renamed.json()["title"] == "My Lahore trip"
    summary = c.get("/api/v1/trips", headers=mine).json()[0]
    assert summary["title"] == "My Lahore trip" and summary["stop_count"] >= 2
    assert c.delete(f"/api/v1/trips/{tid}", headers=mine).status_code == 204
    assert c.get(f"/api/v1/trips/{tid}", headers=mine).status_code == 404


def test_editing_stops_recomputes_times_and_budget(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    trip = c.post("/api/v1/trips/plan", json=plan_body(days=1, pace="relaxed", travelers=1), headers=headers).json()
    tid = trip["id"]
    used = {s["place_id"] for d in trip["itinerary"] for s in d["stops"]}
    spare = next(i for i in LAHORE_IDS if i not in used)
    before = len(trip["itinerary"][0]["stops"])

    added = c.post(f"/api/v1/trips/{tid}/stops", json={"day": 1, "place_id": spare}, headers=headers)
    assert added.status_code == 200, added.text
    day = added.json()["itinerary"][0]
    assert len(day["stops"]) == before + 1 and day["stops"][-1]["place_id"] == spare
    times = [s["start_time"] for s in day["stops"]]
    assert times == sorted(times)

    assert c.post(f"/api/v1/trips/{tid}/stops", json={"day": 1, "place_id": spare}, headers=headers).status_code == 409
    assert c.post(f"/api/v1/trips/{tid}/stops", json={"day": 1, "place_id": "baltit-fort-hunza"}, headers=headers).status_code == 422
    assert c.post(f"/api/v1/trips/{tid}/stops", json={"day": 3, "place_id": "x"}, headers=headers).status_code == 422
    assert c.post(f"/api/v1/trips/{tid}/stops", json={"day": 1, "place_id": "nope"}, headers=headers).status_code == 404

    removed = c.delete(f"/api/v1/trips/{tid}/days/1/stops/{before}", headers=headers)
    assert removed.status_code == 200 and len(removed.json()["itinerary"][0]["stops"]) == before
    assert c.delete(f"/api/v1/trips/{tid}/days/1/stops/99", headers=headers).status_code == 404
    while len(c.get(f"/api/v1/trips/{tid}", headers=headers).json()["itinerary"][0]["stops"]) > 1:
        c.delete(f"/api/v1/trips/{tid}/days/1/stops/0", headers=headers)
    last = c.delete(f"/api/v1/trips/{tid}/days/1/stops/0", headers=headers)
    assert last.status_code == 422 and last.json()["error"]["code"] == "day_needs_a_stop"


def test_food_stops_never_open_the_day(ctx_no_ai):
    c = ctx_no_ai.client
    headers, _ = register(c)
    trip = c.post("/api/v1/trips/plan", json=plan_body(days=1, interests=["food", "heritage"], pace="packed"), headers=headers).json()
    stops = trip["itinerary"][0]["stops"]
    assert len(stops) > 2 and stops[0]["category"] != "food"
    assert any(s["category"] == "food" for s in stops)


def test_meal_order_puts_lunch_midday_and_extra_meals_last():
    from app.services.planner import meal_order

    def p(name, cat, minutes=60):
        return ({"category": cat, "avg_visit_minutes": minutes}, {"name": name})

    pairs = [p("a", "heritage", 90), p("b", "food"), p("c", "museums", 90), p("d", "heritage", 90), p("e", "food")]
    assert [x[1]["name"] for x in meal_order(pairs, 9 * 60)] == ["a", "c", "b", "d", "e"]
    assert [x[1]["name"] for x in meal_order([p("f", "food"), p("g", "food")], 9 * 60)] == ["f", "g"]


def test_a_stay_longer_than_the_places_allow_is_planned_with_free_days(ctx):
    headers, _ = register(ctx.client)
    r = ctx.client.post("/api/v1/trips/plan", json=plan_body(destination="Tiny", days=3), headers=headers)
    assert r.status_code == 201
    trip = r.json()
    assert trip["days"] == 3 and trip["recommended_days"] == 1 and trip["title"].startswith("3-day")
    assert [len(d["stops"]) for d in trip["itinerary"]] == [2, 0, 0]
    assert [d["theme"] for d in trip["itinerary"]][1:] == ["Free day", "Free day"]
    assert "Recommended stay for Tiny is about 1 day" in trip["notice"] and "left open" in trip["notice"]
    assert trip["budget"]["breakdown"]["accommodation"] > 0  # the budget still covers all 3 days
    again = ctx.client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert again["recommended_days"] == 1


def test_a_normal_plan_has_no_stay_note(ctx):
    headers, _ = register(ctx.client)
    trip = ctx.client.post("/api/v1/trips/plan", json=plan_body(), headers=headers).json()
    assert trip["notice"] is None or "Recommended stay" not in trip["notice"]
