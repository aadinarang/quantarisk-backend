import pytest
from unittest.mock import patch, MagicMock
from app.services.auth import create_access_token


def test_create_access_token_returns_string():
    token = create_access_token(user_id=1, email="test@example.com")
    assert isinstance(token, str)
    assert len(token) > 20


def test_create_access_token_different_users_different_tokens():
    token1 = create_access_token(user_id=1, email="user1@example.com")
    token2 = create_access_token(user_id=2, email="user2@example.com")
    assert token1 != token2


def test_hash_password_returns_string():
    with patch("app.services.auth.pwd_context") as mock_ctx:
        mock_ctx.hash.return_value = "$2b$12$fakehash"
        from app.services.auth import hash_password
        result = hash_password("secret")
        assert isinstance(result, str)
        mock_ctx.hash.assert_called_once_with("secret")


def test_verify_password_correct():
    with patch("app.services.auth.pwd_context") as mock_ctx:
        mock_ctx.verify.return_value = True
        from app.services.auth import verify_password
        result = verify_password("secret", "$2b$12$fakehash")
        assert result == True


def test_verify_password_incorrect():
    with patch("app.services.auth.pwd_context") as mock_ctx:
        mock_ctx.verify.return_value = False
        from app.services.auth import verify_password
        result = verify_password("wrong", "$2b$12$fakehash")
        assert result == False
