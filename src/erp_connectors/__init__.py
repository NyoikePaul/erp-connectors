from .base import ERPConnector
from .dynamics_connector import DynamicsBCConnector
from .generic_rest_connector import GenericRESTConnector
from .models import Customer, Invoice, InvoiceLine, Product, SyncResult
from .odoo_connector import OdooConnector

__all__ = [
    "Customer",
    "DynamicsBCConnector",
    "ERPConnector",
    "GenericRESTConnector",
    "Invoice",
    "InvoiceLine",
    "OdooConnector",
    "Product",
    "SyncResult",
]

__version__ = "0.1.0"
