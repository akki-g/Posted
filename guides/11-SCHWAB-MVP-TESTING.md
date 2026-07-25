# Guide 11 — Schwab MVP Setup and Testing

[← Banking connectors](10-BANKING-CONNECTORS.md) | [Roadmap](00-LEARNING-ROADMAP.md)

This guide gets the bare read-only Schwab MVP running without exposing an app secret, access
token, refresh token, or full account number to Expo.

## 1. What the finished flow does

```text
Posted mobile app
-> asks Posted API for a signed Schwab authorization URL
-> opens Schwab in the system browser
-> Schwab redirects the authorization code to the Posted API callback
-> Posted exchanges the code and encrypts both provider tokens
-> API redirects the browser back to posted://settings
-> user taps Sync Schwab
-> backend refreshes the access token when needed
-> backend fetches account hashes and the complete positions snapshot
-> reconciliation atomically replaces accounts/positions
-> mobile Investing queries are refreshed
```

The client never receives Schwab credentials or provider tokens. Posted stores Schwab's opaque
account hash as its provider identifier. It uses the full account number only in memory to join
two Schwab responses and retains only the last four digits in the display name.

The MVP is read-only. It does not place, preview, replace, or cancel orders.

## 2. Backend configuration

Copy the example once:

```bash
cp .env.example .env
```

Set these values in `.env`:

```dotenv
APP_ENV=development
DEMO_MODE=false
APP_SECRET=replace-with-output-from-openssl
SCHWAB_CLIENT_ID=your-approved-app-key
SCHWAB_CLIENT_SECRET=your-approved-app-secret
SCHWAB_REDIRECT_URI=https://the-exact-callback-approved-by-schwab/api/v1/connections/schwab/callback
FRONTEND_APP_URL=posted://settings
```

Generate and then keep one stable local vault key:

```bash
openssl rand -hex 32
```

Changing `APP_SECRET` after connecting makes the stored tokens undecryptable. Never prefix any
Schwab value with `EXPO_PUBLIC_`, and never commit `.env`.

`SCHWAB_REDIRECT_URI` must exactly match the callback configured in the approved Schwab app,
including scheme, host, path, port, and trailing-slash behavior. The callback belongs to the
backend, not the Expo client.

For the cleanest first live test, use a separate database instead of reusing demo fixtures:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./posted-live.db
```

When `DEMO_MODE=false`, Posted creates the single local MVP user but does not seed fake balances.
This development user is not production authentication.

## 3. Mobile API configuration

Create `apps/client/.env`:

```dotenv
EXPO_PUBLIC_API_URL=https://your-reachable-api.example.com/api/v1
```

An installed phone cannot reach `127.0.0.1` on your computer. A LAN URL can work for ordinary
local API calls, but the approved Schwab callback normally needs a stable URL that both the
browser and backend can reach. Use the exact deployed/tunneled HTTPS callback registered with
Schwab.

If testing only in the iOS Simulator with a callback Schwab already permits locally, the default
API URL may work. Do not change the approved callback ad hoc; update the Schwab app registration
first.

## 4. Start and verify the backend

```bash
make setup
make api
```

In another terminal:

```bash
curl http://127.0.0.1:8000/api/v1/connections/schwab/status
```

Confirm:

- `configured` is `true`;
- `redirect_uri` is exactly the approved value;
- no secret or token appears in the response.

API documentation is available at `http://127.0.0.1:8000/docs`.

## 5. Build and open the mobile app

The app includes Plaid's native module, so use the custom development client rather than Expo Go:

```bash
cd apps/client
npm install
npm run dev:ios
# or
npm run dev:android
```

For an installable build for your own device:

```bash
npx eas-cli build --profile preview --platform ios
# or use --platform android
```

The mobile bottom navigation has five destinations:

1. **Home** — cash position, weekly spending/income, categories, and recent money activity.
2. **Activity** — searchable bank/card transactions with pending and transfer treatment.
3. **Invest** — total Schwab value, day/total gain, largest holdings, and brokerage accounts.
4. **Recurring** — inferred recurring charges and expected dates.
5. **Settings** — Plaid/Schwab connection state, OAuth launch, manual sync, and preferences.

The Investing screen's eye button hides values. Pull-to-refresh reloads Posted's API data; **Sync
Schwab** is the action that actually calls Schwab and persists a new provider snapshot.

## 6. First connection test

1. Open **Settings**.
2. Confirm **Schwab Trader API** says `READY`.
3. Tap **Connect or reconnect Schwab**.
4. Complete consent in Schwab's browser flow.
5. Confirm the browser returns to `posted://settings?schwab=connected`.
6. Tap **Sync** beside the connected Schwab row, or open **Invest** and tap **Sync Schwab**.
7. Verify account count, last-sync time, total value, and several known position quantities.
8. Tap Sync again. A new idempotency key performs a new snapshot; retrying the same API request
   key returns the original sync run without duplicating positions.

The first successful live snapshot removes seeded demo portfolio history when it detects demo
accounts. Unsupported positions are reported as sync warnings rather than silently converted.
The current core supports equity and ETF positions; account balances still include cash and other
assets in the portfolio total.

## 7. Test without the mobile UI

Get the authorization URL:

```bash
curl http://127.0.0.1:8000/api/v1/connections/schwab/authorize
```

Open `authorization_url` in a browser. Do not paste the returned authorization code or any token
into source control or chat.

After OAuth completes:

```bash
curl http://127.0.0.1:8000/api/v1/connections
```

Copy the Posted connection `id`, then request one sync:

```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{"idempotency_key":"manual-live-test-0001"}' \
  http://127.0.0.1:8000/api/v1/connections/CONNECTION_ID/sync
```

Inspect read-only output:

```bash
curl http://127.0.0.1:8000/api/v1/dashboard
curl http://127.0.0.1:8000/api/v1/holdings
```

## 8. What a successful sync proves

- ownership was checked before using the connection;
- an expiring access token was refreshed server-side;
- refresh-token omission did not erase the existing refresh token;
- opaque Schwab account hashes, not full account numbers, were persisted;
- an incomplete/invalid snapshot could not close existing holdings;
- reconciliation produced deterministic current positions and deltas;
- account totals, gains, weights, and one portfolio snapshot committed together;
- a repeated idempotency key could not create duplicate durable effects.

## 9. Common failures

### `SETUP` instead of `READY`

Restart the backend after adding both `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET`. Check
`/connections/schwab/status`; do not print the environment file.

### Schwab reports a redirect mismatch

Compare the API status response's `redirect_uri` with the approved Schwab value character for
character. Do not use `posted://settings` as the Schwab callback; that is the backend's
post-exchange destination.

### OAuth succeeds but the app does not reopen

Set `FRONTEND_APP_URL=posted://settings`, reinstall/reopen the custom development build, and verify
that `scheme` remains `posted` in `apps/client/app.json`.

### Sync says authorization expired

Use **Connect or reconnect Schwab**. Posted refreshes ordinary expired access tokens, but a missing
or unusable refresh token requires consent again.

### The phone cannot reach the API

Replace `127.0.0.1` with a reachable HTTPS deployment in `EXPO_PUBLIC_API_URL`, rebuild/restart the
client, and ensure the backend CORS origins and firewall permit the client.

### Some holdings are missing

Check the sync response/status and backend safe warning metadata. The current reconciliation MVP
intentionally rejects options, fixed income, mutual funds, and unknown instruments instead of
misrepresenting them as equities.

## 10. Before exposing this beyond your own test

Replace the fixed development user with real authentication, use managed encryption keys, add
database migrations and token-revocation/disconnect flows, move provider sync into a background
worker, redact structured logs, rate-limit public routes, and add monitoring. Do not treat this
personal bare MVP as a multi-user production security boundary.
