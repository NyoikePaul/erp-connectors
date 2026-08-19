"""
Odoo connector — XML-RPC External API with retry + structured errors.
Docs: https://www.odoo.com/documentation/latest/developer/reference/external_api.html
"""

from __future__ import annotations

import xmlrpc.client

from .base import ERPConnector
from .exceptions import AuthenticationError, TransientError
from .models import Customer, Invoice, SyncResult
from .retry import with_retry
from .status import normalize_status


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

        def _auth():
            try:
                common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
                uid = common.authenticate(self.db, self.username, self.api_key, {})
            except (ConnectionError, TimeoutError, OSError, xmlrpc.client.ProtocolError) as exc:
                raise TransientError(str(exc)) from exc
            if not uid:
                raise AuthenticationError("Odoo authentication failed — check db/username/api key.")
            return uid

        self._uid = with_retry(_auth)
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def _execute(self, model: str, method: str, *args):
        self.authenticate()

        def _call():
            try:
                return self._models.execute_kw(
                    self.db, self._uid, self.api_key, model, method, list(args)
                )
            except (ConnectionError, TimeoutError, OSError, xmlrpc.client.ProtocolError) as exc:
                raise TransientError(str(exc)) from exc

        return with_retry(_call)

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
            success=True,
            system=self.system_name,
            operation=f"upsert_customer:{op}",
            external_id=str(new_id),
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
            success=True,
            system=self.system_name,
            operation="create_invoice",
            external_id=str(new_id),
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        records = self._execute(
            "account.move",
            "search_read",
            [[["id", "=", int(external_id)]]],
            {"fields": ["state"]},
        )
        if not records:
            return None
        return normalize_status(self.system_name, records[0]["state"])
