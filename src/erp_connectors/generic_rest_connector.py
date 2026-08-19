"""
Generic REST connector — for custom-built ERPs (e.g. a bespoke Next.js /
NestJS backend) that don't follow a documented standard like OData or
Odoo's RPC API.

This is deliberately the most configurable connector: every field/endpoint
name is passed in rather than hardcoded, because a hand-rolled ERP's shape
is unknown until you've inspected its API. Start here whenever you're
integrating with an undocumented system — get one resource round-tripping,
then tighten the field_map as you learn the real schema.

Auth defaults to bearer-token (JWT), the most common pattern for a custom
Next.js/NestJS backend using something like NextAuth or a hand-rolled
JWT issuer. Swap `_headers()` if the target uses API keys or cookies instead.
"""

from __future__ import annotations

import requests

from .base import ERPConnector
from .models import Customer, Invoice, SyncResult


class GenericRESTConnector(ERPConnector):
    system_name = "generic_rest"

    def __init__(self, base_url: str, token: str,
                 customers_path: str = "/api/customers",
                 invoices_path: str = "/api/invoices",
                 field_map: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.customers_path = customers_path
        self.invoices_path = invoices_path
        # Maps canonical field name -> this system's actual JSON key.
        # Override per deployment once you've inspected the real API.
        self.field_map = field_map or {
            "name": "name", "email": "email", "phone": "phone",
            "tax_id": "taxId", "currency": "currency",
        }

    def authenticate(self) -> None:
        # Bearer tokens are typically long-lived or refreshed externally
        # for a custom backend — override with a real login call if the
        # target issues short-lived tokens instead.
        if not self.token:
            raise ConnectionError("No bearer token configured for GenericRESTConnector.")

    def _headers(self) -> dict:
        self.authenticate()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def get_customer(self, external_id: str) -> Customer | None:
        resp = requests.get(f"{self.base_url}{self.customers_path}/{external_id}", headers=self._headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        r = resp.json()
        fm = self.field_map
        return Customer(
            external_id=str(r.get("id", external_id)),
            name=r.get(fm["name"], ""),
            email=r.get(fm["email"]),
            phone=r.get(fm["phone"]),
            tax_id=r.get(fm["tax_id"]),
            currency=r.get(fm["currency"], "KES"),
        )

    def upsert_customer(self, customer: Customer) -> SyncResult:
        fm = self.field_map
        payload = {
            fm["name"]: customer.name,
            fm["email"]: customer.email,
            fm["phone"]: customer.phone,
            fm["tax_id"]: customer.tax_id,
            fm["currency"]: customer.currency,
        }
        if customer.external_id:
            resp = requests.put(
                f"{self.base_url}{self.customers_path}/{customer.external_id}",
                headers=self._headers(), json=payload,
            )
            op, new_id = "update", customer.external_id
        else:
            resp = requests.post(f"{self.base_url}{self.customers_path}", headers=self._headers(), json=payload)
            op = "create"
            new_id = str(resp.json().get("id")) if resp.ok else None
        return SyncResult(
            success=resp.ok, system=self.system_name, operation=f"upsert_customer:{op}",
            external_id=new_id, message="" if resp.ok else resp.text,
        )

    def create_invoice(self, invoice: Invoice) -> SyncResult:
        payload = {
            "customerId": invoice.customer_external_id,
            "currency": invoice.currency,
            "issueDate": invoice.issue_date.isoformat(),
            "lines": [
                {"description": l.description, "quantity": str(l.quantity), "unitPrice": str(l.unit_price)}
                for l in invoice.lines
            ],
        }
        resp = requests.post(f"{self.base_url}{self.invoices_path}", headers=self._headers(), json=payload)
        new_id = str(resp.json().get("id")) if resp.ok else None
        return SyncResult(
            success=resp.ok, system=self.system_name, operation="create_invoice",
            external_id=new_id, message="" if resp.ok else resp.text,
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        resp = requests.get(f"{self.base_url}{self.invoices_path}/{external_id}", headers=self._headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("status")
