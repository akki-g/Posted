from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

TRADER_BASE_URL = "https://api.schwabapi.com/trader/v1"


class SchwabTraderClient:
    def __init__(
        self,
        *,
        access_token: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._http = http

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def get_accounts_with_positions(self) -> list[dict[str, Any]]:
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(timeout=20)
        try:
            response = await client.get(
                f"{TRADER_BASE_URL}/accounts",
                params={"fields": "positions"},
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Schwab accounts response must be a list")
            return payload
        finally:
            if owns_client:
                await client.aclose()
