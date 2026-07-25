# Google Login + User Menu

## Goal

Add a login page backed by Google OAuth, and move the Settings entry point into a user menu (opened from the avatar in `AppShell`), instead of it living as its own nav item.

## Background

There is currently no real authentication. Every backend request resolves to a single hardcoded user via `get_current_user_id` (`backend/app/api/deps.py`), which falls back to `settings.dev_user_id` when no `X-Posted-User-Id` header is sent. The frontend has no login screen at all, and the "user menu" is a static `AM`-initialed circle in `AppShell.tsx`'s topbar with no interaction. `Settings` today is only reachable via the mobile bottom-nav tab (`mobileNav` in `AppShell.tsx`) — it isn't in the desktop sidebar nav groups at all.

Scope for this pass, per user decisions:
- **Web only.** Native (iOS/Android) keeps using the dev user; no `expo-auth-session` native flow yet.
- **Optional auth.** Logging in is additive — if nobody has signed in, the app keeps working exactly as it does today (dev user, demo data). Nothing is gated behind login in this pass.
- The user already has a Google OAuth client ID/secret; env vars are added for them to fill in.

## Design

### 1. Backend config

`backend/app/config.py` gains:
- `google_client_id: str | None = None`
- `google_client_secret: str | None = None`
- `google_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/google/callback"`
- `frontend_login_callback_url: str = "http://127.0.0.1:8081/login/callback"`
- `google_configured` property (mirrors `schwab_configured`)

`.env.example` gets the corresponding `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_LOGIN_CALLBACK_URL` entries (blank values, with a comment on what to whitelist in Google Cloud Console).

### 2. Google OAuth client

New `backend/app/providers/google/oauth.py`, following the shape of `providers/schwab/oauth.py`:
- `GoogleOAuthClient(client_id, client_secret, redirect_uri)` with:
  - `authorization_url(state) -> str` — builds the `https://accounts.google.com/o/oauth2/v2/auth` URL with `response_type=code`, `scope=openid email profile`, `prompt=select_account`.
  - `async exchange_code(code) -> str` — POSTs to `https://oauth2.googleapis.com/token`, returns the access token.
  - `async fetch_userinfo(access_token) -> GoogleUserInfo` — GETs `https://www.googleapis.com/oauth2/v3/userinfo` with the access token, returns `{sub, email, name, picture, email_verified}`.

This avoids needing a JWT/JWKS-verification dependency: the code exchange happens server-to-server with the client secret, so trusting the userinfo response is safe (same trust model as the existing Schwab code-exchange flow).

### 3. Session tokens

New `backend/app/security/session_token.py`, a small standalone signed-token helper (same HMAC + base64 technique as `providers/schwab/oauth.py`'s `create_oauth_state`/`verify_oauth_state`, generalized to sign an arbitrary string payload with a caller-supplied TTL, since the CSRF state has no user to embed yet while the session token does):
- `sign_payload(payload: str, secret: str, ttl: timedelta) -> str`
- `verify_payload(token: str, secret: str, ttl: timedelta) -> str | None` — returns `None` (not a raised error) on invalid/expired tokens, since callers treat that as "not valid" rather than a hard failure.
- Two thin wrappers on top: `create_session_token(user_id, secret) -> str` / `verify_session_token(token, secret) -> UUID | None` (30 day TTL, payload is `str(user_id)`).

The CSRF `state` for the Google authorize step is `sign_payload(secrets.token_urlsafe(16), secret, ttl=10min)` directly — there's no user id to embed at that point (unlike Schwab's `state`, which is created for an already-known user).

The existing Schwab `create_oauth_state`/`verify_oauth_state` are untouched — not refactored to share this helper, to keep this change additive and low-risk.

### 4. Auth routes

New `backend/app/api/routes/auth.py`:
- `GET /api/v1/auth/google/authorize` (public) → generates the short-lived signed CSRF `state` described above, returns `{authorization_url}` via the existing `OAuthAuthorizeResponse` schema.
- `GET /api/v1/auth/google/callback` (public, `include_in_schema=False`, matches the Schwab callback style) → verifies `state`, exchanges `code`, fetches userinfo, upserts a `User` row by email (`display_name` from Google's `name`, falling back to the email's local part), issues a session token, redirects (`RedirectResponse`) to `frontend_login_callback_url?session=<token>`. On error/denied, redirects with `?error=1` instead.
- `GET /api/v1/auth/me` (requires a valid Bearer session token) → `{id, email, display_name}` via a new `AuthUser` schema in `schemas.py`.

Registered in `backend/app/api/router.py`.

### 5. Resolving the current user

`get_current_user_id` (`backend/app/api/deps.py`) gains an `authorization: str | None = Header(default=None)` param. Resolution order:
1. If `Authorization: Bearer <token>` is present and `verify_session_token` succeeds → that user id.
2. Else existing behavior: `X-Posted-User-Id` header, else `settings.dev_user_id`.

This is the entire mechanism that makes auth optional — every existing route already depends on `get_current_user_id` and needs no other change.

### 6. Frontend session handling

- New `apps/client/src/lib/auth.ts`: `getToken()`/`setToken(token: string | null)` backed by `window.localStorage` under `Platform.OS === 'web'` (no-op on native, since native is out of scope this pass).
- New `apps/client/src/lib/AuthContext.tsx`: `AuthProvider` + `useAuth()` hook. Holds `{ user, isLoading, signOut }`; on mount and whenever the token changes, fetches `GET /auth/me` (via react-query) when a token exists, clearing it if the request 401s. `signOut()` clears the token and resets the query cache for `['auth-me']`.
- `apps/client/src/lib/api.ts`: the shared request helper attaches `Authorization: Bearer <token>` when `getToken()` returns one.
- `apps/client/src/lib/types.ts`: add `AuthUser = { id: string; email: string; display_name: string }`.
- `_layout.tsx`: wrap the existing `QueryClientProvider` children in `AuthProvider`; register two new `Stack.Screen`s: `login` and `login/callback`.

### 7. Login page

`apps/client/src/app/login.tsx`: centered card (reuses existing `colors`/`spacing` tokens, no new design system), "Continue with Google" button. On press: `api.googleAuthorize()` (`GET /auth/google/authorize`) then `window.location.href = authorization_url`. Guarded by `Platform.OS === 'web'` — on native it renders a "Sign-in is available on the web app for now" message instead of a broken button.

`apps/client/src/app/login/callback.tsx`: reads `session` from `useLocalSearchParams`, calls `setToken(session)`, invalidates `['auth-me']`, `router.replace('/')`. If `error` is present instead, shows a short failure message with a link back to `/login`.

### 8. User menu

`apps/client/src/components/AppShell.tsx`:
- Remove `{ label: 'Settings', href: '/settings', icon: Settings }` from `mobileNav` (its only current entry point).
- The topbar avatar becomes a `Pressable` toggling local `menuOpen` state. When open, renders a small absolutely-positioned dropdown (plus a full-screen transparent `Pressable` behind it to close on outside tap — standard RN pattern, no new library):
  - Header row: user's `display_name`/`email` initials + name if `useAuth().user` is set, else "Not signed in".
  - "Settings" row → `router.push('/settings')`.
  - If signed in: "Sign out" row → `signOut()` then `router.replace('/')`.
  - If signed out: "Sign in with Google" row → `router.push('/login')`.
- Avatar initials are derived from `user.display_name` when present, else the existing static fallback.

### 9. Settings page account panel

`apps/client/src/app/settings.tsx` gets one new panel at the top of `settingsGrid`, above "Banking connections": shows the signed-in user's name/email, or "Using the demo account — sign in with Google to personalize" with a link to `/login` when signed out. Uses the same `SectionHeader`/panel styling already used by the rest of the page — no new component.

## Out of scope

- Native (iOS/Android) Google sign-in — dev user continues to be used there.
- Gating any existing screen/route behind authentication.
- Account linking, multiple OAuth providers, email/password login.
- Logout revocation of Google's own session (this only clears Posted's local session token).
- Editing profile info (name/picture) from within Posted.
