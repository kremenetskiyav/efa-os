from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TaxpayerConfig:
    tax_year: int
    region: str
    tax_authority: str
    entity_type: str
    usn_object: str
    usn_rate: Decimal
    has_employees: bool
    prior_year_business_income: Decimal
    non_ozon_income_ytd: Decimal
    insurance_contributions_paid_ytd: Decimal
    fixed_insurance_contribution: Decimal
    additional_contribution_threshold: Decimal
    additional_contribution_rate: Decimal
    additional_contribution_cap: Decimal
    vat_status: str
    vat_threshold: Decimal
    vat_warning_ratio: Decimal

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaxpayerConfig":
        decimal_fields = {"usn_rate","prior_year_business_income","non_ozon_income_ytd",
                          "insurance_contributions_paid_ytd","fixed_insurance_contribution",
                          "additional_contribution_threshold","additional_contribution_rate",
                          "additional_contribution_cap","vat_threshold","vat_warning_ratio"}
        data = {key: Decimal(str(item)) if key in decimal_fields else item for key,item in value.items() if key != "version"}
        return cls(**data)


@dataclass(frozen=True)
class TaxRevenueEvent:
    event_id: str
    tax_year: int
    source_period: str
    event_type: str
    amount: Decimal
    source_document: str
    source_reference: str
    tax_semantics_status: str
    tax_date_status: str
    data_quality_status: str
    posting_number: str | None = None
    offer_id: str | None = None
    sku: int | None = None
    event_date: str | None = None
