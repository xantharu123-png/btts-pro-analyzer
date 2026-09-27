"""One server-owned price/feature catalogue. Quality is not a paid upgrade."""
PLANS = {
    "starter": {"name": "Starter", "cents": 990, "price": "9.90", "features": ("automatic", "saved")},
    "plus": {"name": "Plus", "cents": 1990, "price": "19.90", "features": ("automatic", "saved", "search", "riskobet")},
    "pro": {"name": "Pro", "cents": 2990, "price": "29.90", "features": ("automatic", "saved", "search", "riskobet", "live", "daily3", "15k")},
}


def valid_plan(value):
    return value if value in PLANS else "starter"
