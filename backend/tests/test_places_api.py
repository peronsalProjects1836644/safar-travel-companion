from tests.conftest import admin_headers, register

NEW_PLACE = {
    "name": "Test Garden", "destination": "Lahore", "region": "Punjab", "category": "parks",
    "tags": ["garden"], "description": "A test place.", "lat": 31.55, "lng": 74.34,
    "price_level": 1, "avg_visit_minutes": 45, "indoor": False, "best_season": ["winter"],
}


def test_meta_lists_choices_for_forms(ctx):
    meta = ctx.client.get("/api/v1/meta").json()
    assert "heritage" in meta["categories"] and meta["limits"]["max_days"] == 7
    assert {"label": "Police", "number": "15"} in meta["emergency_numbers"]


def test_destinations_are_grouped_with_counts(ctx):
    rows = {d["name"]: d for d in ctx.client.get("/api/v1/destinations").json()}
    assert rows["Lahore"]["count"] == 8 and rows["Hunza"]["count"] == 4
    assert rows["Lahore"]["region"] == "Punjab"
    assert 31 < rows["Lahore"]["lat"] < 32


def test_list_filters_and_pagination(ctx):
    c = ctx.client
    page = c.get("/api/v1/places", params={"destination": "lahore", "limit": 3, "offset": 0}).json()
    assert page["total"] == 8 and len(page["items"]) == 3
    names = [p["name"] for p in page["items"]]
    assert names == sorted(names)
    rest = c.get("/api/v1/places", params={"destination": "Lahore", "limit": 50, "offset": 3}).json()
    assert len(rest["items"]) == 5
    heritage = c.get("/api/v1/places", params={"category": "heritage"}).json()
    assert heritage["total"] == 6 and all(p["category"] == "heritage" for p in heritage["items"])
    found = c.get("/api/v1/places", params={"q": "mughal fort"}).json()
    assert [p["name"] for p in found["items"]] == ["Lahore Fort"]
    assert c.get("/api/v1/places", params={"category": "nonsense"}).status_code == 422


def test_search_text_is_not_treated_as_a_regex(ctx):
    r = ctx.client.get("/api/v1/places", params={"q": ".*"})
    assert r.status_code == 200 and r.json()["total"] == 0


def test_suggest_ranks_prefix_matches_first(ctx):
    names = [p["name"] for p in ctx.client.get("/api/v1/places/suggest", params={"q": "bad"}).json()]
    assert names[0] == "Badshahi Mosque"
    assert ctx.client.get("/api/v1/places/suggest", params={"q": ""}).status_code == 422


def test_nearby_is_sorted_and_respects_radius(ctx):
    rows = ctx.client.get("/api/v1/places/nearby", params={"lat": 31.5883, "lng": 74.3107, "radius_km": 3}).json()
    dists = [r["distance_km"] for r in rows]
    assert dists == sorted(dists) and rows[0]["name"] == "Badshahi Mosque"
    assert all(d <= 3 for d in dists)
    assert "Baltit Fort" not in [r["name"] for r in rows]
    only = ctx.client.get("/api/v1/places/nearby", params={"lat": 31.5883, "lng": 74.3107, "radius_km": 30, "category": "museums"}).json()
    assert [r["name"] for r in only] == ["Lahore Museum"]


def test_place_detail_and_404(ctx):
    r = ctx.client.get("/api/v1/places/badshahi-mosque-lahore")
    assert r.status_code == 200 and r.json()["name"] == "Badshahi Mosque"
    assert "max-age" in r.headers["cache-control"]
    missing = ctx.client.get("/api/v1/places/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "place_not_found"


def test_only_admins_can_edit_places(ctx):
    c = ctx.client
    user, _ = register(c)
    assert c.post("/api/v1/admin/places", json=NEW_PLACE, headers=user).status_code == 403
    admin = admin_headers(c)

    created = c.post("/api/v1/admin/places", json=NEW_PLACE, headers=admin)
    assert created.status_code == 201 and created.json()["id"] == "test-garden-lahore"
    again = c.post("/api/v1/admin/places", json=NEW_PLACE, headers=admin).json()
    assert again["id"] == "test-garden-lahore-2"  # slug collisions get a suffix
    dup = c.post("/api/v1/admin/places", json={**NEW_PLACE, "id": "test-garden-lahore"}, headers=admin)
    assert dup.status_code == 409

    updated = c.put("/api/v1/admin/places/test-garden-lahore", json={**NEW_PLACE, "price_level": 3}, headers=admin)
    assert updated.status_code == 200 and updated.json()["price_level"] == 3
    assert c.delete("/api/v1/admin/places/test-garden-lahore", headers=admin).status_code == 204
    assert c.get("/api/v1/places/test-garden-lahore").status_code == 404
    assert c.delete("/api/v1/admin/places/test-garden-lahore", headers=admin).status_code == 404


def test_place_validation(ctx):
    admin = admin_headers(ctx.client)
    bad = ctx.client.post("/api/v1/admin/places", json={**NEW_PLACE, "lat": 120}, headers=admin)
    assert bad.status_code == 422
    bad_cat = ctx.client.post("/api/v1/admin/places", json={**NEW_PLACE, "category": "casino"}, headers=admin)
    assert bad_cat.status_code == 422
    bad_url = ctx.client.post("/api/v1/admin/places", json={**NEW_PLACE, "image_url": "javascript:alert(1)"}, headers=admin)
    assert bad_url.status_code == 422


def test_destinations_carry_a_cover_photo_when_any_place_has_one(ctx):
    admin = admin_headers(ctx.client)
    ctx.client.post("/api/v1/admin/places", json={**NEW_PLACE, "destination": "Hunza", "region": "Gilgit-Baltistan",
                                                   "image_url": "https://example.com/p.jpg"}, headers=admin)
    rows = {d["name"]: d for d in ctx.client.get("/api/v1/destinations").json()}
    assert rows["Hunza"]["image_url"] == "https://example.com/p.jpg" and rows["Lahore"]["image_url"] is None
