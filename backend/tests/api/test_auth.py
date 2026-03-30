"""Integration tests for auth endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.connection import Base, get_db
from main import app

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(db_session):
    """Create a test admin user."""
    from passlib.context import CryptContext
    import uuid
    from db.models import User

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        id=uuid.uuid4(),
        email="test@admin.local",
        password_hash=pwd.hash("TestPass123!"),
        name="Test Admin",
        role="super_admin",
        capital=200_000,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    resp = await client.post("/auth/login", json={
        "email": "test@admin.local",
        "password": "TestPass123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    resp = await client.post("/auth/login", json={
        "email": "test@admin.local",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    resp = await client.post("/auth/login", json={
        "email": "nobody@nowhere.com",
        "password": "anypassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(client, admin_user):
    # Login first
    login = await client.post("/auth/login", json={
        "email": "test@admin.local",
        "password": "TestPass123!"
    })
    token = login.json()["access_token"]

    # Get me
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@admin.local"
    assert resp.json()["role"] == "super_admin"


@pytest.mark.asyncio
async def test_get_me_without_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client, admin_user):
    login = await client.post("/auth/login", json={
        "email": "test@admin.local",
        "password": "TestPass123!"
    })
    token = login.json()["access_token"]
    resp = await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
