from unittest.mock import MagicMock, patch

from erp_connectors.models import Customer, Invoice, InvoiceLine
from erp_connectors.odoo_connector import OdooConnector


def test_authenticate_sets_uid_and_models():
    common = MagicMock()
    common.authenticate.return_value = 42

    models = MagicMock()

    with patch("erp_connectors.odoo_connector.xmlrpc.client.ServerProxy") as server_proxy:
        server_proxy.side_effect = [common, models]

        connector = OdooConnector(
            url="https://odoo.example.com/",
            db="testdb",
            username="admin",
            api_key="secret",
        )

        connector.authenticate()
        connector.authenticate()

        assert connector._uid == 42
        assert connector._models is models
        assert server_proxy.call_count == 2


def test_get_customer_maps_odoo_record():
    models = MagicMock()
    models.execute_kw.return_value = [
        {
            "id": 42,
            "name": "Plantech Kenya Ltd",
            "email": "finance@plantech.co.ke",
            "phone": "+254700000000",
            "vat": "P051234567A",
            "is_company": True,
        }
    ]

    with patch("erp_connectors.odoo_connector.xmlrpc.client.ServerProxy") as server_proxy:
        common = MagicMock()
        common.authenticate.return_value = 42
        server_proxy.side_effect = [common, models]

        connector = OdooConnector("https://odoo.example.com", "db", "user", "key")

        customer = connector.get_customer("42")

        assert customer == Customer(
            external_id="42",
            name="Plantech Kenya Ltd",
            email="finance@plantech.co.ke",
            phone="+254700000000",
            tax_id="P051234567A",
            is_company=True,
        )

        models.execute_kw.assert_called_once()


def test_upsert_customer_create():
    models = MagicMock()
    models.execute_kw.return_value = 99

    with patch("erp_connectors.odoo_connector.xmlrpc.client.ServerProxy") as server_proxy:
        common = MagicMock()
        common.authenticate.return_value = 42
        server_proxy.side_effect = [common, models]

        connector = OdooConnector("https://odoo.example.com", "db", "user", "key")

        result = connector.upsert_customer(
            Customer(
                external_id=None,
                name="New Customer",
                email="customer@example.com",
            )
        )

        assert result.success
        assert result.operation == "upsert_customer:create"
        assert result.external_id == "99"


def test_upsert_customer_update():
    models = MagicMock()

    with patch("erp_connectors.odoo_connector.xmlrpc.client.ServerProxy") as server_proxy:
        common = MagicMock()
        common.authenticate.return_value = 42
        server_proxy.side_effect = [common, models]

        connector = OdooConnector("https://odoo.example.com", "db", "user", "key")

        result = connector.upsert_customer(
            Customer(
                external_id="99",
                name="Updated Customer",
                email="updated@example.com",
            )
        )

        assert result.success
        assert result.operation == "upsert_customer:update"
        assert result.external_id == "99"

        models.execute_kw.assert_called_once()


def test_create_invoice_maps_invoice_lines():
    models = MagicMock()
    models.execute_kw.return_value = 123

    with patch("erp_connectors.odoo_connector.xmlrpc.client.ServerProxy") as server_proxy:
        common = MagicMock()
        common.authenticate.return_value = 42
        server_proxy.side_effect = [common, models]

        connector = OdooConnector("https://odoo.example.com", "db", "user", "key")

        invoice = Invoice(
            external_id=None,
            customer_external_id="42",
            number=None,
            currency="KES",
            issue_date=None,
            due_date=None,
            lines=[
                InvoiceLine(
                    description="Rooted cuttings",
                    quantity=10,
                    unit_price=50,
                    tax_rate=16,
                )
            ],
        )

        result = connector.create_invoice(invoice)

        assert result.success
        assert result.operation == "create_invoice"
        assert result.external_id == "123"

        args = models.execute_kw.call_args.args
        assert args[0] == "db"
        assert args[1] == 42
        assert args[3] == "account.move"
        assert args[4] == "create"
        payload = args[5][0]
        assert payload["move_type"] == "out_invoice"
        assert payload["partner_id"] == 42
        assert payload["invoice_line_ids"][0][2]["name"] == "Rooted cuttings"
        assert payload["invoice_line_ids"][0][2]["quantity"] == 10.0
        assert payload["invoice_line_ids"][0][2]["price_unit"] == 50.0
