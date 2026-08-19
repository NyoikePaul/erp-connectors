# Architecture

## The problem this solves

Every ERP integration project starts the same way: write a script that
talks to System A, then a different script for System B, each hardcoding
that system's field names, auth flow, and quirks. Six months later nothing
is reusable and every new integration starts from zero.

This toolkit inverts that: application code is written once, against a
**canonical model** (`Customer`, `Invoice`, `Product`), and each ERP gets a
thin **connector** that translates between the canonical model and its own
native API.

```
            ┌───────────────────────┐
            │   Canonical models    │   Customer / Invoice / Product
            │   (models.py)         │   — the shared vocabulary
            └───────────▲───────────┘
                         │ implements
            ┌────────────┴────────────┐
            │      ERPConnector       │   authenticate() / get_customer() /
            │      (base.py)          │   upsert_customer() / create_invoice()
            └─┬───────────┬──────────┬┘
              │            │          │
   ┌──────────▼──┐ ┌───────▼──────┐ ┌─▼────────────────┐
   │OdooConnector│ │DynamicsBC    │ │GenericRESTConnector│
   │(JSON/XML-RPC│ │Connector     │ │(custom Next.js/    │
   │ + ORM calls)│ │(OData v4 +   │ │ NestJS ERPs)        │
   │             │ │ MSAL/OAuth2) │ │                     │
   └─────────────┘ └──────────────┘ └─────────────────────┘
```

## Why a canonical model, not a shared schema per vendor

Odoo's `res.partner`, Business Central's `customerCard`, and a bespoke
Next.js API's `/api/customers` shape are all "a customer," but none of
them agree on field names, required fields, or how currency is
represented. `Customer` in `models.py` is deliberately the *smallest*
shared shape all three can support — vendor-specific fields live in
`extra: dict` rather than forcing every connector to grow fields the
others don't have.

## Why each connector owns its own auth

Odoo uses a DB name + API key over XML-RPC. Business Central uses Azure AD
client-credentials (OAuth2) via MSAL. A custom backend most often uses a
bearer JWT. There's no honest way to unify these behind one auth
interface, so `authenticate()` is the one method every connector
implements completely differently — and callers never need to know how.

## Idempotency

`upsert_customer` is deliberately idempotent by contract: passing the
same `Customer` twice must not create a duplicate. Callers should treat
`external_id` as the source of truth for "does this record already
exist," and every connector is expected to honor that — this matters most
when a scheduled sync job retries after a network failure.

## Adding a fourth connector

1. Subclass `ERPConnector` in a new file under `src/erp_connectors/`.
2. Implement `authenticate`, `get_customer`, `upsert_customer`,
   `create_invoice`, `get_invoice_status`.
3. Export it from `__init__.py`.
4. Add a fake/mock-backed test following the pattern in
   `tests/test_base_contract.py` — no live credentials should ever be
   required for the test suite to pass.

## Known gaps (intentionally left for the next iteration)

- No webhook/event listener layer yet (Odoo automated actions, BC
  Business Events) — everything here is pull/push, not event-driven.
- No conflict-resolution strategy for two-way sync yet (what happens if
  the same customer changed in both systems since the last sync).
- `Invoice` line item tax handling is simplified — real deployments will
  need per-line tax codes, not a flat `tax_rate`.
