# Guide 05 — Money Domain Roadmap

[← Synchronization orchestrator](04-SYNC-ORCHESTRATOR.md) | [Next: Transaction normalization →](06-TRANSACTION-NORMALIZATION.md)

Posted now has two related but deliberately separate domains:

```text
portfolio domain                    money domain
brokerage positions                 bank and card accounts
market events                       everyday transactions
investment impact                   spending and recurring charges
Schwab + OpenBB + SEC               Plaid + Apple FinanceKit (later)
```

The database and UI may show both, but their accounting rules must not be mixed. A credit-card payment is a transfer in the money domain; it is not an investment trade. A brokerage cash position is part of portfolio valuation; it is not automatically available checking cash.

## What you write

Complete these only after the original five learning files:

| Order | File | Lesson | Guide |
|---|---|---|---|
| 6 | `backend/app/money/normalize.py` | Provider boundaries, money signs, identity, stable fingerprints | [Guide 06](06-TRANSACTION-NORMALIZATION.md) |
| 7 | `backend/app/money/reconcile.py` | Incremental ledgers, mutations, deletion, pending replacement | [Guide 07](07-LEDGER-RECONCILIATION.md) |
| 8 | `backend/app/money/spending.py` | Double-count prevention, transfer matching, classification | [Guide 08](08-SPENDING-CLASSIFICATION.md) |
| 9 | `backend/app/money/recurring.py` | Time-series grouping, cadence, confidence, false positives | [Guide 09](09-RECURRING-TRANSACTIONS.md) |

The provider clients, encryption, SQLAlchemy tables, routes, demo data, and React Native screens are agent-owned. Read them to understand the boundaries; do not pause your learning track to rewrite them.

The focused guides also mark generic helpers as **provided**. Those helpers—text cleanup,
stable sorting, canonical tuple projection, hashing wrappers, interpolation, and basic date
arithmetic—are already implemented inside the exercise files. “You write” means you implement
the business flow that uses them, not that you must author every line in the module.

## The end-to-end flow

```text
Plaid / FinanceKit payload
        |
        v
provider mapper                         agent-owned
        |
        v
TransactionObservation
        |
        v
normalize_transactions                 you write
        |
        v
NormalizedTransaction
        |
        v
reconcile_ledger                       you write
        |
        v
database actions -> money_transactions agent-owned persistence
        |
        +--> summarize_weekly_spending  you write
        |
        +--> detect_recurring...        you write
        |
        v
FastAPI JSON -> Expo Money UI           agent-owned
```

Each boundary has one job. The Plaid mapper knows Plaid's unusual amount sign. Normalization knows Posted's canonical rules. Reconciliation knows how a mutable provider feed changes a durable ledger. Spending and recurring analysis read the ledger without changing it.

## Contracts to open before coding

- `backend/app/money/enums.py` — every allowed classification.
- `backend/app/money/models.py` — immutable inputs and outputs.
- `backend/app/tests/user_owned/money_factories.py` — deterministic examples.
- `backend/app/tests/user_owned/test_money_*.py` — executable requirements.

Do not import SQLAlchemy, FastAPI, Plaid, or environment settings into the four files you write. They are pure domain functions and should run with no database or network.

## Important accounting choices

Posted represents transaction amounts as positive `Decimal` values and stores the economic direction separately:

```text
coffee purchase: amount=6.50, direction=OUTFLOW
paycheck:        amount=3250, direction=INFLOW
```

Never use negative amounts inside the canonical model. Never use `float` for money. Convert a provider's sign convention in its adapter.

A transaction is not necessarily spending:

```text
outflow purchase       -> spending
outflow card payment   -> transfer/payment, not new spending
outflow brokerage move -> investment, not consumer spending
inflow paycheck        -> income
inflow refund          -> refund
pending purchase       -> visible activity, not finalized spending
```

This distinction is the heart of the learning track.

## How to work through it

Use the same loop as the portfolio track:

```text
read one pass in the guide
-> run one named test
-> trace the factory input by hand
-> implement only that behavior
-> explain the invariant
-> continue
```

Run all four money exercises:

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_money_*.py -q
```

While another user-owned file is temporarily incomplete, run only the file you are implementing so pytest does not import the unfinished module.

## Definition of complete

You are done when you can explain:

1. Why a provider mapper and a canonical normalizer are different layers.
2. Why an incremental feed must not delete every transaction absent from one page.
3. How one credit-card purchase and its later payment would otherwise be counted twice.
4. Why recurring-charge detection produces evidence and confidence, not certainty.
5. Why Apple Wallet is not a universal transaction or subscription API.
