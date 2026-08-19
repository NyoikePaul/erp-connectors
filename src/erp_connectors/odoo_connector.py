"""
Odoo connector — talks to Odoo's JSON-RPC endpoint (/jsonrpc).

Odoo has no separate "API layer": external calls go through the same ORM
methods (`search_read`, `create`, `write`) that Odoo's own UI uses. That
makes this connector a thin, honest wrapper rather than a translation of
some separate REST surface.

Docs: https://www.odoo.com/documentation/latest/developer/reference/external_api.html
"""

from __future__ import annotations

import xmlrpc.client

from .base import ERPConnector
from .models import Customer, Invoice, SyncResult


class OdooConnector(ERPConnector):
    system_name = "odoo"

    def __init__(self, url: str, db: str, username: str, api_key: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.api_key = api_key
        self._uid: int | None = None
        self._models = None

    def authenticate(self) -> None:
        if self._uid is not None:
            return
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._uid = common.authenticate(self.db, self.username, self.api_key, {})
        if not self._uid:
            raise ConnectionError("Odoo authentication failed — check db/username/api key.")
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def _execute(self, model: str, method: str, *args):
        self.authenticate()
        return self._models.execute_kw(self.db, self._uid, self.api_key, model, method, list(args))

    def get_customer(self, external_id: str) -> Customer | None:
        records = self._execute(
            "res.partner",
            "search_read",
            [[["id", "=", int(external_id)]]],
            {"fields": ["id", "name", "email", "phone", "vat", "is_company"]},
        )
        if not records:
            return None
        r = records[0]
        return Customer(
            external_id=str(r["id"]),
            name=r["name"],
            email=r.get("email") or None,
            phone=r.get("phone") or None,
            tax_id=r.get("vat") or None,
            is_company=r.get("is_company", False),
        )

    def upsert_customer(self, customer: Customer) -> SyncResult:
        payload = {
            "name": customer.name,
            "email": customer.email or False,
            "phone": customer.phone or False,
            "vat": customer.tax_id or False,
            "is_company": customer.is_company,
        }
        if customer.external_id:
            self._execute("res.partner", "write", [int(customer.external_id)], payload)
            new_id = customer.external_id
            op = "update"
        else:
            new_id = self._execute("res.partner", "create", payload)
            op = "create"
        return SyncResult(
            success=True, system=self.system_name, operation=f"upsert_customer:{op}", external_id=str(new_id)
        )

    def create_invoice(self, invoice: Invoice) -> SyncResult:
        line_commands = [
            (
                0,
                0,
                {
                    "name": line.description,
                    "quantity": float(line.quantity),
                    "price_unit": float(line.unit_price),
                },
            )
            for line in invoice.lines
        ]
        new_id = self._execute(
            "account.move",
            "create",
            {
                "move_type": "out_invoice",
                "partner_id": int(invoice.customer_external_id),
                "invoice_line_ids": line_commands,
            },
        )
        return SyncResult(
            success=True, system=self.system_name, operation="create_invoice", external_id=str(new_id)
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        records = self._execute(
            "account.move", "search_read", [[["id", "=", int(external_id)]]], {"fields": ["state"]}
        )
        return records[0]["state"] if records else None
