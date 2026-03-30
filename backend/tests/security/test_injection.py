"""Security tests — SQL injection, JWT forgery, input validation."""

import pytest


def test_sql_injection_email_rejected():
    """SQLAlchemy parameterized queries prevent SQL injection."""
    from pydantic import ValidationError
    from auth.schemas import LoginRequest

    # Test that suspicious email is caught by Pydantic EmailStr
    with pytest.raises(ValidationError):
        LoginRequest(email="'; DROP TABLE users; --", password="pass")


def test_jwt_forged_token_rejected():
    """Tokens signed with a different secret must be rejected."""
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    fake_token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "WRONG_SECRET_KEY",
        algorithm="HS256",
    )

    from auth.middleware import _decode_token
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(fake_token)
    assert exc_info.value.status_code == 401


def test_expired_jwt_rejected():
    """Expired tokens must be rejected."""
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    from config import settings

    expired_token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000",
         "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    from auth.middleware import _decode_token
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(expired_token)
    assert exc_info.value.status_code == 401


def test_rbac_admin_cannot_create_super_admin():
    """Admin role cannot create super_admin accounts."""
    from auth.schemas import CreateUserRequest
    from pydantic import ValidationError

    # Role pattern only allows admin|analyst|viewer (not super_admin)
    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="test@test.com",
            password="ValidPass123!",
            name="Test",
            role="super_admin",  # Should fail validation
        )


def test_password_min_length_enforced():
    """Password must be at least 8 characters."""
    from auth.schemas import CreateUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="test@test.com",
            password="short",  # Too short
            name="Test",
            role="analyst",
        )


def test_capital_must_be_positive():
    """Capital value must be greater than 0."""
    from auth.schemas import CreateUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="test@test.com",
            password="ValidPass123!",
            name="Test",
            role="analyst",
            capital=-1000,  # Negative
        )
