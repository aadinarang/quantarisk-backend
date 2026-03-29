import pytest
from app.services.auth import hash_password, verify_password, create_access_token


def test_hash_password_returns_string():
    hashed = hash_password("secret")
    assert isinstance(hashed, str)
    assert hashed != "secret"


def test_verify_password_correct():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) == True


def test_verify_password_incorrect():
    hashed = hash_password("secret")
    assert verify_password("wrong", hashed) == False


def test_create_access_token_returns_string():
    token = create_access_token(user_id=1, email="test@example.com")
    assert isinstance(token, str)
    assert len(token) > 20


def test_create_access_token_different_users_different_tokens():
    token1 = create_access_token(user_id=1, email="user1@example.com")
    token2 = create_access_token(user_id=2, email="user2@example.com")
    assert token1 != token2
