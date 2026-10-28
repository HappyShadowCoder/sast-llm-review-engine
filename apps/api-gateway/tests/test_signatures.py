import hmac
import hashlib
import pytest
from src.services.signature_validator import (
    SignatureValidationError,
    verify_github_signature,
    verify_gitlab_token,
)


def test_github_signature_valid():
    secret = "my_super_secret"
    body = b'{"action": "opened", "number": 1}'
    expected_hash = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    header = f"sha256={expected_hash}"

    assert verify_github_signature(body, header, secret) is True


def test_github_signature_invalid():
    secret = "my_super_secret"
    body = b'{"action": "opened", "number": 1}'
    header = "sha256=invalidhex0123456789abcdef0123456789abcdef0123456789abcdef01234567"

    with pytest.raises(SignatureValidationError) as exc:
        verify_github_signature(body, header, secret)
    assert exc.value.status_code == 401
    assert "Invalid GitHub webhook signature" in exc.value.detail


def test_github_signature_missing_header():
    secret = "my_super_secret"
    body = b'{"action": "opened"}'

    with pytest.raises(SignatureValidationError) as exc:
        verify_github_signature(body, None, secret)
    assert exc.value.status_code == 401
    assert "Missing X-Hub-Signature-256 header" in exc.value.detail


def test_github_signature_malformed_prefix():
    secret = "my_super_secret"
    body = b'{"action": "opened"}'

    with pytest.raises(SignatureValidationError) as exc:
        verify_github_signature(body, "sha1=abcdef", secret)
    assert exc.value.status_code == 401
    assert "must start with 'sha256='" in exc.value.detail


def test_gitlab_token_valid():
    secret = "gitlab_secret_token_abc"
    assert verify_gitlab_token(secret, secret) is True


def test_gitlab_token_invalid():
    secret = "gitlab_secret_token_abc"
    with pytest.raises(SignatureValidationError) as exc:
        verify_gitlab_token("wrong_token", secret)
    assert exc.value.status_code == 401
    assert "Invalid GitLab webhook token" in exc.value.detail


def test_gitlab_token_missing():
    secret = "gitlab_secret_token_abc"
    with pytest.raises(SignatureValidationError) as exc:
        verify_gitlab_token(None, secret)
    assert exc.value.status_code == 401
    assert "Missing X-Gitlab-Token header" in exc.value.detail
