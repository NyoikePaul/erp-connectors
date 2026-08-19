"""
Canonical data models.

Every connector speaks a different native "dialect" (Odoo's res.partner,
Business Central's customerCard, a custom Next.js API's own JSON shape).
These dataclasses are the shared vocabulary that sits between them — the
whole point of this toolkit is that application code is written against
*these* models, never against a vendor's native schema.

Add a field here only when at least two target systems can support it.
System-specific extras belong in `extra: dict`, not as new top-level fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SyncDirection(str, Enum):
    PULL = "pull"    # source system -> canonical model
    PUSH = "push"    # canonical model -> target system


@dataclass
class Customer:
    external_id: str | None       # ID in the *source* system, if pulled from one
    name: str
    email: str | None = None
    phone: str | None = None
    tax_id: str | None = None      # KRA PIN, VAT number, etc.
    currency: str = "KES"
    is_company: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal(0)


@dataclass
class Invoice:
    external_id: str | None
    customer_external_id: str
    number: str | None
    currency: str
    issue_date: datetime
    due_date: datetime | None
    lines: list[InvoiceLine] = field(default_factory=list)
    status: str = "draft"          # draft | posted | paid | cancelled
    extra: dict = field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        return sum(
            (line.quantity * line.unit_price) * (1 + line.tax_rate / 100)
            for line in self.lines
        )


@dataclass
class Product:
    external_id: str | None
    sku: str
    name: str
    unit_price: Decimal
    currency: str = "KES"
    tracking: str = "none"         # none | lot | serial
    extra: dict = field(default_factory=dict)


@dataclass
class SyncResult:
    """Returned by every connector operation so callers get a uniform result
    regardless of which system they just talked to."""
    success: bool
    system: str
    operation: str
    external_id: str | None = None
    message: str = ""
    raw_response: dict | None = None
