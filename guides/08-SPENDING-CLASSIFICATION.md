# Guide 08 — Spending Classification

[← Ledger reconciliation](07-LEDGER-RECONCILIATION.md) | [Next: Recurring transactions →](09-RECURRING-TRANSACTIONS.md)

**You write:** `backend/app/money/spending.py`

**Immediate goal:** compute truthful weekly spending without counting pending charges, transfers, card payments, or investment movements as consumer spending.

## 1. Start here

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_money_spending.py -q
```

Open the function, `SpendingPolicy`, `WeeklySpendingSummary`, `SpendingTreatment`, and the tests together.

## 2. Why this logic is mission critical

Suppose a user buys $100 of groceries on a credit card, then pays $100 from checking:

```text
credit-card purchase -> $100 outflow
checking payment     -> $100 outflow
card payment receipt -> $100 inflow
```

A naive sum of outflows reports $200 of spending. The true spending is $100. The other two records move money between the user's own accounts.

Your function must classify first and aggregate second.

## 3. Output contract

`WeeklySpendingSummary` contains:

- `total_spending`: posted consumer outflows in the period.
- `total_income`: posted non-transfer inflows in the period.
- `total_excluded`: outflow value intentionally excluded from spending.
- `by_category`: consumer spending grouped by primary category.
- `decisions`: one auditable classification per input transaction.

Every input should receive one `SpendingDecision`, even when excluded. This makes the result explainable.

## 4. Use an inclusive reporting window

For this exercise, a transaction is in period when:

```text
period_start <= occurred_at <= period_end
```

Validate that both boundaries are timezone-aware and `period_start <= period_end`. A production API may prefer a half-open interval, but changing the convention silently causes boundary-day mistakes.

SQLite can return naive timestamps even for timezone columns. This pure exercise receives domain objects and should require valid aware times; database adapters are responsible for restoring UTC.

## 5. Classification order

Order matters. Apply the first matching rule:

| Priority | Condition | Treatment |
|---:|---|---|
| 1 | pending status | `PENDING` |
| 2 | outside reporting period | `EXCLUDED` |
| 3 | part of a matched internal transfer pair | `INTERNAL_TRANSFER` |
| 4 | category in credit-card-payment set | `CREDIT_CARD_PAYMENT` |
| 5 | category in investment set | `INVESTMENT` |
| 6 | category in refund set | `REFUND` |
| 7 | direction is inflow | `INCOME` |
| 8 | direction is outflow | `SPENDING` |

Normalize category comparison with stripped uppercase values. Do not alter the stored transaction.

`PENDING` comes first because a pending card payment is still provisional. Internal transfer matching comes before generic income/outflow handling so neither side reaches totals.

## 6. Match internal transfers conservatively

Create candidate pairs only when all are true:

1. Both transactions are posted and in the period.
2. They use different account IDs.
3. They use the same currency.
4. They have exactly equal `Decimal` amounts.
5. One is inflow and one is outflow.
6. Their timestamps are within `policy.transfer_window`.
7. At least one has a category in `policy.transfer_categories`.

For the starter test, checking out is `TRANSFER_OUT`, credit in is `TRANSFER_IN`, amounts are $500, and timestamps are one day apart.

One transaction may belong to at most one pair. Sort candidates by timestamp/UUID and choose the closest unmatched opposite movement. Conservative unmatched records are safer than overmatching two unrelated $100 transactions.

Do not use merchant equality as a requirement; bank descriptions often differ between the sending and receiving accounts.

## 7. Aggregate after decisions exist

Once every transaction has a treatment:

```text
SPENDING -> add to total_spending and its category
INCOME   -> add to total_income
excluded outflow treatments -> add to total_excluded
all other treatments -> no spending/category contribution
```

Use `Decimal("0")` as every sum's start value.

For uncategorized spending, group under `UNCATEGORIZED`. Sort `by_category` by descending amount, then category name. Sort decisions by a stable key such as `(occurred_at, str(transaction_id))`.

The final equality test depends on deterministic tuple ordering.

## 8. Suggested implementation passes

### Pass 1

Classify one posted outflow as spending and aggregate its category. Run `test_posted_purchase_counts_as_spending`.

### Pass 2

Add pending and income handling. Run the next two tests.

### Pass 3

Write `_match_internal_transfers` and mark both transaction IDs before ordinary classification. Run `test_matching_account_movements_are_internal_transfer`.

### Pass 4

Add policy category sets, totals for exclusions, and stable sorting. Run the remaining tests.

## 9. Exact implementation walkthrough

The file already provides these mechanical helpers:

```python
_is_timezone_aware
_in_period
_normalized_category
_transaction_sort_key
_validate_period
```

Your learning task is the conservative transfer matcher and the classification priority table.

Add these imports:

```python
from collections import defaultdict
from decimal import Decimal

from app.money.enums import SpendingTreatment, TransactionDirection, TransactionStatus
from app.money.models import CategorySpend, SpendingDecision
```

### 9.1 Validate the reporting contract

Call the provided helper once at the start of the public function:

```python
_validate_period(
    transactions,
    period_start=period_start,
    period_end=period_end,
)
```

It rejects naive boundaries, a reversed period, and naive transaction occurrence times.

### 9.2 Match internal transfers

Return a set of transaction UUIDs. Both sides of every selected pair enter the set:

```python
PSEUDOCODE _match_internal_transfers(transactions, period_start, period_end, policy):
    eligible = sorted(
        (
            transaction
            FOR transaction IN transactions
            IF transaction.status IS TransactionStatus.POSTED
            AND _in_period(transaction, period_start=period_start, period_end=period_end)
        ),
        key=_transaction_sort_key,
    )

    matched_ids = empty set

    FOR transaction IN eligible:
        IF transaction.transaction_id IN matched_ids:
            CONTINUE

        category = _normalized_category(transaction)
        candidates = []

        FOR other IN eligible:
            IF other.transaction_id == transaction.transaction_id:
                CONTINUE
            IF other.transaction_id IN matched_ids:
                CONTINUE
            IF other.account_id == transaction.account_id:
                CONTINUE
            IF other.currency.upper() != transaction.currency.upper():
                CONTINUE
            IF other.amount != transaction.amount:
                CONTINUE
            IF other.direction IS transaction.direction:
                CONTINUE
            IF abs(other.occurred_at - transaction.occurred_at) > policy.transfer_window:
                CONTINUE

            other_category = _normalized_category(other)
            IF category NOT IN policy.transfer_categories
               AND other_category NOT IN policy.transfer_categories:
                CONTINUE

            candidates.append(other)

        IF candidates is empty:
            CONTINUE

        match = min(
            candidates,
            key=lambda other: (
                abs((other.occurred_at - transaction.occurred_at).total_seconds()),
                _transaction_sort_key(other),
            ),
        )
        matched_ids.add(transaction.transaction_id)
        matched_ids.add(match.transaction_id)

    return matched_ids
```

Sorting and the closest-time tie-breaker make the greedy selection deterministic.

### 9.3 Apply the classification table

```python
PSEUDOCODE _treatment(
    transaction,
    transfer_ids,
    period_start,
    period_end,
    policy,
):
    IF transaction.status IS TransactionStatus.PENDING:
        return (SpendingTreatment.PENDING, "Transaction is still pending")

    IF NOT _in_period(transaction, period_start=period_start, period_end=period_end):
        return (SpendingTreatment.EXCLUDED, "Transaction is outside the reporting period")

    IF transaction.transaction_id IN transfer_ids:
        return (SpendingTreatment.INTERNAL_TRANSFER, "Matched an equal opposite account movement")

    category = _normalized_category(transaction)

    IF category IN policy.credit_card_payment_categories:
        return (SpendingTreatment.CREDIT_CARD_PAYMENT, "Credit-card payment is not new spending")

    IF category IN policy.investment_categories:
        return (SpendingTreatment.INVESTMENT, "Investment movement is excluded from spending")

    IF category IN policy.refund_categories:
        return (SpendingTreatment.REFUND, "Refund is reported separately from income")

    IF transaction.direction IS TransactionDirection.INFLOW:
        return (SpendingTreatment.INCOME, "Posted non-transfer inflow counted as income")

    return (SpendingTreatment.SPENDING, "Posted outflow counted as consumer spending")
```

### 9.4 Classify first, aggregate second

```python
PSEUDOCODE summarize_weekly_spending(...):
    active_policy = policy OR SpendingPolicy()
    ordered = tuple(sorted(transactions, key=_transaction_sort_key))
    _validate_period(ordered, period_start, period_end)

    transfer_ids = _match_internal_transfers(
        ordered,
        period_start,
        period_end,
        active_policy,
    )

    ZERO = Decimal("0")
    total_spending = ZERO
    total_income = ZERO
    total_excluded = ZERO
    category_totals = defaultdict(lambda: ZERO)
    decisions = []

    FOR transaction IN ordered:
        treatment, reason = _treatment(
            transaction,
            transfer_ids,
            period_start,
            period_end,
            active_policy,
        )
        decisions.append(SpendingDecision(transaction.transaction_id, treatment, reason))

        IF treatment IS SpendingTreatment.SPENDING:
            total_spending += transaction.amount
            category_totals[_normalized_category(transaction)] += transaction.amount
        ELSE IF treatment IS SpendingTreatment.INCOME:
            total_income += transaction.amount
        ELSE IF transaction.direction IS TransactionDirection.OUTFLOW:
            total_excluded += transaction.amount

    categories = (
        CategorySpend(category=name, amount=amount)
        FOR name, amount IN category_totals.items()
    )

    return WeeklySpendingSummary(
        period_start=period_start,
        period_end=period_end,
        total_spending=total_spending,
        total_income=total_income,
        total_excluded=total_excluded,
        by_category=tuple(sorted(categories, key=lambda item: (-item.amount, item.category))),
        decisions=tuple(decisions),
    )
```

The learner-owned functions are `_match_internal_transfers`, `_treatment`, and
`summarize_weekly_spending`. Period validation is already provided. Reasons are fixed close to
the rule that produced them.

## 10. Common mistakes

- Summing outflows before deciding what each record means.
- counting a card purchase and its checking payment.
- treating every inflow as income, including transfer receipts and refunds.
- using a fuzzy amount tolerance for transfers and matching unrelated activity.
- matching one transaction to multiple counterparts.
- including pending amounts in finalized weekly spending.
- returning categories in dictionary insertion order.

## 11. Completion check

```bash
uv run pytest -m user_owned app/tests/user_owned/test_money_spending.py -q
```

You should be able to trace a credit-card purchase and payment across all three ledger records and show why only the purchase reaches `total_spending`.
