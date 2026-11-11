from tests.conftest import admin_headers, register


def test_register_login_me_flow(ctx):
    c = ctx.client
    headers, body = register(c, "ali@example.com")
    assert body["user"]["email"] == "ali@example.com"
    assert body["user"]["role"] == "user"
    assert "password" not in str(body).lower().replace("password_hash", "")
    me = c.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["name"] == "Ali Khan"

    login = c.post("/api/v1/auth/login", json={"email": "ALI@example.com", "password": "Passw0rd123"})
    assert login.status_code == 200
    assert login.json()["tokens"]["expires_in"] == 7200


def test_duplicate_email_and_weak_password(ctx):
    c = ctx.client
    register(c, "dup@example.com")
    r = c.post("/api/v1/auth/register", json={"email": "dup@example.com", "name": "X", "password": "Passw0rd123"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    weak = c.post("/api/v1/auth/register", json={"email": "w@example.com", "name": "X", "password": "password"})
    assert weak.status_code == 422
    err = weak.json()["error"]
    assert err["code"] == "validation_error" and err["fields"][0]["field"] == "password"


def test_wrong_password_and_unknown_email_look_the_same(ctx):
    c = ctx.client
    register(c, "known@example.com")
    a = c.post("/api/v1/auth/login", json={"email": "known@example.com", "password": "Wrong12345"})
    b = c.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Wrong12345"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_refresh_requires_a_refresh_token(ctx):
    c = ctx.client
    _, body = register(c)
    ok = c.post("/api/v1/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = c.post("/api/v1/auth/refresh", json={"refresh_token": body["tokens"]["access_token"]})
    assert bad.status_code == 401
    # an access token cannot be used where a refresh token is expected, and vice versa
    misuse = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['tokens']['refresh_token']}"})
    assert misuse.status_code == 401


def test_protected_routes_need_a_token(ctx):
    r = ctx.client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"
    junk = ctx.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert junk.status_code == 401


def test_profile_update_normalizes_phone_numbers(ctx):
    c = ctx.client
    headers, _ = register(c)
    r = c.patch(
        "/api/v1/auth/me", headers=headers,
        json={
            "name": "Ali Raza",
            "preferences": {"interests": ["heritage"], "budget_level": "budget", "pace": "relaxed"},
            "emergency_contacts": [{"name": "Dad", "phone": "0300-1234567"}],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Ali Raza"
    assert body["emergency_contacts"] == [{"name": "Dad", "phone": "923001234567"}]
    assert body["preferences"]["pace"] == "relaxed"


def test_profile_rejects_bad_phone_and_too_many_contacts(ctx):
    c = ctx.client
    headers, _ = register(c)
    bad = c.patch("/api/v1/auth/me", headers=headers, json={"emergency_contacts": [{"name": "X", "phone": "123"}]})
    assert bad.status_code == 422
    many = [{"name": f"C{i}", "phone": "03001234567"} for i in range(6)]
    assert c.patch("/api/v1/auth/me", headers=headers, json={"emergency_contacts": many}).status_code == 422
    unknown = c.patch("/api/v1/auth/me", headers=headers, json={"role": "admin"})
    assert unknown.status_code == 422  # unknown fields are rejected, so no privilege escalation


def test_login_is_rate_limited(ctx):
    c = ctx.client
    for _ in range(10):
        assert c.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "Wrong12345"}).status_code == 401
    r = c.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "Wrong12345"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited" and "retry-after" in r.headers


def test_seeded_admin_exists_and_users_are_not_admins(ctx):
    admin = admin_headers(ctx.client)
    assert ctx.client.get("/api/v1/auth/me", headers=admin).json()["role"] == "admin"
    headers, _ = register(ctx.client)
    assert ctx.client.get("/api/v1/admin/stats", headers=headers).status_code == 403
    assert ctx.client.get("/api/v1/admin/stats").status_code == 401
