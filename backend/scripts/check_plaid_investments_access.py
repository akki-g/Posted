"""Confirm the Plaid trial can create an investments Link token.

Usage: uv run python scripts/check_plaid_investments_access.py   (from backend/)
Never prints the client secret.
"""

import asyncio
import sys

import httpx

sys.path.insert(0, ".")
from app.config import get_settings  # noqa: E402
from app.providers.plaid.client import PlaidClient  # noqa: E402


async def main() -> None:
    settings = get_settings()
    if not settings.plaid_configured:
        print("[Plaid] SKIP -> PLAID_CLIENT_ID / PLAID_SECRET not set")
        return
    client = PlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_environment,
    )
    try:
        result = await client.create_link_token(
            user_id="access-check",
            client_name=settings.app_name,
            products=["investments"],
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"[Plaid] FAIL ({settings.plaid_environment}) -> {exc}")
        return
    token = str(result.get("link_token") or "")
    print(
        f"[Plaid] OK -> investments Link token created "
        f"({settings.plaid_environment}, token …{token[-6:]})"
        if token
        else "[Plaid] FAIL -> no link_token in response"
    )


if __name__ == "__main__":
    asyncio.run(main())
