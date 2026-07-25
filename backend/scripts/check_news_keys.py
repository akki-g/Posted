"""Quick sanity check that ALPACA and FINNHUB keys can fetch news.

Usage: uv run python scripts/check_news_keys.py   (from backend/)
"""

import asyncio
import sys
from datetime import date, timedelta

import httpx

sys.path.insert(0, ".")
from app.config import get_settings  # noqa: E402


async def check_alpaca(api_key: str, api_secret: str) -> None:
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
    async with httpx.AsyncClient(
        base_url="https://data.alpaca.markets", headers=headers, timeout=10
    ) as client:
        response = await client.get("/v1beta1/news", params={"symbols": "AAPL", "limit": 1})
    if response.status_code == 200:
        articles = response.json().get("news", [])
        headline = articles[0]["headline"] if articles else "(no articles returned)"
        print(f"[Alpaca]  OK  -> {headline}")
    else:
        print(f"[Alpaca]  FAIL ({response.status_code}) -> {response.text[:200]}")


async def check_finnhub(api_key: str) -> None:
    headers = {"X-Finnhub-Token": api_key}
    async with httpx.AsyncClient(
        base_url="https://finnhub.io/api/v1", headers=headers, timeout=10
    ) as client:
        response = await client.get(
            "/company-news",
            params={"symbol": "AAPL", "from": "2026-07-23", "to": "2026-07-24"},
        )
    if response.status_code == 200:
        articles = response.json()
        headline = articles[0]["headline"] if articles else "(no articles returned)"
        print(f"[Finnhub] OK  -> {headline}")
    else:
        print(f"[Finnhub] FAIL ({response.status_code}) -> {response.text[:200]}")


async def check_finnhub_insider(api_key: str) -> None:
    headers = {"X-Finnhub-Token": api_key}
    async with httpx.AsyncClient(
        base_url="https://finnhub.io/api/v1", headers=headers, timeout=10
    ) as client:
        response = await client.get("/stock/insider-transactions", params={"symbol": "AAPL"})
    if response.status_code == 200:
        articles = response.json()["data"]
        headline = articles[0]["name"] if articles else "(no articles returned)"
        print(f"[Finnhub] OK  -> {headline}")
    else:
        print(f"[Finnhub] FAIL ({response.status_code}) -> {response.text[:200]}")


async def check_finnhub_insider_sentiment(api_key: str) -> None:
    headers = {"X-Finnhub-Token": api_key}
    today = date.today()
    async with httpx.AsyncClient(
        base_url="https://finnhub.io/api/v1", headers=headers, timeout=10
    ) as client:
        response = await client.get(
            "/stock/insider-sentiment",
            params={
                "symbol": "AAPL",
                "from": (today - timedelta(days=370)).isoformat(),
                "to": today.isoformat(),
            },
        )
    if response.status_code == 200:
        points = response.json().get("data", [])
        latest = points[-1].get("mspr") if points else "(no sentiment returned)"
        print(f"[Finnhub] OK  -> latest AAPL insider MSPR: {latest}")
    else:
        print(f"[Finnhub] FAIL ({response.status_code}) -> {response.text[:200]}")


async def main() -> None:
    settings = get_settings()

    if settings.alpaca_configured:
        await check_alpaca(settings.alpaca_api_key, settings.alpaca_api_secret)
    else:
        print("[Alpaca]  SKIP -> ALPACA_API_KEY / ALPACA_API_SECRET not set")

    if settings.finnhub_configured:
        await check_finnhub(settings.finnhub_api_key)
        await check_finnhub_insider(settings.finnhub_api_key)
        await check_finnhub_insider_sentiment(settings.finnhub_api_key)
    else:
        print("[Finnhub] SKIP -> FINNHUB_API_KEY not set")


if __name__ == "__main__":
    asyncio.run(main())
