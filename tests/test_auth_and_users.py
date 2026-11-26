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

    # Refresh rotates the refresh token
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ctx["refresh_token"]},
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != ctx["access_token"]

    # Reusing the old rotated refresh token fails
    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ctx["refresh_token"]},
    )
    assert reused.status_code == 401

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
async def test_user_profile_update_and_change_password(client: AsyncClient) -> None:
    ctx = await register_and_login(client, email="bob@example.com", full_name="Bob Tran")

    me = await client.get("/api/v1/users/me", headers=ctx["headers"])
    assert me.status_code == 200
    assert me.json()["full_name"] == "Bob Tran"

    patched = await client.patch(
        "/api/v1/users/me",
        headers=ctx["headers"],
        json={"full_name": "Bob Updated"},
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
