"""
Microsoft Dynamics 365 Business Central — OData v4 + MSAL, with retry + structured errors.
"""

from __future__ import annotations

import msal
import requests

from .base import ERPConnector
from .exceptions import AuthenticationError, TransientError
from .models import Customer, Invoice, SyncResult
from .retry import with_retry
from .status import normalize_status


class DynamicsBCConnector(ERPConnector):
    system_name = "dynamics_bc"

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        environment: str,
        company_id: str,
    ):
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
        def _auth():
            result = self._app.acquire_token_silent(
                ["https://api.businesscentral.dynamics.com/.default"], account=None
            )
            if not result:
                result = self._app.acquire_token_for_client(
                    scopes=["https://api.businesscentral.dynamics.com/.default"]
                )
            if "access_token" not in result:
                raise AuthenticationError(f"BC auth failed: {result.get('error_description')}")
            return result["access_token"]

        self._token = with_retry(_auth)

    def _headers(self) -> dict:
        self.authenticate()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        def _call():
            headers = {**self._headers(), **kwargs.pop("headers", {})}
            try:
                resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                raise TransientError(str(exc)) from exc
            if resp.status_code in (429, 500, 502, 503, 504):
                raise TransientError(f"BC {resp.status_code}: {resp.text[:200]}")
            return resp

        return with_retry(_call)

    def get_customer(self, external_id: str) -> Customer | None:
        resp = self._request("GET", f"{self.base_url}/customers({external_id})")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        r = resp.json()
        return Customer(
            external_id=r["id"],
            name=r["displayName"],
            email=r.get("email") or None,
            phone=r.get("phoneNumber") or None,
            currency=r.get("currencyCode") or "KES",
        )

    def upsert_customer(self, customer: Customer) -> SyncResult:
        payload = {
            "displayName": customer.name,
            "email": customer.email,
            "phoneNumber": customer.phone,
            "currencyCode": customer.currency,
        }
        if customer.external_id:
            resp = self._request(
                "PATCH",
                f"{self.base_url}/customers({customer.external_id})",
                json=payload,
                headers={**self._headers(), "If-Match": "*"},
            )
            # _request already sets headers; merge If-Match via kwargs carefully
            op, new_id = "update", customer.external_id
        else:
            resp = self._request("POST", f"{self.base_url}/customers", json=payload)
            op = "create"
            new_id = resp.json().get("id") if resp.ok else None
        return SyncResult(
            success=resp.ok,
            system=self.system_name,
            operation=f"upsert_customer:{op}",
            external_id=new_id,
            message="" if resp.ok else resp.text,
        )

    def create_invoice(self, invoice: Invoice) -> SyncResult:
        payload = {
            "customerId": invoice.customer_external_id,
            "invoiceDate": invoice.issue_date.date().isoformat(),
            "currencyCode": invoice.currency,
        }
        resp = self._request("POST", f"{self.base_url}/salesInvoices", json=payload)
        new_id = resp.json().get("id") if resp.ok else None
        if resp.ok and new_id:
            for line in invoice.lines:
                self._request(
                    "POST",
                    f"{self.base_url}/salesInvoices({new_id})/salesInvoiceLines",
                    json={
                        "lineType": "Item",
                        "description": line.description,
                        "quantity": float(line.quantity),
                        "unitPrice": float(line.unit_price),
                    },
                )
        return SyncResult(
            success=resp.ok,
            system=self.system_name,
            operation="create_invoice",
            external_id=new_id,
            message="" if resp.ok else resp.text,
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        resp = self._request("GET", f"{self.base_url}/salesInvoices({external_id})")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return normalize_status(self.system_name, resp.json().get("status"))
