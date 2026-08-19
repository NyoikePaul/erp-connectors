# erp-connectors

A single integration layer that unifies **Odoo**, **Microsoft Dynamics 365
Business Central**, and **custom-built ERPs** (e.g. a hand-rolled
Next.js/NestJS backend) behind one canonical interface.

Most ERP integration work gets rewritten from scratch for every new
platform. This toolkit inverts that: write your sync/automation logic
once against a shared `Customer` / `Invoice` / `Product` model, and swap
which ERP it talks to by changing one line — not the integration logic.

```python
from erp_connectors import OdooConnector, DynamicsBCConnector, Customer

odoo = OdooConnector(url=..., db=..., username=..., api_key=...)
bc = DynamicsBCConnector(tenant_id=..., client_id=..., client_secret=..., environment=..., company_id=...)

customer = odoo.get_customer("42")          # pull from Odoo
bc.upsert_customer(Customer(                # push into Business Central
    external_id=None, name=customer.name, email=customer.email,
))
```

## Why this exists

Built while working across Odoo, Microsoft Dynamics 365 Business Central,
and a custom Next.js ERP in parallel — the same business objects
(customers, invoices) kept needing to move between systems that don't
speak the same language. This is the reusable middle layer instead of a
one-off script per project.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design
rationale and how to add a fourth connector.

## Supported systems

| Connector | Protocol | Auth |
|---|---|---|
| `OdooConnector` | XML-RPC (Odoo's External API) | DB + API key |
| `DynamicsBCConnector` | OData v4 | Azure AD (MSAL client-credentials) |
| `GenericRESTConnector` | REST (configurable) | Bearer token, field-mappable |

`GenericRESTConnector` is the one to reach for on day one of integrating
an undocumented, custom-built ERP — its field map is designed to be
adjusted as you learn the target system's real schema.

## Install

```bash
git clone https://github.com/NyoikePaul/erp-connectors.git
cd erp-connectors
pip install -e ".[dev]"
```

## Run the tests

The test suite runs against an in-memory fake connector — no live ERP
credentials are needed to develop or run CI:

```bash
pytest -v
```

## Try the cross-platform sync example

```bash
export ODOO_URL=... ODOO_DB=... ODOO_USERNAME=... ODOO_API_KEY=... ODOO_CUSTOMER_ID=...
export BC_TENANT_ID=... BC_CLIENT_ID=... BC_CLIENT_SECRET=... BC_COMPANY_ID=...
export CUSTOM_ERP_URL=... CUSTOM_ERP_TOKEN=...
python examples/sync_customer_across_systems.py
```

This pulls one customer from Odoo and pushes the same record into
Business Central and a custom REST-based ERP — the scenario the whole
project is built around.

## Roadmap

- [ ] Webhook/event-driven sync (Odoo automated actions, BC Business Events)
- [ ] Two-way sync with conflict resolution
- [ ] Kenya-specific extensions: KRA eTIMS invoice submission, M-Pesa
      Daraja payment reconciliation, as connector mixins
- [ ] `InvoiceConnector` parity for `Product`/inventory sync

## License

MIT — see [LICENSE](LICENSE).
