"""
Tests run against a fake in-memory connector, not live Odoo/BC/custom-ERP
instances — so CI can run on every push without credentials. Real
connectors are exercised manually / in an integration environment.
"""

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from erp_connectors.base import ERPConnector
from erp_connectors.models import Customer, Invoice, InvoiceLine, SyncResult


class FakeConnector(ERPConnector):
    """Minimal in-memory implementation used to prove the contract works
    end-to-end without hitting any real ERP."""

    system_name = "fake"

    def __init__(self):
        self._db: dict[str, Customer] = {}
        self._next_id = 1
        self.authenticated = False

    def authenticate(self) -> None:
        self.authenticated = True

    def get_customer(self, external_id: str) -> Customer | None:
        return self._db.get(external_id)

    def upsert_customer(self, customer: Customer) -> SyncResult:
        if customer.external_id and customer.external_id in self._db:
            self._db[customer.external_id] = customer
            return SyncResult(True, self.system_name, "upsert_customer:update", customer.external_id)
        new_id = str(self._next_id)
        self._next_id += 1
        customer.external_id = new_id
        self._db[new_id] = customer
        return SyncResult(True, self.system_name, "upsert_customer:create", new_id)

    def create_invoice(self, invoice: Invoice) -> SyncResult:
        return SyncResult(True, self.system_name, "create_invoice", "INV-1")

    def get_invoice_status(self, external_id: str) -> str | None:
        return "posted" if external_id == "INV-1" else None


def test_authenticate_is_idempotent():
    conn = FakeConnector()
    conn.authenticate()
    conn.authenticate()
    assert conn.authenticated is True


def test_upsert_customer_creates_then_updates():
    conn = FakeConnector()
    customer = Customer(external_id=None, name="Plantech Kenya Ltd", email="ap@plantech.co.ke")

    created = conn.upsert_customer(customer)
    assert created.success
    assert created.operation.endswith("create")

    customer.external_id = created.external_id
    customer.email = "finance@plantech.co.ke"
    updated = conn.upsert_customer(customer)
    assert updated.success
    assert updated.operation.endswith("update")
    assert updated.external_id == created.external_id

    fetched = conn.get_customer(created.external_id)
    assert fetched.email == "finance@plantech.co.ke"


def test_invoice_total_computes_with_tax():
    invoice = Invoice(
        external_id=None, customer_external_id="1", number=None,
        currency="KES", issue_date=datetime(2026, 8, 1, tzinfo=timezone.utc), due_date=None,
        lines=[InvoiceLine(description="Rooted cuttings", quantity=Decimal(100),
                            unit_price=Decimal(50), tax_rate=Decimal(16))],
    )
    # 100 * 50 = 5000, +16% tax = 5800
    assert invoice.total == Decimal("5800.00") or invoice.total == 5800


def test_health_check_reports_success():
    conn = FakeConnector()
    result = conn.health_check()
    assert result.success
    assert result.system == "fake"
