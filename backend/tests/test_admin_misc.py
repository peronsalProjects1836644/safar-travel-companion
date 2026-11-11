from tests.conftest import admin_headers, plan_body, register

API = "/api/v1"


def test_admin_endpoints_are_locked_to_admins(ctx):
    c = ctx.client
    user, _ = register(c)
    for path in ("/admin/stats", "/admin/users"):
        assert c.get(f"{API}{path}").status_code == 401
        assert c.get(f"{API}{path}", headers=user).status_code == 403


def test_admin_stats_and_user_list(ctx):
    c = ctx.client
    user, _ = register(c, name="Sara Ahmed")
    c.post(f"{API}/trips/plan", json=plan_body(), headers=user)
    admin = admin_headers(c)
    stats = c.get(f"{API}/admin/stats", headers=admin).json()
    assert stats["users"] >= 2 and stats["trips"] == 1 and stats["places"] == 14
    assert stats["trips_by_source"]["ai"] + stats["trips_by_source"]["rules"] == 1
    rows = c.get(f"{API}/admin/users", params={"limit": 1}, headers=admin).json()
    assert len(rows) == 1 and "password_hash" not in str(rows)
    everyone = c.get(f"{API}/admin/users", headers=admin).json()
    assert any(r["name"] == "Sara Ahmed" for r in everyone) and all("password" not in r for r in everyone)


def test_disabling_a_user_blocks_login_and_existing_tokens(ctx):
    c = ctx.client
    user, data = register(c, email="blocked@example.com", password="StrongPass123")
    uid = data["user"]["id"]
    admin = admin_headers(c)
    assert c.patch(f"{API}/admin/users/{uid}", json={"disabled": True}, headers=admin).json() == {"id": uid, "disabled": True}
    login = c.post(f"{API}/auth/login", json={"email": "blocked@example.com", "password": "StrongPass123"})
    assert login.status_code == 403 and login.json()["error"]["code"] == "account_disabled"
    assert c.get(f"{API}/auth/me", headers=user).status_code == 403
    c.patch(f"{API}/admin/users/{uid}", json={"disabled": False}, headers=admin)
    assert c.get(f"{API}/auth/me", headers=user).status_code == 200


def test_admin_user_changes_are_validated(ctx):
    c = ctx.client
    admin = admin_headers(c)
    me = c.get(f"{API}/auth/me", headers=admin).json()
    own = c.patch(f"{API}/admin/users/{me['id']}", json={"disabled": True}, headers=admin)
    assert own.status_code == 422 and own.json()["error"]["code"] == "cannot_disable_self"
    missing = c.patch(f"{API}/admin/users/000000000000000000000000", json={"disabled": True}, headers=admin)
    assert missing.status_code == 404
    assert c.patch(f"{API}/admin/users/x", json={"disabled": "yes please", "extra": 1}, headers=admin).status_code == 422


def test_health_endpoints(ctx):
    assert ctx.client.get("/health").json() == {"status": "ok"}
    assert ctx.client.get("/health/ready").json() == {"status": "ready"}


def test_unknown_routes_and_bad_methods_use_the_standard_error_shape(ctx):
    r = ctx.client.get(f"{API}/nothing-here")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message"}
    r = ctx.client.delete(f"{API}/destinations")
    assert r.status_code == 405 and "code" in r.json()["error"]


def test_every_response_carries_its_own_request_id(ctx):
    first = ctx.client.get("/health").headers["x-request-id"]
    second = ctx.client.get("/health", headers={"X-Request-ID": "client-supplied"}).headers["x-request-id"]
    assert len(first) >= 8 and first != second and second != "client-supplied"  # ids are server-generated


def test_cors_allows_only_configured_origins(ctx):
    ok = ctx.client.options(
        f"{API}/destinations",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = ctx.client.options(
        f"{API}/destinations",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


def test_errors_never_leak_internals(ctx):
    r = ctx.client.get(f"{API}/places/%27%3B%20drop")
    assert r.status_code == 404 and "Traceback" not in r.text
    r = ctx.client.post(f"{API}/auth/login", content="{broken", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and "error" in r.json()
