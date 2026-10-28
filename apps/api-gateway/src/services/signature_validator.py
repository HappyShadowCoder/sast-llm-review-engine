import hmac
import hashlib
from typing import Optional
from fastapi import HTTPException, status


class SignatureValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


def verify_github_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret: str,
) -> bool:
    """
    Validates GitHub X-Hub-Signature-256 against HMAC-SHA256 of raw body.
    Header format: 'sha256=<64-character-hex-digest>'
    """
    if not signature_header:
        raise SignatureValidationError("Missing X-Hub-Signature-256 header")

    if not signature_header.startswith("sha256="):
        raise SignatureValidationError("Invalid signature header format; must start with 'sha256='")

    expected_signature = signature_header[len("sha256="):]
    computed_mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    )
    computed_signature = computed_mac.hexdigest()

    if not hmac.compare_digest(computed_signature, expected_signature):
        raise SignatureValidationError("Invalid GitHub webhook signature")

    return True


def verify_gitlab_token(
    token_header: Optional[str],
    expected_secret: str,
) -> bool:
    """
    Validates GitLab X-Gitlab-Token header using constant-time comparison.
    """
    if not token_header:
        raise SignatureValidationError("Missing X-Gitlab-Token header")

    if not hmac.compare_digest(token_header, expected_secret):
        raise SignatureValidationError("Invalid GitLab webhook token")

    return True
