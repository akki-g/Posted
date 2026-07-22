# Guide 10 — Banking Connector Setup

[← Recurring transactions](09-RECURRING-TRANSACTIONS.md) | [Roadmap](00-LEARNING-ROADMAP.md)

This is a read-and-operate guide for agent-owned connector code. Do not write provider HTTP plumbing as a learning exercise. Understand the flow, configure Sandbox, and review how your four money-domain functions fit into synchronization.

## 1. What is implemented

Use this matrix instead of assuming “a seam exists” means “the flow is complete”:

| Capability | Current state | Concrete file |
|---|---|---|
| Report whether Plaid credentials exist | Implemented | `app/api/routes/plaid.py` |
| Create a Plaid Link token | Implemented backend endpoint | `app/api/routes/plaid.py` |
| Exchange a public token and store encrypted access token/accounts | Implemented backend endpoint | `app/api/routes/plaid.py` |
| Call Plaid `/transactions/sync` for one page | Implemented client method | `app/providers/plaid/client.py` |
| Convert one Plaid transaction payload | Implemented mapper | `app/providers/plaid/mapper.py` |
| Loop all sync pages, reconcile, persist, and commit cursor | **Not implemented** | requires a background sync service |
| Receive and verify Plaid webhooks | **Not implemented** | requires route, verification, and queue |
| Open native Plaid Link from Expo | **Not installed** | requires native SDK and development build |
| Read FinanceKit data | **Not implemented or entitled** | later iOS-only adapter |

The Money, Transactions, and Subscriptions screens currently read database/demo API data. The
Settings screen reports Plaid readiness but does not launch Link.

The Expo Plaid Link native UI is intentionally not installed until credentials are available, because adding native code changes the development workflow.

## 2. Start safely with Plaid Sandbox

From the repository root, create local settings if needed:

```bash
cp .env.example .env
```

Edit `.env` and set:

```dotenv
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_sandbox_secret
PLAID_ENVIRONMENT=sandbox
PLAID_WEBHOOK_URL=
PLAID_REDIRECT_URI=
PLAID_ANDROID_PACKAGE_NAME=com.posted.portfolio
APP_SECRET=a-long-random-development-secret
```

Generate a development secret instead of using that literal example:

```bash
openssl rand -hex 32
```

Start the API:

```bash
make setup
make api
```

Never put `PLAID_SECRET`, an access token, or `APP_SECRET` in `EXPO_PUBLIC_*` variables. The client receives only short-lived Link tokens and sends the returned public token to the backend.

Check readiness:

```bash
curl http://127.0.0.1:8000/api/v1/money/connections/plaid/status
```

Before credentials, expect `configured: false`. After restarting the API with both
`PLAID_CLIENT_ID` and `PLAID_SECRET` populated, expect `configured: true` and
`environment: "sandbox"`.

Create a Link token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/money/connections/plaid/link-token
```

With valid Sandbox credentials, the response contains `link_token`, `expiration`, and possibly
`request_id`. A `503` means credentials are still missing; a `502` means Plaid rejected or could
not complete the upstream request.

The exchange endpoint expects JSON from a successful Link session:

```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{"public_token":"public-sandbox-token-from-link"}' \
  http://127.0.0.1:8000/api/v1/money/connections/plaid/exchange
```

Do not type an access token into this request. Link returns a short-lived `public_token`; only
the backend exchanges it and encrypts the resulting `access_token`.

The intended exchange is:

```text
Expo asks Posted backend for link_token
-> native Plaid Link opens
-> user completes Sandbox institution login
-> Plaid returns public_token to Expo
-> Expo POSTs public_token to /exchange
-> backend exchanges it for access_token
-> backend encrypts access_token and stores accounts
```

## 3. Native Expo requirement

Plaid's current React Native SDK contains native iOS and Android code. It supports Expo projects
but does not run in Expo Go. As of this guide's July 2026 verification, Plaid documents the
active 13.x SDK as requiring React Native 0.76+ and Expo 52+; this project uses newer versions.
Recheck the [official compatibility table](https://plaid.com/docs/link/react-native/) before
installing because native requirements change.

When credentials are ready:

```bash
cd apps/client
npm install react-native-plaid-link-sdk
npx expo prebuild
npx expo run:ios
# or: npx expo run:android
```

After installation, add a platform-specific Link component that performs these exact calls:

```text
POST Posted /money/connections/plaid/link-token
-> createPlaidLinkSession with returned link_token
-> session.open()
-> onSuccess receives public_token
-> POST public_token to Posted /money/connections/plaid/exchange
-> invalidate money-connection/account queries
```

Version 13 uses session APIs such as `createPlaidLinkSession`; do not copy examples using removed
legacy `PlaidLink`, `create`, or `open` APIs from older tutorials.

Use a custom development build thereafter. Register the iOS bundle identifier and Android package name shown in `app.json` with Plaid, especially for OAuth institutions. Review the exact version requirements before installation because Plaid releases major SDK versions regularly: <https://plaid.com/docs/link/react-native/>.

For web, use Plaid Link's web package in a platform-specific component rather than trying to load the native module in React Native Web.

## 4. Transaction synchronization

`PlaidClient.sync_transactions()` fetches only one page. The following background service still
needs to be agent-implemented before live transactions flow into Posted:

The background job should loop `/transactions/sync` pages:

```text
starting_cursor = cursor currently stored for this Plaid Item
working_cursor = starting_cursor
added = []
modified = []
removed = []

repeat:
    request /transactions/sync using working_cursor
    append page.added, page.modified, and page.removed
    working_cursor = page.next_cursor
until page.has_more is false

map added + modified payloads to TransactionObservation
call normalize_transactions(...)
call reconcile_ledger(incoming=normalized, existing=stored, removed=removed_refs)

in one short database transaction:
    apply every ledger action
    persist normalization rejections
    save working_cursor as the new durable cursor
    commit
```

Preserve `starting_cursor` until pagination completes. If Plaid reports
`TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION`, discard the accumulated pages and restart from
`starting_cursor`. Save the final cursor only in the same commit that applies every ledger
action. Plaid documents this behavior in its
[Transactions API](https://plaid.com/docs/api/products/transactions/) and
[sync migration guide](https://plaid.com/docs/transactions/sync-migration/).

Do not keep a database transaction open during provider HTTP requests. Fetch pages first or use a short transaction per safely replayable batch.

## 5. Webhooks

Production should receive `SYNC_UPDATES_AVAILABLE`, enqueue a sync job, and return quickly. A webhook is a signal to fetch; it is not the transaction data itself.

Before production:

1. Expose an HTTPS webhook URL.
2. Verify Plaid's signed webhook JWT and request-body hash.
3. Map `item_id` to one owned financial connection.
4. Deduplicate delivery and enqueue work.
5. Never perform a long full sync inside the request handler.
6. Test delivery in Sandbox.

The current project leaves the webhook route out until signature verification and a job queue exist. Accepting unauthenticated financial webhooks would be worse than waiting.

## 6. Balances and freshness

The normal accounts endpoint returns balances cached by Plaid. Treat `last_synced_at` and pending transactions as user-visible freshness information. Do not label data “live” unless the specific provider endpoint and product entitlement guarantee that behavior.

For the MVP:

- transaction webhooks drive ordinary refresh;
- manual refresh can enqueue a sync;
- current/available balance meanings stay distinct;
- card `current_balance` is a liability, not cash;
- connection errors never erase the last known good ledger.

## 7. Apple FinanceKit: what it can and cannot do

FinanceKit is the correct Apple-side research track, not a generic “read every Apple Pay
purchase” API. At this guide's July 2026 verification, Apple lists Apple Card, Apple Cash, and
Savings support in the United States on iOS 17.4+, and a supported-bank open-banking model in
the United Kingdom on iOS 18.4+. Access requires an organization-level Apple Developer account,
user consent, a managed entitlement tied to the bundle ID, and
`NSFinancialDataUsageDescription`. Verify current eligibility on Apple's
[FinanceKit overview](https://developer.apple.com/financekit/) and
[framework documentation](https://developer.apple.com/documentation/financekit) before planning
the adapter.

FinanceKit data is on-device, so the architecture is:

```text
native Swift Expo module
-> FinanceStore / FinanceKitUI authorization
-> map on-device accounts and transactions to Posted observations
-> send canonical-safe observations to backend
-> normal normalization/reconciliation pipeline
```

Create this adapter only after Apple grants the entitlement. It needs an iOS custom build and cannot be meaningfully completed or tested on web/Android.

## 8. Apple Pay and subscriptions limitation

Do not promise a universal Apple Wallet or Apple Pay subscription list. FinanceKit supports specific financial data sources, not every card transaction simply because Apple Pay was used.

StoreKit reports purchases and subscriptions for products offered by **your own app**. It is not an API for reading a user's Netflix, gym, or unrelated App Store subscriptions. Apple's StoreKit overview is at <https://developer.apple.com/storekit/>.

Posted therefore detects recurring charges from bank/card transaction history. The UI must describe them as inferred and direct users to the merchant to manage or cancel them.

## 9. Production security checklist

- Replace the development vault secret with a managed KMS/envelope-encryption design.
- Authenticate real users; the fixed demo user is development-only.
- Enforce ownership on every account, connection, and transaction query.
- Redact tokens and raw provider payloads from logs.
- Add migrations before modifying production schemas.
- Add disconnect/revocation and deletion flows.
- Define retention/export policies for financial data.
- Verify webhooks and rate-limit public endpoints.
- Use Plaid Sandbox and Apple test environments before real accounts.
- Review provider terms, pricing, and privacy disclosures with counsel before launch.

## 10. When the connector track is complete

You should be able to draw where secrets exist, explain why public and access tokens differ, show where the sync cursor commits, and identify exactly which of your pure functions runs on each provider update.
