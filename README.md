# Posted

Posted is a learning-first personal-finance and portfolio app. The mobile MVP supports money management plus read-only Charles Schwab portfolio synchronization, with safe demo data available before connecting providers.

The client is a single Expo/React Native application for web, iOS, and Android. The backend is Python 3.12 with FastAPI, SQLAlchemy asyncio, SQLite for one-command local development, and PostgreSQL support for deployment.

## What works now

- Mobile-first money home with cash/card balances, weekly cash flow, categories, and recent activity
- Searchable bank/card transactions and explainable recurring-charge review
- Native Plaid Link onboarding plus paginated transaction synchronization and manual refresh
- Pull-to-refresh behavior on the core money screens
- Mobile Investing tab with Schwab accounts, balances, holdings, gains, privacy mode, and manual sync
- Seeded demo portfolio, idempotent demo sync, and typed REST API
- Schwab OAuth, encrypted token storage, automatic access-token refresh, and complete-snapshot reconciliation
- OpenBB news and Schwab account adapters behind provider-neutral contracts
- Plaid Link/account/transaction sync with encrypted credential storage and cursor-safe reconciliation
- Dockerized PostgreSQL/API option
- Agent-owned test suite plus executable specifications for nine learning files

All nine provider-neutral domain modules now pass their executable specifications. Live Schwab and Plaid data runs through the same normalization and reconciliation rules used by the demo/test paths.

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

Then press `w` for web. The web app is normally available at `http://localhost:8081`; API documentation is at `http://127.0.0.1:8000/docs`.

The native Plaid SDK does not run in Expo Go. For the mobile app, create a custom native development build instead:

```bash
cd apps/client
npm run dev:ios
# or
npm run dev:android
```

For an installable EAS development build, run `npx eas-cli build --profile development --platform ios` (or `android`). App-store builds use the included `production` profile, but still require your Apple/Google signing accounts and production API URL.

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

All nine files are implemented. Keep `make learning-check` green when changing their invariants.

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
- [Schwab MVP setup and testing](guides/11-SCHWAB-MVP-TESTING.md)
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

Add the desired provider key to `.env`; the adapter defaults to OpenBB's `yfinance` provider for development. For Schwab, use the exact callback URL approved for your app, then follow [the Schwab MVP testing guide](guides/11-SCHWAB-MVP-TESTING.md). Never commit `.env`.

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
