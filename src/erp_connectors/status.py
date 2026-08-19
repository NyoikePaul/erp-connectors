STATUS_MAP = {
    "odoo": {
        "draft": "draft",
        "posted": "posted",
        "cancel": "cancelled",
    },
    "dynamics_bc": {
        "Draft": "draft",
        "Open": "posted",
        "Paid": "paid",
        "Canceled": "cancelled",
    },
}


def normalize_status(system: str, raw: str | None) -> str | None:
    if raw is None:
        return None
    return STATUS_MAP.get(system, {}).get(raw, raw.lower())
