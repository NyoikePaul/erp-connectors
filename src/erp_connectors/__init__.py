from .base import ERPConnector
from .exceptions import (
    AuthenticationError,
    ERPConnectorError,
    NotFoundError,
    TransientError,
    ValidationError,
)
from .status import normalize_status
from .dynamics_connector import DynamicsBCConnector
from .generic_rest_connector import GenericRESTConnector
from .models import Customer, Invoice, InvoiceLine, Product, SyncResult
from .odoo_connector import OdooConnector

__all__ = [
    "AuthenticationError",
    "Customer",
    "DynamicsBCConnector",
    "normalize_status",
    "ValidationError",
    "TransientError",
    "NotFoundError",
    "ERPConnectorError",
    "ERPConnector",
    "GenericRESTConnector",
    "Invoice",
    "InvoiceLine",
    "OdooConnector",
    "Product",
    "SyncResult",
]

__version__ = "0.1.0"
