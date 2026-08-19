"""
Example: pull one customer from Odoo and push it into both Business Central
and a custom Next.js ERP — the scenario this whole toolkit exists for.

This is the flagship demo: the SAME `Customer` object, unmodified, is
accepted by three completely different systems because each connector
speaks the canonical model, not its own native schema.

Run with real credentials via environment variables, or point at local
sandboxes / mocks while you're first wiring this up.
"""

import os

from erp_connectors import Customer, DynamicsBCConnector, GenericRESTConnector, OdooConnector


def main() -> None:
    odoo = OdooConnector(
        url=os.environ["ODOO_URL"],
        db=os.environ["ODOO_DB"],
        username=os.environ["ODOO_USERNAME"],
        api_key=os.environ["ODOO_API_KEY"],
    )
    bc = DynamicsBCConnector(
        tenant_id=os.environ["BC_TENANT_ID"],
        client_id=os.environ["BC_CLIENT_ID"],
        client_secret=os.environ["BC_CLIENT_SECRET"],
        environment=os.environ.get("BC_ENVIRONMENT", "production"),
        company_id=os.environ["BC_COMPANY_ID"],
    )
    custom_erp = GenericRESTConnector(
        base_url=os.environ["CUSTOM_ERP_URL"],
        token=os.environ["CUSTOM_ERP_TOKEN"],
    )

    # 1. Pull the canonical record from the source of truth (Odoo, here).
    source_id = os.environ["ODOO_CUSTOMER_ID"]
    customer = odoo.get_customer(source_id)
    if customer is None:
        raise SystemExit(f"No customer {source_id} found in Odoo.")

    print(f"Pulled from Odoo: {customer.name} <{customer.email}>")

    # 2. Push the SAME object into every other system. Each connector clears
    #    its own external_id first since this is a new record in that system.
    for label, connector in [("Business Central", bc), ("Custom Next.js ERP", custom_erp)]:
        target_customer = Customer(
            external_id=None,  # unknown in the target system -> creates new
            name=customer.name, email=customer.email, phone=customer.phone,
            tax_id=customer.tax_id, currency=customer.currency,
            is_company=customer.is_company,
        )
        result = connector.upsert_customer(target_customer)
        status = "OK" if result.success else "FAILED"
        print(f"[{status}] {label}: external_id={result.external_id} {result.message}")


if __name__ == "__main__":
    main()
