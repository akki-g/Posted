# SMS Phone Verification

## Goal

Let a signed-in Posted user prove ownership of a phone number from within the app, and use that to resolve inbound SMS identity — so texting Posted's number only works for someone who has verified their own number, and gets them their own real data (portfolio, spending, news) through the existing assistant.

## Background

The inbound SMS bridge (`backend/app/services/sms.py`, `backend/app/api/routes/signalwire.py`) already routes a text through the exact same assistant used in-app (`send_message` in `app/services/assistant.py`), with the same money/investing/general section routing. The only thing standing in for identity today is `is_local_test_user`: a single hardcoded number (`SIGNALWIRE_LOCAL_TEST_PHONE`) mapped to `settings.dev_user_id`. Anyone else texting already gets `UNLINKED_REPLY` ("this number is not linked for SMS. Link it from Posted Settings first.") — copy that references a Settings flow that doesn't exist yet.

This replaces that hardcoded check with a real per-user verified-number table, plus the Settings UI and endpoints to manage it. SignalWire's Platform Free Trial currently restricts sending to a single verified test number regardless of what we build here — that's an external constraint on *testing*, not on the design. The system is built as it would run once the pending Telnyx premium-plan approval lands and full messaging is unlocked.

## Design

### 1. Data model

New `SmsLink` model in `backend/app/db/models.py`:

```python
class SmsLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sms_links"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

One row per user (`user_id` unique) — requesting a new number overwrites any pending/verified row that user already had. No Alembic in this project; the table is created via the existing `Base.metadata.create_all` startup call, so adding the model is sufficient.

### 2. Code generation and hashing

New `backend/app/services/sms_link.py`:
- `generate_code() -> str`: `secrets.randbelow(1_000_000)`, zero-padded to 6 digits.
- `hash_code(code, secret) -> str`: `hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()` — same construction as `security/session_token.py`, so the code is never stored in plaintext.
- `normalize_phone` is reused from `services/sms.py` (already exists) for all lookups/comparisons.

Constants: `CODE_TTL = timedelta(minutes=10)`, `RESEND_COOLDOWN = timedelta(seconds=60)`, `MAX_VERIFY_ATTEMPTS = 5`, `MAX_REQUESTS_PER_HOUR = 5`.

### 3. Endpoints

New `backend/app/api/routes/sms_link.py`, mounted at `/settings/sms` (registered in `router.py` alongside the existing `/settings` router), all behind `get_current_user_id` (same dependency the rest of `/settings` uses, so it behaves the same in demo mode as every other settings endpoint):

- **`POST /settings/sms/request`** — body `{phone_number: str}`. Validates E.164-ish shape (`^\+[1-9]\d{7,14}$`). Rejects with 429 if `last_sent_at` was under 60s ago. Hourly cap uses a fixed window: if `now - request_window_started_at > 1 hour` (or the row is new), reset `request_window_started_at = now` and `request_count = 1`; otherwise increment `request_count` and reject with 429 once it exceeds `MAX_REQUESTS_PER_HOUR`. Generates + hashes a code, upserts the row (`user_id` is the conflict key), calls `send_sms`. If `send_sms` raises (SignalWire rejects the destination under PFT, network error, etc.), that propagates as a `502` with a clear message — this is a synchronous user-initiated action, unlike the inbound-reply path in `sms.py` which must swallow delivery errors.
- **`POST /settings/sms/verify`** — body `{code: str}`. 404 if no pending row. 400 if `code_expires_at` has passed. 429 + "request a new code" once `attempt_count >= MAX_VERIFY_ATTEMPTS`. Wrong code: increments `attempt_count`, 400. Right code: if another user's row has the same `phone_number` and `verified_at IS NOT NULL`, clear that row first (ownership transfer — proving live receipt of the code is the same bar the original owner cleared). Sets `verified_at = now`, clears `code_hash`/`code_expires_at`, resets `attempt_count`.
- **`DELETE /settings/sms/link`** — deletes the caller's row if present. 204.
- **`GET /settings/sms/link`** — `{status: "none" | "pending" | "verified", phone_number_masked: str | null, opted_out: bool}`. Masked as `•••• ` + last 4 digits.

New schemas in `api/schemas.py`: `SmsLinkRequest`, `SmsVerifyRequest`, `SmsLinkStatus`.

### 4. Inbound identity resolution

`backend/app/services/sms.py`:
- Remove `is_local_test_user` and the `settings.dev_user_id` fallback entirely — no dev-only bypass. Local testing goes through the real flow (verify your own test phone once via the app while running in demo mode, which resolves to `dev_user_id` the same way every other demo-mode request does).
- Add `async def find_verified_user(session, phone_number) -> UUID | None`, querying `SmsLink` for `phone_number == normalize_phone(...)` and `verified_at IS NOT NULL`.
- `process_inbound_sms` calls this instead of `is_local_test_user`. Found → real `user_id` passed into the existing `send_message` call, unchanged. Not found → existing `UNLINKED_REPLY`.

### 5. STOP/START persistence

Currently `STOP`/`START` send canned replies with no durable effect (`services/sms.py` comment: "Local testing has no durable notification preference yet"). Since `SmsLink.opted_out` already exists for this:
- `STOP` on a row matching `from_number` (any status) → `opted_out = True`, send `STOP_REPLY`.
- `START` → `opted_out = False`, send `START_REPLY`.
- `HELP` unaffected.
- Any other message when `opted_out = True` on the resolved link → short "you're opted out, reply START to resume" reply instead of reaching the assistant.

### 6. Settings UI

`apps/client/src/app/settings.tsx` gets a new "Text Messaging" section, same `SectionHeader` + connection-row pattern used for Banking/Investing connections:
- **No link** (`status: "none"`): phone number input + "Send code" button.
- **Pending**: 6-digit code input + "Verify" button; "Resend" disabled for 60s after the last send (mirrors the backend cooldown so the button state doesn't lie).
- **Verified**: masked number + "Unlink" button.

New functions in `apps/client/src/lib/api.ts` (`requestSmsLink`, `verifySmsLink`, `unlinkSmsLink`, `getSmsLinkStatus`) and matching react-query mutations/query in `settings.tsx`, mirroring `connectSchwab`/`syncMoney` in the same file. New types in `apps/client/src/lib/types.ts`: `SmsLinkStatus`.

### 7. Logging

Never log the phone number in full or the code. Where logging is needed (e.g. `send_sms` failures in the new endpoint), mask to last-4 — matches the existing `recipient_suffix=from_number[-4:]` convention already in `sms.py`.

## Testing

- Backend: new `test_sms_link.py` covering request/verify/unlink/status endpoints (happy path, expired code, wrong code, attempt lockout, resend cooldown, hourly request cap, ownership transfer), and updated `test_signalwire.py` cases for `find_verified_user` replacing the old `is_local_test_user` cases, plus STOP/START persistence.
- Manual: the existing `docs`/README local-testing flow, now going through the app's Settings UI to link `SIGNALWIRE_LOCAL_TEST_PHONE` to whichever user is active in demo mode, instead of the hardcoded bypass.

## Out of scope

- Notifying a previous owner when a phone number transfers to a new user on re-verification.
- Multiple verified numbers per user.
- Any change to how SignalWire/Telnyx account-level messaging limits (PFT, 10DLC, toll-free) work — this is purely Posted's own identity layer on top of whichever provider is active.
