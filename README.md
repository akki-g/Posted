# Posted

Posted is a learning-first portfolio and personal-finance intelligence app. The current MVP runs end to end with safe demo data and includes seams for Schwab investments, OpenBB/SEC company intelligence, Plaid bank and card accounts, spending analysis, and recurring-charge detection.

The client is a single Expo/React Native application for web, iOS, and Android. The backend is Python 3.12 with FastAPI, SQLAlchemy asyncio, SQLite for one-command local development, and PostgreSQL support for deployment.

## What works now

- Responsive portfolio dashboard with balances, performance history, accounts, and positions
- Searchable impact feed, materiality filters, event explanations, and read state
- Settings and brokerage connection screens
- Money overview with cash/card balances, weekly spending, and category analysis
- Searchable bank/card transactions and explainable recurring-charge review
- Seeded demo portfolio, idempotent demo sync, and typed REST API
- Schwab OAuth authorize/callback plumbing with signed state and encrypted token storage
- OpenBB news and Schwab account adapters behind provider-neutral contracts
- Plaid Link/account/transaction-sync backend seams with encrypted credential storage
- Dockerized PostgreSQL/API option
- Agent-owned test suite plus executable specifications for nine learning files

Live ingestion intentionally does not bypass the human-owned domain modules. Until the relevant implementations pass their specifications, demo data remains the active end-to-end path.

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 22+.

```bash
cp .env.example .env
make setup
make api
```

In a second terminal:

```bash
make client
```

Then press `w` for web, `i` for iOS Simulator, or `a` for an Android emulator. The web app is normally available at `http://localhost:8081`; API documentation is at `http://127.0.0.1:8000/docs`.

For a physical phone, copy `apps/client/.env.example` to `apps/client/.env` and replace the sample IP with your computer's LAN address. Android Emulator automatically uses `10.0.2.2`; web and iOS Simulator use `127.0.0.1`.

## Your learning files

Complete the original five first:

1. `backend/app/portfolio/reconcile.py`
2. `backend/app/events/normalize.py`
3. `backend/app/events/dedupe.py`
4. `backend/app/impact/scoring.py`
5. `backend/app/sync/orchestrator.py`

Then complete the separate money track:

6. `backend/app/money/normalize.py`
7. `backend/app/money/reconcile.py`
8. `backend/app/money/spending.py`
9. `backend/app/money/recurring.py`

Their public contracts live in `backend/app/domain/models.py`. Run the normal suite at any time with `make check`; run your executable specifications with:

```bash
make learning-check
```

Those tests are expected to fail until you implement each exercise. Work in the order shown above—the orchestrator composes the other four.

Start with the [learning roadmap](guides/00-LEARNING-ROADMAP.md), then use the focused guides:

- [Portfolio reconciliation](guides/01-PORTFOLIO-RECONCILIATION.md)
- [Event normalization and deduplication](guides/02-EVENT-PIPELINE.md)
- [Portfolio impact engine](guides/03-IMPACT-ENGINE.md)
- [Synchronization orchestrator](guides/04-SYNC-ORCHESTRATOR.md)
- [Money-domain roadmap](guides/05-MONEY-ROADMAP.md)
- [Transaction normalization](guides/06-TRANSACTION-NORMALIZATION.md)
- [Ledger reconciliation](guides/07-LEDGER-RECONCILIATION.md)
- [Spending classification](guides/08-SPENDING-CLASSIFICATION.md)
- [Recurring transaction detection](guides/09-RECURRING-TRANSACTIONS.md)
- [Plaid and FinanceKit setup](guides/10-BANKING-CONNECTORS.md)
- [Learning companion](guides/POSTED-LEARNING-COMPANION.md)

## Architecture

```text
Expo app (web / iOS / Android)
             |
         REST / JSON
             v
FastAPI routes -> dashboard queries -> PostgreSQL / SQLite
       |                              |
      sync orchestrator (you)
       /                  \
Schwab adapter       OpenBB / SEC adapters
       \                  /
 reconciliation -> normalize -> dedupe -> impact score -> alerts
       (you)          (you)      (you)        (you)

Plaid adapter -> transaction normalization -> ledger reconciliation
                                  |
                         spending + recurring analysis
                         (all four are your money track)
```

The adapters translate vendor payloads at the boundary. Your modules own the business invariants and never depend directly on Schwab, Plaid, OpenBB, FastAPI, or SQLAlchemy.

## Live-provider setup

Install OpenBB only when you are ready to exercise live news retrieval:

```bash
cd backend
uv sync --extra openbb
```

Add the desired provider key to `.env`; the adapter defaults to OpenBB's `yfinance` provider for development. For Schwab, register the exact callback URL shown in `.env.example`, then set `SCHWAB_CLIENT_ID`, `SCHWAB_CLIENT_SECRET`, and a long random `APP_SECRET`. Never commit `.env`.

For banking, start with Plaid Sandbox variables in `.env`; follow [the connector guide](guides/10-BANKING-CONNECTORS.md). Plaid's native Link SDK requires a custom Expo development build rather than Expo Go. Apple FinanceKit is a later, separately entitled iOS integration and is not a universal Apple Pay subscription ledger.

The provider layer stores only encrypted tokens. A production deployment still needs real user authentication, managed encryption keys, migrations, background workers, verified webhooks, privacy controls, and observability before handling actual financial data.

## Useful commands

```bash
make check          # backend lint/tests plus frontend typecheck/web export
make learning-check # all nine human-owned executable specs
make docker-up      # PostgreSQL + API with demo data
make docker-down
```

The frontend visual language is original to Posted: dense trading-dashboard information hierarchy, restrained geometry, neutral surfaces, teal emphasis, and responsive table/card composition. It borrows enterprise dashboard placement patterns without using IBM branding or Carbon components.
