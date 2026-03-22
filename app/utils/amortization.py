from __future__ import annotations

from decimal import Decimal

from app.utils.emi import calculate_emi


def build_loan_schedule(
    principal: Decimal,
    annual_rate_pct: Decimal,
    tenure_months: int,
) -> list[dict[str, str]]:
    if tenure_months <= 0 or principal <= 0:
        return []
    emi = calculate_emi(principal, annual_rate_pct, tenure_months)
    r = (annual_rate_pct / Decimal("100")) / Decimal("12")
    bal = principal
    out: list[dict[str, str]] = []
    for m in range(1, tenure_months + 1):
        if annual_rate_pct == 0:
            interest = Decimal("0")
            principal_part = emi
        else:
            interest = (bal * r).quantize(Decimal("0.01"))
            principal_part = (emi - interest).quantize(Decimal("0.01"))
        bal = (bal - principal_part).quantize(Decimal("0.01"))
        if bal < 0:
            bal = Decimal("0")
        out.append(
            {
                "installment": str(m),
                "emi": str(emi),
                "principal_component": str(principal_part),
                "interest_component": str(interest),
                "remaining_principal": str(bal),
            }
        )
    return out
