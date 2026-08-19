"""One-way pull → push sync helpers."""

from __future__ import annotations

from erp_connectors.base import ERPConnector
from erp_connectors.models import Customer, SyncResult


def sync_customer(
    source: ERPConnector,
    target: ERPConnector,
    source_external_id: str,
) -> SyncResult:
    """Pull customer from source and upsert into target as a new record."""
    customer = source.get_customer(source_external_id)
    if customer is None:
        return SyncResult(
            success=False,
            system=target.system_name,
            operation="sync_customer",
            message=f"Customer {source_external_id} not found in {source.system_name}",
        )

    payload = Customer(
        external_id=None,  # create in target
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        tax_id=customer.tax_id,
        currency=customer.currency,
        is_company=customer.is_company,
        extra=customer.extra,
    )
    return target.upsert_customer(payload)
