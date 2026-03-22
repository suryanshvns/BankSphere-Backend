from __future__ import annotations
from decimal import Decimal


def calculate_emi(principal: Decimal, annual_rate_pct: Decimal, tenure_months: int) -> Decimal:
    if tenure_months <= 0:
        raise ValueError("Tenure must be positive")
    if principal <= 0:
        raise ValueError("Principal must be positive")
    if annual_rate_pct < 0:
        raise ValueError("Rate cannot be negative")
    if annual_rate_pct == 0:
        return (principal / Decimal(tenure_months)).quantize(Decimal("0.01"))
    r = (annual_rate_pct / Decimal("100")) / Decimal("12")
    n = Decimal(tenure_months)
    one_plus_r_pow = (Decimal("1") + r) ** n
    emi = principal * r * one_plus_r_pow / (one_plus_r_pow - Decimal("1"))
    return emi.quantize(Decimal("0.01"))
