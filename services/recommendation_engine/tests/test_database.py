"""Guardrails for the read-only v0.2 source query."""

import unittest

from database import PRODUCT_ECONOMICS_QUERY


class UnitEconomicsQueryTests(unittest.TestCase):
    def test_cost_uses_confirmed_posting_quantity(self) -> None:
        self.assertIn("cost_price * quantity", PRODUCT_ECONOMICS_QUERY)
        self.assertIn("p.status = 'delivered'", PRODUCT_ECONOMICS_QUERY)

    def test_unattributed_advertising_is_not_included(self) -> None:
        self.assertNotIn("OperationMarketplaceCostPerClick", PRODUCT_ECONOMICS_QUERY)
        self.assertNotIn("InsuranceServiceSellerItem", PRODUCT_ECONOMICS_QUERY)
        self.assertNotIn("DisposalOfGoods", PRODUCT_ECONOMICS_QUERY)

    def test_windows_use_observed_effective_revenue_per_unit(self) -> None:
        self.assertIn("revenue / NULLIF(quantity, 0)", PRODUCT_ECONOMICS_QUERY)
