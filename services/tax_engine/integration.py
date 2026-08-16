from __future__ import annotations

from decimal import Decimal


def after_tax_management_economics(profit_before_tax: Decimal | None,
                                   taxable_revenue: Decimal | None,
                                   reserve_rate: Decimal | None,
                                   tax_quality: str) -> dict[str, object]:
    """Add an estimate beside confirmed profit; never mutate or rename the source fact."""
    if profit_before_tax is None or taxable_revenue is None or reserve_rate is None:
        return {"profit_before_tax":profit_before_tax,"management_tax_reserve":None,
                "profit_after_tax_estimate":None,"status":"NOT_AVAILABLE"}
    reserve = (taxable_revenue * reserve_rate).quantize(Decimal("0.01"))
    return {"profit_before_tax":profit_before_tax,"management_tax_reserve":reserve,
            "profit_after_tax_estimate":profit_before_tax-reserve,
            "status":"ESTIMATED" if tax_quality == "CONFIRMED" else "PARTIAL"}
