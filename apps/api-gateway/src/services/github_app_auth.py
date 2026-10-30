import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, Union
import httpx
import jwt

from ..config import settings

logger = logging.getLogger(__name__)


class GitHubAppAuthService:
    """
    Manages GitHub App authentication:
    - Generates RS256 JWT using GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY
    - Exchanges JWT for installation access tokens per installation ID
    - Caches installation tokens in memory until shortly before expiration (60s buffer)
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        self._app_id = app_id or settings.GITHUB_APP_ID
        self._private_key = private_key or settings.GITHUB_APP_PRIVATE_KEY
        self._api_base = (api_base or settings.GITHUB_API_BASE).rstrip("/")
        # In-memory token cache: {installation_id: (token, expires_at_timestamp)}
        self._tokens: Dict[str, Tuple[str, float]] = {}

    def _get_private_key_pem(self) -> str:
        key = self._private_key or settings.GITHUB_APP_PRIVATE_KEY
        if not key:
            raise ValueError(
                "GITHUB_APP_PRIVATE_KEY is not set. Please configure it in your environment or .env file."
            )
        # If it's a file path
        if os.path.exists(key):
            with open(key, "r", encoding="utf-8") as f:
                return f.read().strip()
        # If newlines are escaped
        if "\\n" in key and "\n" not in key:
            return key.replace("\\n", "\n").strip()
        return key.strip()

    def generate_app_jwt(self, expiration_seconds: int = 540) -> str:
        """
        Generates an RS256 JWT signed with the GitHub App's private key.
        GitHub allows maximum 10 minutes (600s). We default to 9 minutes (540s).
        """
        app_id = self._app_id or settings.GITHUB_APP_ID
        if not app_id:
            raise ValueError("GITHUB_APP_ID is not configured.")

        pem_key = self._get_private_key_pem()
        now = int(time.time())
        payload = {
            # Issued at time, 60 seconds in the past to account for clock drift
            "iat": now - 60,
            # Expiration time
            "exp": now + expiration_seconds,
            # GitHub App ID
            "iss": str(app_id),
        }
        return jwt.encode(payload, pem_key, algorithm="RS256")

    async def get_installation_token(
        self,
        installation_id: Union[str, int],
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """
        Retrieves an installation access token for the given GitHub App installation.
        Returns cached token if still valid (with 60-second expiration buffer).
        """
        inst_id_str = str(installation_id)
        now = time.time()

        # Check in-memory cache
        if inst_id_str in self._tokens:
            token, exp_timestamp = self._tokens[inst_id_str]
            if now < (exp_timestamp - 60):
                return token

        # Fetch fresh token from GitHub App installation endpoint
        app_jwt = self.generate_app_jwt()
        url = f"{self._api_base}/app/installations/{inst_id_str}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async def _do_request(c: httpx.AsyncClient) -> str:
            res = await c.post(url, headers=headers)
            if res.status_code not in (200, 201):
                logger.error(
                    f"Failed to obtain installation token for {inst_id_str}: {res.status_code} {res.text}"
                )
                res.raise_for_status()

            data = res.json()
            token = data["token"]
            expires_at_str = data.get("expires_at")
            if expires_at_str:
                clean_exp = expires_at_str.replace("Z", "+00:00")
                exp_ts = datetime.fromisoformat(clean_exp).timestamp()
            else:
                exp_ts = now + 3600  # Default 1 hour fallback

            self._tokens[inst_id_str] = (token, exp_ts)
            return token

        if client is not None:
            return await _do_request(client)
        else:
            async with httpx.AsyncClient(timeout=10.0) as default_client:
                return await _do_request(default_client)

    def clear_cache(self) -> None:
        """Clears the token cache (useful for testing)."""
        self._tokens.clear()


github_app_auth = GitHubAppAuthService()

