"""
Microsoft Dynamics 365 Business Central connector — OData v4 over the
standard BC API, authenticated via Azure AD (MSAL client-credentials flow).

This mirrors the `d365_client.py` pattern already in production for the
Plantech ERP bridge — pulled out here as a reusable, ERP-agnostic
implementation of the same ERPConnector contract as the Odoo connector.

Docs: https://learn.microsoft.com/dynamics365/business-central/dev-itpro/api-reference/v2.0/
"""

from __future__ import annotations

import msal
import requests

from .base import ERPConnector
from .models import Customer, Invoice, SyncResult


class DynamicsBCConnector(ERPConnector):
    system_name = "dynamics_bc"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 environment: str, company_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment
        self.company_id = company_id
        self.base_url = (
            f"https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/"
            f"{environment}/api/v2.0/companies({company_id})"
        )
        self._token: str | None = None
        self._app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
        )

    def authenticate(self) -> None:
        result = self._app.acquire_token_silent(
            ["https://api.businesscentral.dynamics.com/.default"], account=None
        )
        if not result:
            result = self._app.acquire_token_for_client(
                scopes=["https://api.businesscentral.dynamics.com/.default"]
            )
        if "access_token" not in result:
            raise ConnectionError(f"BC auth failed: {result.get('error_description')}")
        self._token = result["access_token"]

    def _headers(self) -> dict:
        self.authenticate()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def get_customer(self, external_id: str) -> Customer | None:
        resp = requests.get(f"{self.base_url}/customers({external_id})", headers=self._headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        r = resp.json()
        return Customer(
            external_id=r["id"], name=r["displayName"], email=r.get("email") or None,
            phone=r.get("phoneNumber") or None, currency=r.get("currencyCode") or "KES",
        )

    def upsert_customer(self, customer: Customer) -> SyncResult:
        payload = {
            "displayName": customer.name,
            "email": customer.email,
            "phoneNumber": customer.phone,
            "currencyCode": customer.currency,
        }
        if customer.external_id:
            resp = requests.patch(
                f"{self.base_url}/customers({customer.external_id})",
                headers={**self._headers(), "If-Match": "*"}, json=payload,
            )
            op, new_id = "update", customer.external_id
        else:
            resp = requests.post(f"{self.base_url}/customers", headers=self._headers(), json=payload)
            op = "create"
            new_id = resp.json().get("id") if resp.ok else None
        return SyncResult(
            success=resp.ok, system=self.system_name, operation=f"upsert_customer:{op}",
            external_id=new_id, message="" if resp.ok else resp.text,
        )

    def create_invoice(self, invoice: Invoice) -> SyncResult:
        payload = {
            "customerId": invoice.customer_external_id,
            "invoiceDate": invoice.issue_date.date().isoformat(),
            "currencyCode": invoice.currency,
        }
        resp = requests.post(f"{self.base_url}/salesInvoices", headers=self._headers(), json=payload)
        new_id = resp.json().get("id") if resp.ok else None
        if resp.ok and new_id:
            for line in invoice.lines:
                requests.post(
                    f"{self.base_url}/salesInvoices({new_id})/salesInvoiceLines",
                    headers=self._headers(),
                    json={
                        "lineType": "Comment",
                        "description": line.description,
                        "quantity": float(line.quantity),
                        "unitPrice": float(line.unit_price),
                    },
                )
        return SyncResult(
            success=resp.ok, system=self.system_name, operation="create_invoice",
            external_id=new_id, message="" if resp.ok else resp.text,
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        resp = requests.get(f"{self.base_url}/salesInvoices({external_id})", headers=self._headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("status")
