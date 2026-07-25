import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, replace
from datetime import date

from app.config import Settings
from app.domain.models import ProviderEventEnvelope
from app.providers.news.alpaca import AlpacaNewsClient
from app.providers.news.finnhub import FinnhubNewsClient
from app.providers.openbb.news import OpenBBNewsAdapter


@dataclass(frozen=True, slots=True)
class NewsFetchResult:
    envelopes: tuple[ProviderEventEnvelope, ...]
    providers: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class MultiSourceNewsAdapter:
    """Fetch configured direct providers concurrently, with OpenBB as a final fallback."""

    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    async def fetch_company_news(
        self,
        *,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> NewsFetchResult:
        requests: list[
            tuple[str, Awaitable[tuple[ProviderEventEnvelope, ...]]]
        ] = []
        if self.settings.alpaca_configured:
            requests.append(
                (
                    "alpaca",
                    AlpacaNewsClient(
                        api_key=self.settings.alpaca_api_key or "",
                        api_secret=self.settings.alpaca_api_secret or "",
                    ).fetch_company_news(
                        symbols=symbols,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    ),
                )
            )
        if self.settings.finnhub_configured:
            requests.append(
                (
                    "finnhub",
                    FinnhubNewsClient(
                        api_key=self.settings.finnhub_api_key or ""
                    ).fetch_company_news(
                        symbols=symbols,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    ),
                )
            )

        if not requests:
            if self.settings.demo_mode:
                return NewsFetchResult(
                    envelopes=(),
                    providers=(),
                    warnings=("Live news is disabled in demo mode until provider keys are added.",),
                )
            requests.append(
                (
                    f"openbb:{self.settings.openbb_news_provider}",
                    OpenBBNewsAdapter(
                        provider=self.settings.openbb_news_provider
                    ).fetch_company_news(
                        symbols=symbols,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    ),
                )
            )

        responses = await asyncio.gather(
            *(request for _, request in requests),
            return_exceptions=True,
        )
        providers: list[str] = []
        warnings: list[str] = []
        provider_envelopes: list[tuple[str, tuple[ProviderEventEnvelope, ...]]] = []
        for (provider, _), response in zip(requests, responses, strict=True):
            if isinstance(response, Exception):
                warnings.append(f"{provider} news failed: {response}")
                continue
            providers.append(provider)
            provider_envelopes.append(
                (
                    provider,
                    tuple(sorted(response, key=lambda item: item.published_at, reverse=True)),
                )
            )

        # This removes obvious provider overlap before the canonical event pipeline
        # performs its stricter URL/title/time-window deduplication. Reserve an even
        # initial quota per source so a high-volume provider cannot crowd the other
        # verified source completely out of a small assistant or UI request.
        quota = max(1, limit // max(len(provider_envelopes), 1))
        preferred = [
            envelope
            for _, envelopes in provider_envelopes
            for envelope in envelopes[:quota]
        ]
        overflow = sorted(
            [
                envelope
                for _, envelopes in provider_envelopes
                for envelope in envelopes[quota:]
            ],
            key=lambda item: item.published_at,
            reverse=True,
        )
        unique: dict[tuple[str, str], ProviderEventEnvelope] = {}
        for envelope in [*preferred, *overflow]:
            identity = (
                (envelope.source_url or "").strip().casefold(),
                " ".join(envelope.headline.casefold().split()),
            )
            existing = unique.get(identity)
            if existing is None:
                if len(unique) >= max(limit, 1):
                    continue
                unique[identity] = envelope
            else:
                summaries = [item for item in (existing.summary, envelope.summary) if item]
                unique[identity] = replace(
                    existing,
                    summary=max(summaries, key=len, default=None),
                    symbols=tuple(sorted({*existing.symbols, *envelope.symbols})),
                )
        return NewsFetchResult(
            envelopes=tuple(
                sorted(unique.values(), key=lambda item: item.published_at, reverse=True)
            ),
            providers=tuple(providers),
            warnings=tuple(warnings),
        )
