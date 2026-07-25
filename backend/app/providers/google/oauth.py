from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleUserInfo(BaseModel):
    sub: str
    email: str
    name: str | None = None
    picture: str | None = None
    email_verified: bool = False


class GoogleOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http

    def authorization_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, *, code: str) -> str:
        response = await self._request(
            "POST",
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
            },
        )
        access_token = response.json().get("access_token")
        if not access_token:
            raise ValueError("Google token response did not include an access token")
        return access_token

    async def fetch_userinfo(self, *, access_token: str) -> GoogleUserInfo:
        response = await self._request(
            "GET",
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return GoogleUserInfo.model_validate(response.json())

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(timeout=20)
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                await client.aclose()
