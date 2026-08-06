# Posted

Posted is a learning-first personal-finance and portfolio app. The mobile MVP supports money management plus read-only Charles Schwab portfolio synchronization, with safe demo data available before connecting providers.

The client is a single Expo/React Native application for web, iOS, and Android. The backend is Python 3.12 with FastAPI, SQLAlchemy asyncio, SQLite for one-command local development, and PostgreSQL support for deployment.

## What works now

- Mobile-first money home with cash/card balances, weekly cash flow, categories, and recent activity
- Searchable bank/card transactions and explainable recurring-charge review
- Native Plaid Link onboarding plus paginated transaction synchronization and manual refresh
- Pull-to-refresh behavior on the core money screens
- Mobile Investing tab with Schwab accounts, balances, holdings, gains, privacy mode, and manual sync
- Searchable stock research with Alpaca IEX history, Finnhub fundamentals/earnings, and sourced news
- Portfolio insider tracker with Finnhub transactions/MSPR sentiment and grounded AI interpretation
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

Add `ALPACA_API_KEY`, `ALPACA_API_SECRET`, and `FINNHUB_API_KEY` to `.env` to
enable the stock-research page and the multi-source portfolio news feed. Confirm
the configured credentials without printing them:

```bash
cd backend
uv run python scripts/check_news_keys.py
```

Alpaca and Finnhub news is fetched concurrently, normalized, deduplicated, scored,
and stored in the existing impact feed. OpenBB remains a fallback only when neither
direct provider is configured. Install that optional fallback with:

```bash
cd backend
uv sync --extra openbb
```

Add the desired provider key to `.env`; the adapter defaults to OpenBB's `yfinance` provider for development. For Schwab, use the exact callback URL approved for your app, then follow [the Schwab MVP testing guide](guides/11-SCHWAB-MVP-TESTING.md). Never commit `.env`.

The same Finnhub key powers reported insider transactions and monthly insider
sentiment (MSPR). The Insider Activity screen keeps discretionary purchases/sales
separate from awards, gifts, withholding, and option exercises. When
`ANTHROPIC_API_KEY` is configured, Posted adds a portfolio-aware interpretation;
the deterministic signal, source data, and caveats remain available without AI.

For banking, start with Plaid Sandbox variables in `.env`; follow [the connector guide](guides/10-BANKING-CONNECTORS.md). Plaid's native Link SDK requires a custom Expo development build rather than Expo Go. Apple FinanceKit is a later, separately entitled iOS integration and is not a universal Apple Pay subscription ledger.

Investing now supports multiple brokerages: Schwab via OAuth, plus Robinhood and
other Plaid-covered brokerages connected from Settings → Investing connections in
the app. This ships a breaking local-database change — the credential table was
renamed from `oauth_credentials` to `brokerage_credentials` — so existing local
databases must be recreated (`rm backend/*.db`, then restart the API, or just run
`make setup`) and Schwab reconnected afterward.

The provider layer stores only encrypted tokens. A production deployment still needs real user authentication, managed encryption keys, migrations, background workers, verified webhooks, privacy controls, and observability before handling actual financial data.

## Telnyx SMS local test

Posted includes a development-only inbound SMS bridge. It acknowledges Telnyx
immediately, then routes a text from one explicitly configured phone number to
the existing assistant and sends the concise reply back as SMS. It is not enabled
until the Telnyx variables in `.env` are supplied.

1. Create a separate **development** Telnyx API key, buy/assign an SMS-capable
   number to a Messaging Profile, and copy the account's Ed25519 public key
   from the Mission Control Portal. Do not use a production key locally.
2. Set `TELNYX_API_KEY`, `TELNYX_FROM_NUMBER` (E.164), `TELNYX_PUBLIC_KEY`, and
   `TELNYX_LOCAL_TEST_PHONE` (your E.164 mobile number) in `.env`. The latter is
   intentionally mapped only to `DEV_USER_ID` in development. Unlike a
   Twilio-compatible provider, Telnyx's signature does not cover the webhook
   URL, so there's no separate webhook-url setting to keep in sync behind a
   tunnel.
3. Start the API with `make api`, then expose it with `ngrok http 8000`.
4. Set the Messaging Profile's primary webhook to
   `https://YOUR-NGROK-DOMAIN/api/v1/webhooks/telnyx`. Leave webhook signing on;
   Posted verifies Telnyx's Ed25519 `timestamp|raw JSON` signature.
5. Text the Telnyx number from the configured test phone. Try `HELP`, then a
   question such as `What changed in my portfolio today?`.

For a manual endpoint-only check, temporarily set
`TELNYX_ALLOW_UNSIGNED_WEBHOOKS=true` in development and POST the sample
`message.received` payload from Telnyx's documentation. Do not enable that flag
outside local development. `STOP`/`START` replies are exercised for UI testing;
they are not durable opt-out storage yet, so do not use this bridge for real
customer notifications.

## Schema changes without Alembic

This project has no Alembic migrations; `Base.metadata.create_all` only creates
missing tables and never `ALTER`s existing ones. A fresh dev SQLite database
picks up new columns automatically via `create_all`, but the existing prod
Postgres database needs a one-off manual migration at/before deploy whenever a
column is added to an existing table. For example, adding the nullable, indexed
`institution_id` column to `financial_connections` and `brokerage_connections`
required running:

```sql
ALTER TABLE financial_connections ADD COLUMN IF NOT EXISTS institution_id VARCHAR(64);
ALTER TABLE brokerage_connections ADD COLUMN IF NOT EXISTS institution_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_financial_connections_institution_id ON financial_connections (institution_id);
CREATE INDEX IF NOT EXISTS ix_brokerage_connections_institution_id ON brokerage_connections (institution_id);
```

Right after that migration runs, also run
`uv run python scripts/backfill_institution_id.py` (from `backend/`) once.
Existing connections have `institution_id = NULL`, and the new dedup lookup
matches on `institution_id` first, so without the backfill the first re-link
of a pre-existing connection after deploy misses the match and creates a
duplicate connection instead of reusing the existing one. The script is
idempotent and safe to re-run. If a duplicate does slip through (e.g. a user
re-links before the backfill finishes), the Unlink button on the connection
removes it.

## Useful commands

```bash
make check          # backend lint/tests plus frontend typecheck/web export
make learning-check # all nine human-owned executable specs
make docker-up      # PostgreSQL + API with demo data
make docker-down
```

The frontend is built around the Position Spine: Money and Investing are lenses (Everything/Cash/Investments) over one net-worth overview, not separate destinations, with a tappable sync-freshness indicator driven by each connection's real `last_synced_at` rather than a decorative status dot. Visual language stays dense and trading-dashboard-flavored — restrained geometry, neutral surfaces, teal emphasis, Space Mono for every measured figure — with shared `Panel`/`StatTile`/`IconButton`/`ConnectionRow` primitives replacing what used to be independently reimplemented per screen. See `design/approved-design-system.md` and `design/migration-plan.md` for the full rationale and rollout.
