"""
The connector contract.

Every ERP connector (Odoo, Business Central, a custom REST backend, or a
future one you add) implements this interface. Application code — sync
scripts, a scheduler, a CLI — is written against `ERPConnector`, never
against a specific vendor class. Swapping Odoo for a different platform
should mean swapping one connector instantiation, not rewriting the
integration logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Customer, Invoice, SyncResult


class ERPConnector(ABC):
    """Common interface every target system must satisfy."""

    #: Short machine-readable name used in logs and SyncResult.system
    system_name: str = "base"

    @abstractmethod
    def authenticate(self) -> None:
        """Establish a session / token. Must be idempotent — safe to call
        more than once (e.g. before every batch run)."""
        raise NotImplementedError

    @abstractmethod
    def get_customer(self, external_id: str) -> Customer | None:
        raise NotImplementedError

    @abstractmethod
    def upsert_customer(self, customer: Customer) -> SyncResult:
        """Create the customer if external_id is None or not found;
        otherwise update the existing record. Must be safe to retry —
        calling twice with the same data must not create duplicates."""
        raise NotImplementedError

    @abstractmethod
    def create_invoice(self, invoice: Invoice) -> SyncResult:
        raise NotImplementedError

    @abstractmethod
    def get_invoice_status(self, external_id: str) -> str | None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers — connectors get these for free, no need to override.
    # ------------------------------------------------------------------

    def health_check(self) -> SyncResult:
        """Cheap connectivity probe. Subclasses may override with a
        lighter-weight call (e.g. a version endpoint) if authenticate()
        is expensive."""
        try:
            self.authenticate()
            return SyncResult(success=True, system=self.system_name, operation="health_check")
        except Exception as exc:  # noqa: BLE001 - surface any failure uniformly
            return SyncResult(
                success=False,
                system=self.system_name,
                operation="health_check",
                message=str(exc),
            )
