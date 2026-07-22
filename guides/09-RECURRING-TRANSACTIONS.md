# Guide 09 — Recurring Transaction Detection

[← Spending classification](08-SPENDING-CLASSIFICATION.md) | [Next: Banking connectors →](10-BANKING-CONNECTORS.md)

**You write:** `backend/app/money/recurring.py`

**Immediate goal:** identify repeated posted outflows with a plausible cadence while rejecting weak or unstable evidence.

## 1. Run the exercise

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_money_recurring.py -q
```

Start with:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_money_recurring.py::test_three_regular_monthly_charges_form_a_stream -q
```

## 2. Detection is an inference

A provider may offer a recurring-transactions product, but Posted still needs a transparent local model that works across providers and explains why something was detected.

The output is a `RecurringStreamCandidate`, not a confirmed cancellation-ready subscription. Rent, insurance, a gym membership, and a monthly donation can all be recurring without being an App Store subscription.

## 3. Filter usable evidence

Only consider transactions that are:

- `POSTED`;
- `OUTFLOW`;
- at or before `as_of`;
- backed by a timezone-aware occurrence time;
- nonblank merchant and currency values.

Pending records can disappear or change amount. Inflows represent a different economic pattern. Ignore both for this exercise.

## 4. Group into candidate streams

Normalize merchant grouping conservatively:

```text
strip -> collapse whitespace -> casefold
```

Use a group key containing at least:

```text
(normalized merchant, uppercase currency)
```

Optionally include category to reduce collisions, but then category drift can split one real subscription. Do not include account ID by default; a user may move a subscription to another card.

Keep a readable merchant name from a deterministic representative, not whichever input arrived first.

Discard groups with fewer than `policy.minimum_occurrences` (three by default).

## 5. Calculate cadence

Sort each group chronologically and calculate day gaps between adjacent charges:

```text
May 22 -> Jun 21 = 30 days
Jun 21 -> Jul 21 = 30 days
gaps = [30, 30]
```

If `policy.frequency_windows` is `None`, use these defaults:

| Frequency | Inclusive day-gap window |
|---|---:|
| `WEEKLY` | 5–9 |
| `BIWEEKLY` | 12–16 |
| `MONTHLY` | 25–35 |
| `QUARTERLY` | 80–100 |
| `ANNUAL` | 350–380 |

Choose a frequency only when every gap falls inside its window. This conservative starter rule avoids calling irregular shopping recurring. A later version may tolerate one missed observation using robust statistics.

## 6. Check amount stability

Compute the exact Decimal average:

```text
average = sum(amounts) / count
variation ratio = (maximum - minimum) / average
```

Reject the group if the ratio exceeds `maximum_amount_variation` (0.25 by default).

For `[10, 10, 30]`, the range is too large relative to the average, so the starter test expects no stream. Constant `[14.99, 14.99, 14.99]` is accepted.

Do not convert to float for money calculations. Float is acceptable only for the final confidence field.

## 7. Predict the next expected date

Use a robust representative gap such as the integer median of observed gaps. Start with:

```text
last charged date + representative gap
```

If that date is not after `as_of.date()`, advance it by the same cadence until it is in the future. This prevents an old inactive sequence from predicting a date in the past. A production hardening rule should eventually expire streams that have missed several cycles.

## 8. Build explainable confidence

The contract requires a float from 0 to 1; it does not require one exact formula. Use simple components you can explain:

- evidence bonus for occurrences beyond the minimum;
- timing consistency based on spread of gaps;
- amount consistency based on the variation ratio;
- recency penalty when the last charge is overdue.

Clamp with:

```python
max(0.0, min(1.0, score))
```

Do not return 100% merely because three timestamps align. Confidence measures evidence quality, not truth.

## 9. Deterministic candidate fields

`stream_key` must be stable. SHA-256 a serialization of normalized merchant, currency, and frequency. Do not use `hash()`.

Populate:

```text
merchant_name       deterministic display name
frequency           detected enum
average_amount      Decimal average
last_amount         chronologically last amount
currency            uppercase currency
last_charged_at     last occurrence time
next_expected_date  future date
confidence          clamped float
transaction_ids     chronological tuple of UUIDs
```

Sort final streams by `(next_expected_date, stream_key)` so reversed inputs compare equal.

## 10. Exact implementation walkthrough

These generic helpers are already implemented:

```python
_merchant_key
_frequency_windows
_amount_variation
_representative_gap
_next_expected_date
_stream_key
_stream_sort_key
```

You own evidence filtering, cadence classification, confidence policy, and candidate assembly.

Add these imports:

```python
from collections import defaultdict

from app.money.enums import TransactionDirection, TransactionStatus
from app.money.models import RecurringStreamCandidate
```

### 10.1 Validate the request and filter evidence

```python
PSEUDOCODE _usable(transaction, as_of):
    return (
        transaction.status IS TransactionStatus.POSTED
        AND transaction.direction IS TransactionDirection.OUTFLOW
        AND transaction.occurred_at has a usable timezone
        AND transaction.occurred_at <= as_of
        AND _merchant_key(transaction.merchant_name) is not empty
        AND transaction.currency.strip() is not empty
    )


PSEUDOCODE detect_recurring_transactions(...):
    IF as_of has no usable timezone:
        raise ValueError("as_of must be timezone-aware")

    active_policy = policy OR RecurringPolicy()

    IF active_policy.minimum_occurrences < 2:
        raise ValueError
    IF active_policy.maximum_amount_variation < Decimal("0"):
        raise ValueError

    groups = defaultdict(list)

    FOR transaction IN transactions:
        IF NOT _usable(transaction, as_of):
            CONTINUE

        key = (
            _merchant_key(transaction.merchant_name),
            transaction.currency.strip().upper(),
        )
        groups[key].append(transaction)
```

Invalid `as_of` is a caller error. A transaction with unusable evidence is ignored because this
function detects candidates; it does not own ledger validation.

### 10.2 Detect a frequency

```python
PSEUDOCODE _detect_frequency(gaps, policy):
    windows = _frequency_windows(policy)

    FOR frequency IN RecurrenceFrequency sorted by frequency.value:
        IF frequency is not in windows:
            CONTINUE

        minimum_days, maximum_days = windows[frequency]
        IF minimum_days <= 0 OR minimum_days > maximum_days:
            raise ValueError("invalid recurrence window")

        IF every gap satisfies minimum_days <= gap <= maximum_days:
            return frequency

    return None
```

The default windows do not overlap. If custom windows overlap, sorting by enum value makes the
winner deterministic, but the better policy fix is to remove the overlap.

### 10.3 Use one explicit confidence formula

The original guide allowed any explainable formula, which made implementation unnecessarily
open-ended. Use this version-one formula:

```python
PSEUDOCODE _confidence(
    *,
    occurrence_count,
    gaps,
    representative_gap,
    amount_variation,
    policy,
    last_charged_at,
    as_of,
):
    gap_spread = max(gaps) - min(gaps)
    timing_consistency = max(0.0, 1.0 - gap_spread / representative_gap)

    IF policy.maximum_amount_variation == Decimal("0"):
        amount_consistency = 1.0 if amount_variation == 0 else 0.0
    ELSE:
        amount_consistency = max(
            0.0,
            1.0 - float(amount_variation / policy.maximum_amount_variation),
        )

    first_prediction = last_charged_at.date() + timedelta(days=representative_gap)
    overdue_days = max(0, (as_of.date() - first_prediction).days)
    overdue_cycles = overdue_days / representative_gap
    recency = max(0.0, 1.0 - 0.25 * overdue_cycles)

    extra_evidence = min(
        0.25,
        0.05 * (occurrence_count - policy.minimum_occurrences),
    )

    raw = (
        0.45 * timing_consistency
        + 0.35 * amount_consistency
        + 0.20 * recency
        + extra_evidence
    )
    return max(0.0, min(1.0, raw))
```

This is policy, not truth. A future change should be versioned and evaluated against labeled
examples rather than silently tuned.

### 10.4 Build each candidate

Continue the public function after grouping:

```python
PSEUDOCODE:
    streams = []

    FOR (merchant_key, currency), group IN groups.items():
        ordered = sorted(
            group,
            key=lambda item: (item.occurred_at.isoformat(), str(item.transaction_id)),
        )

        IF len(ordered) < active_policy.minimum_occurrences:
            CONTINUE

        gaps = [
            (current.occurred_at.date() - previous.occurred_at.date()).days
            FOR each adjacent previous/current pair in ordered
        ]
        frequency = _detect_frequency(gaps, active_policy)

        IF frequency IS None:
            CONTINUE

        amounts = [item.amount FOR item IN ordered]
        variation = _amount_variation(amounts)

        IF variation > active_policy.maximum_amount_variation:
            CONTINUE

        average_amount = sum(amounts, Decimal("0")) / len(amounts)
        representative_gap = _representative_gap(gaps)
        last = ordered[-1]

        display_names = {
            " ".join(item.merchant_name.split())
            FOR item IN ordered
        }
        display_name = min(
            display_names,
            key=lambda value: (value.casefold(), value),
        )

        streams.append(
            RecurringStreamCandidate(
                stream_key=_stream_key(merchant_key, currency, frequency),
                merchant_name=display_name,
                frequency=frequency,
                average_amount=average_amount,
                last_amount=last.amount,
                currency=currency,
                last_charged_at=last.occurred_at,
                next_expected_date=_next_expected_date(
                    last.occurred_at,
                    representative_gap,
                    as_of.date(),
                ),
                confidence=_confidence(
                    occurrence_count=len(ordered),
                    gaps=gaps,
                    representative_gap=representative_gap,
                    amount_variation=variation,
                    policy=active_policy,
                    last_charged_at=last.occurred_at,
                    as_of=as_of,
                ),
                transaction_ids=tuple(item.transaction_id FOR item IN ordered),
            )
        )

    return RecurringDetectionResult(
        streams=tuple(sorted(streams, key=_stream_sort_key))
    )
```

The learner-owned functions are `_usable`, `_detect_frequency`, `_confidence`, and
`detect_recurring_transactions`.

## 11. Test order

1. three monthly charges form a stream;
2. two charges are insufficient;
3. unstable amount rejects a stream;
4. pending/inflow records are ignored;
5. input order does not affect output.

## 12. Common mistakes

- Grouping only by amount and combining unrelated merchants.
- treating two charges as enough proof.
- using average dates without sorting first.
- including pending activity.
- predicting a past next date.
- using current time inside the function instead of the passed `as_of`.
- leaving transaction IDs in input order.

## 13. Completion check

```bash
uv run pytest -m user_owned app/tests/user_owned/test_money_recurring.py -q
```

You should be able to explain what evidence makes a candidate stronger and why the UI must call it “detected recurring activity,” not a guaranteed subscription.
