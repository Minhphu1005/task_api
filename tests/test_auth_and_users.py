import asyncio

import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_health_check_and_request_headers(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_auth_validation_edge_cases(client: AsyncClient) -> None:
    # Password exceeding bcrypt 72-byte limit returns 422 (not 500)
    too_long_pw = "a" * 73
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "longpw@example.com", "full_name": "Long PW", "password": too_long_pw},
    )
    assert resp.status_code == 422

    # Multi-byte UTF-8 password exceeding 72 bytes also returns 422
    utf8_long_pw = "ế" * 30  # 90 bytes in UTF-8
    resp_utf8 = await client.post(
        "/api/v1/auth/register",
        json={"email": "utf8pw@example.com", "full_name": "UTF8 PW", "password": utf8_long_pw},
    )
    assert resp_utf8.status_code == 422

    # Whitespace-padded short full_name fails min_length after stripping
    resp_ws = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws@example.com", "full_name": "  a  ", "password": "StrongPass123!"},
    )
    assert resp_ws.status_code == 422


@pytest.mark.asyncio
async def test_auth_register_login_refresh_and_logout(client: AsyncClient) -> None:
    ctx = await register_and_login(client, email="alice@example.com", full_name="Alice Nguyen")

    # Duplicate email returns 409 Conflict
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "full_name": "Alice 2", "password": "Password123!"},
    )
    assert dup.status_code == 409

    # Wrong password returns 401
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert bad_login.status_code == 401

    # Passing an access token to /auth/refresh returns 401
    wrong_type = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ctx["access_token"]},
    )
    assert wrong_type.status_code == 401

    # Concurrent refresh with the same refresh token: only one succeeds
    r1, r2 = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json={"refresh_token": ctx["refresh_token"]}),
        client.post("/api/v1/auth/refresh", json={"refresh_token": ctx["refresh_token"]}),
    )
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 401]
    winner = r1 if r1.status_code == 200 else r2
    new_tokens = winner.json()
    assert new_tokens["access_token"] != ctx["access_token"]

    # Logout revokes the new refresh token
    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout.status_code == 200

    after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_user_profile_update_and_change_password_revokes_old_refresh(
    client: AsyncClient,
) -> None:
    ctx = await register_and_login(client, email="bob@example.com", full_name="Bob Tran")

    me = await client.get("/api/v1/users/me", headers=ctx["headers"])
    assert me.status_code == 200
    assert me.json()["full_name"] == "Bob Tran"

    # Explicit null for full_name returns 422
    null_patch = await client.patch(
        "/api/v1/users/me",
        headers=ctx["headers"],
        json={"full_name": None},
    )
    assert null_patch.status_code == 422

    patched = await client.patch(
        "/api/v1/users/me",
        headers=ctx["headers"],
        json={"full_name": "  Bob Updated  "},
    )
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "Bob Updated"

    # Change password
    changed = await client.post(
        "/api/v1/users/me/change-password",
        headers=ctx["headers"],
        json={"current_password": "StrongPass123!", "new_password": "NewStrongPass456!"},
    )
    assert changed.status_code == 200

    # Refresh token issued before password change is rejected
    old_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ctx["refresh_token"]},
    )
    assert old_refresh.status_code == 401

    # Old password fails, new password succeeds
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "StrongPass123!"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "NewStrongPass456!"},
    )
    assert new_login.status_code == 200
