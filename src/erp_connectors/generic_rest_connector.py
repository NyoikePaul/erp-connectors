"""
Generic REST connector for custom ERPs — bearer token, field-mappable, with retry.
"""

from __future__ import annotations

import requests

from .base import ERPConnector
from .exceptions import AuthenticationError, TransientError
from .models import Customer, Invoice, SyncResult
from .retry import with_retry


class GenericRESTConnector(ERPConnector):
    system_name = "generic_rest"

    def __init__(
        self,
        base_url: str,
        token: str,
        customers_path: str = "/api/customers",
        invoices_path: str = "/api/invoices",
        field_map: dict | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.customers_path = customers_path
        self.invoices_path = invoices_path
        self.field_map = field_map or {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "tax_id": "taxId",
            "currency": "currency",
        }

    def authenticate(self) -> None:
        if not self.token:
            raise AuthenticationError("No bearer token configured for GenericRESTConnector.")

    def _headers(self) -> dict:
        self.authenticate()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        def _call():
            try:
                resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                raise TransientError(str(exc)) from exc
            if resp.status_code in (429, 500, 502, 503, 504):
                raise TransientError(f"REST {resp.status_code}: {resp.text[:200]}")
            return resp

        return with_retry(_call)

    def get_customer(self, external_id: str) -> Customer | None:
        resp = self._request("GET", f"{self.base_url}{self.customers_path}/{external_id}")
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
            resp = self._request(
                "PUT",
                f"{self.base_url}{self.customers_path}/{customer.external_id}",
                json=payload,
            )
            op, new_id = "update", customer.external_id
        else:
            resp = self._request("POST", f"{self.base_url}{self.customers_path}", json=payload)
            op = "create"
            new_id = str(resp.json().get("id")) if resp.ok else None
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
            "currency": invoice.currency,
            "issueDate": invoice.issue_date.isoformat(),
            "lines": [
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unitPrice": str(line.unit_price),
                }
                for line in invoice.lines
            ],
        }
        resp = self._request("POST", f"{self.base_url}{self.invoices_path}", json=payload)
        new_id = str(resp.json().get("id")) if resp.ok else None
        return SyncResult(
            success=resp.ok,
            system=self.system_name,
            operation="create_invoice",
            external_id=new_id,
            message="" if resp.ok else resp.text,
        )

    def get_invoice_status(self, external_id: str) -> str | None:
        resp = self._request("GET", f"{self.base_url}{self.invoices_path}/{external_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("status")
