# Guide 06 — Transaction Normalization

[← Money roadmap](05-MONEY-ROADMAP.md) | [Next: Ledger reconciliation →](07-LEDGER-RECONCILIATION.md)

**You write:** `backend/app/money/normalize.py`

**Immediate goal:** make `backend/app/tests/user_owned/test_money_normalize.py` pass without importing Plaid, SQLAlchemy, or FastAPI.

## 1. Start with one test

Open these files side by side:

1. `app/money/normalize.py`
2. `app/money/models.py`
3. `app/money/enums.py`
4. `app/tests/user_owned/test_money_normalize.py`
5. `app/tests/user_owned/money_factories.py`

From `backend`, run:

```bash
uv run pytest -m user_owned app/tests/user_owned/test_money_normalize.py -q
```

Then isolate the first behavior:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_money_normalize.py::test_valid_transaction_is_canonicalized -q
```

## 2. What normalization does

Provider adapters emit `TransactionObservation`. It is provider-neutral in shape, but its values are still not trusted. Normalization validates those values, resolves the internal account, and creates a deterministic `NormalizedTransaction`.

Input example:

```text
provider account = plaid-checking
amount           = Decimal("6.50")
currency         = "usd"
merchant         = "  NORTHSTAR   COFFEE  "
authorized_at    = 2026-07-22T12:00:00+00:00
status           = POSTED
```

Canonical result:

```text
account_id       = Posted's UUID for plaid-checking
account_type     = CHECKING
amount           = Decimal("6.50")
currency         = "USD"
merchant         = "Northstar Coffee"
occurred_at      = timezone-aware UTC time
fingerprint      = stable non-empty digest
```

## 3. Understand account resolution

The `resolve_account` callback is the only way this function converts a provider account ID into Posted identity:

```python
account = resolve_account(observation.provider_account_id)
```

It returns `MoneyAccountIdentity` or `None`. Copy `account_id` and `account_type` from the result. Do not build a second account dictionary in this module.

This keeps account lookup replaceable: tests use an in-memory resolver, while production uses records created from Plaid or FinanceKit.

## 4. Implement in four passes

### Pass 1 — Validate in a fixed order

For each observation, apply these rules in order:

| Condition | Rejection reason |
|---|---|
| amount is zero or negative | `INVALID_AMOUNT` |
| currency is missing or not three alphabetic characters | `INVALID_CURRENCY` |
| neither provider ID nor enough fields for a fingerprint exist | `MISSING_IDENTITY` |
| chosen occurrence time is missing, naive, or invalid | `INVALID_TIMESTAMP` |
| account resolver returns `None` | `UNRESOLVED_ACCOUNT` |

The occurrence time is:

```text
authorized_at when present
otherwise posted_at
```

Require a timezone. Convert valid times to UTC with `astimezone(UTC)`. Do not attach UTC to a naive time; that guesses what the provider meant. Reject it.

Construct `RejectedMoneyTransaction` with the original observation, enum reason, and a concise detail. Rejections are data, not exceptions.

Run the amount, timestamp, and account tests after this pass.

### Pass 2 — Canonicalize text and categories

Use small private helpers rather than one long loop.

Whitespace normalization means:

```python
" ".join(value.split())
```

For the exercise, canonical merchant rules are:

1. Use `merchant_name` when nonblank.
2. Otherwise use `description`.
3. Collapse whitespace.
4. Convert the all-upper/all-lower test input to title case.

This makes the factory input become `Northstar Coffee`. In a production hardening pass, title casing would be replaced with a merchant-alias table because brands such as `iFixit` and `AT&T` have intentional capitalization.

Other canonical values:

```text
currency         -> stripped uppercase, e.g. USD
description      -> collapsed whitespace
category_primary -> stripped uppercase, or UNCATEGORIZED
category_detailed/payment_channel -> stripped value or None
```

Never round the amount during normalization. Keep the provider's exact `Decimal` value.

### Pass 3 — Create a stable fingerprint

The fingerprint identifies an observation even when a provider transaction ID is unavailable. It must not depend on input order or Python's randomized `hash()`.

Build a delimiter-separated string from stable canonical fields:

```text
source
account_id
provider_transaction_id or empty string
direction
amount in fixed decimal form
currency
merchant
occurred_at in UTC ISO-8601
```

Encode it as UTF-8 and hash it with SHA-256 from `hashlib`. Use `.hexdigest()`.

Why include both provider ID and economic fields? The provider ID is strongest when present; the remaining fields make the fallback deterministic and auditable. Do not include `received_at` or the current clock.

### Pass 4 — Stable result ordering

The same observations in reverse order must produce the same result. Sort normalized transactions by comparable canonical fields, for example:

```text
(occurred_at, source value, provider ID or "", fingerprint)
```

Sort rejected values using fields from their observations, replacing every optional string with `""`. Return tuples:

```python
TransactionNormalizationResult(
    transactions=tuple(sorted_transactions),
    rejected=tuple(sorted_rejections),
)
```

Do not mutate the input sequence.

## 5. Exact implementation walkthrough

The file already contains these mechanical helpers:

```python
_is_timezone_aware
_occurrence_time
_clean_text
_clean_optional_text
_merchant_name
_transaction_sort_key
_rejection_sort_key
```

Do not rewrite them. You own the trust boundary: validation order, account resolution,
fingerprint identity, and construction of accepted/rejected records.

Add these imports to the starter file:

```python
from datetime import UTC
from decimal import Decimal
from hashlib import sha256

from app.money.enums import TransactionRejectionReason
from app.money.models import NormalizedTransaction, RejectedMoneyTransaction
```

### 5.1 Choose and validate the timestamp

```python
PSEUDOCODE _rejection_reason(observation):
    IF observation.amount <= Decimal("0"):
        return TransactionRejectionReason.INVALID_AMOUNT

    currency = observation.currency.strip()
    IF len(currency) != 3 OR NOT currency.isalpha():
        return TransactionRejectionReason.INVALID_CURRENCY

    occurred_at = _occurrence_time(observation)
    fallback_text = _clean_optional_text(observation.merchant_name) OR \
                    _clean_optional_text(observation.description)

    IF observation.provider_transaction_id is None AND fallback_text is None:
        return TransactionRejectionReason.MISSING_IDENTITY

    IF occurred_at is None OR NOT _is_timezone_aware(occurred_at):
        return TransactionRejectionReason.INVALID_TIMESTAMP

    IF observation.posted_at exists AND NOT _is_timezone_aware(observation.posted_at):
        return TransactionRejectionReason.INVALID_TIMESTAMP

    return None
```

Account resolution happens after these checks because `UNRESOLVED_ACCOUNT` is last in the
documented rejection order.

### 5.2 Build the fingerprint from canonical values

```python
PSEUDOCODE _fingerprint(
    observation,
    account,
    currency,
    merchant,
    occurred_at,
):
    fields = (
        observation.source.value,
        str(account.account_id),
        observation.provider_transaction_id OR "",
        observation.direction.value,
        format(observation.amount, "f"),
        currency,
        merchant,
        occurred_at.isoformat(),
    )

    seed = "|".join(fields)
    return sha256(seed.encode("utf-8")).hexdigest()
```

The helper accepts already-canonical values so it cannot accidentally hash lowercase currency
or uncollapsed merchant text.

### 5.3 Normalize one accepted observation

```python
PSEUDOCODE _normalize_one(observation, account):
    occurred_at = _occurrence_time(observation).astimezone(UTC)
    posted_at = (
        observation.posted_at.astimezone(UTC)
        IF observation.posted_at exists
        ELSE None
    )

    currency = observation.currency.strip().upper()
    merchant = _merchant_name(observation)
    description = _clean_text(observation.description)
    primary_category = (
        _clean_optional_text(observation.category_primary) OR "UNCATEGORIZED"
    ).upper()
    detailed_category = _clean_optional_text(observation.category_detailed)
    payment_channel = _clean_optional_text(observation.payment_channel)

    return NormalizedTransaction(
        account_id=account.account_id,
        account_type=account.account_type,
        source=observation.source,
        provider_transaction_id=observation.provider_transaction_id,
        pending_provider_transaction_id=observation.pending_provider_transaction_id,
        status=observation.status,
        direction=observation.direction,
        amount=observation.amount,
        currency=currency,
        merchant_name=merchant,
        description=description,
        occurred_at=occurred_at,
        posted_at=posted_at,
        category_primary=primary_category,
        category_detailed=detailed_category,
        payment_channel=payment_channel,
        fingerprint=_fingerprint(
            observation,
            account,
            currency,
            merchant,
            occurred_at,
        ),
    )
```

### 5.4 Assemble the batch function

`resolve_account` is supplied by the caller. Call it; do not build your own account lookup:

```python
PSEUDOCODE normalize_transactions(observations, resolve_account):
    accepted = []
    rejected = []

    FOR observation IN observations:
        reason = _rejection_reason(observation)

        IF reason IS NOT None:
            rejected.append(
                RejectedMoneyTransaction(
                    observation=observation,
                    reason=reason,
                    detail="Transaction rejected: " + reason.value,
                )
            )
            CONTINUE

        account = resolve_account(observation.provider_account_id)

        IF account IS None:
            rejected.append(
                RejectedMoneyTransaction(
                    observation=observation,
                    reason=TransactionRejectionReason.UNRESOLVED_ACCOUNT,
                    detail="Provider account does not map to a Posted account",
                )
            )
            CONTINUE

        accepted.append(_normalize_one(observation, account))

    return TransactionNormalizationResult(
        transactions=tuple(sorted(accepted, key=_transaction_sort_key)),
        rejected=tuple(sorted(rejected, key=_rejection_sort_key)),
    )
```

The learner-owned functions are `_rejection_reason`, `_fingerprint`, `_normalize_one`, and
`normalize_transactions`. Timestamp selection, generic cleanup, and sorting are already
provided.

## 6. Trace the first test by hand

Before coding, write these variable values on paper:

```text
observation.amount                         6.50
canonical currency                         USD
resolve_account("plaid-checking")          checking identity
chosen time                                NOW (authorized_at)
clean merchant                             Northstar Coffee
category                                   FOOD_AND_DRINK
fingerprint input                          stable fields above
```

If your function produces those values, the first test becomes straightforward.

## 7. Common mistakes

- Using `float(observation.amount)` before hashing.
- calling `.replace(tzinfo=UTC)` on a naive time instead of rejecting it.
- using the provider account string as the internal UUID.
- using Python `hash()`, which is not durable between processes.
- sorting on optional values without replacing `None`.
- raising on the first bad record and losing all good records in the batch.

## 8. Completion check

```bash
uv run pytest -m user_owned app/tests/user_owned/test_money_normalize.py -q
```

You should be able to explain why provider mapping handles Plaid's sign convention, while this function handles Posted's trust and identity rules.
