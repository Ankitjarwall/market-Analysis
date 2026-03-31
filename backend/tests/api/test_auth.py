"""Integration tests for auth endpoints — tests against running backend."""

import os
import pytest
from httpx import AsyncClient

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# Credentials matching db/seed.py
ADMIN_EMAIL = "admin@marketplatform.io"
ADMIN_PASS = "Admin@123!"


@pytest.fixture
async def http_client():
    async with AsyncClient(base_url=BASE_URL, timeout=10) as c:
        yield c


@pytest.fixture
async def admin_token(http_client):
    resp = await http_client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_health_endpoint(http_client):
    resp = await http_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(http_client):
    resp = await http_client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(http_client):
    resp = await http_client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpassword"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(http_client):
    resp = await http_client.post("/auth/login", json={"email": "nobody@example.com", "password": "anypassword"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(http_client, admin_token):
    resp = await http_client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == ADMIN_EMAIL
    assert resp.json()["role"] == "super_admin"


@pytest.mark.asyncio
async def test_get_me_without_token(http_client):
    resp = await http_client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(http_client, admin_token):
    resp = await http_client.post("/auth/refresh", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_logout(http_client):
    login = await http_client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert login.status_code == 200
    token = login.json()["access_token"]
    resp = await http_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
