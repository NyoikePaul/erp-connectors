from .base import ERPConnector
from .dynamics_connector import DynamicsBCConnector
from .exceptions import (
    AuthenticationError,
    ERPConnectorError,
    NotFoundError,
    TransientError,
    ValidationError,
)
from .generic_rest_connector import GenericRESTConnector
from .models import Customer, Invoice, InvoiceLine, Product, SyncResult
from .odoo_connector import OdooConnector
from .status import normalize_status

__all__ = [
    "AuthenticationError",
    "Customer",
    "DynamicsBCConnector",
    "ERPConnector",
    "ERPConnectorError",
    "GenericRESTConnector",
    "Invoice",
    "InvoiceLine",
    "NotFoundError",
    "OdooConnector",
    "Product",
    "SyncResult",
    "TransientError",
    "ValidationError",
    "normalize_status",
]

__version__ = "0.1.0"
