"""Regression and domain tests for EFA Ozon Price Calculator V1."""

from decimal import Decimal, localcontext
import unittest

from calculator import (
    CalculatorValidationError,
    MarginClassification,
    MarginPolicy,
    calculate_unit_economics,
    classify_margin,
    find_price_for_margin,
)


D = Decimal
GOLDEN_INPUTS = {
    "cost_price": D("166"),
    "commission_rate": D("0.42"),
    "acquiring_rate": D("0.015"),
    "processing_amount": D("10"),
    "forward_logistics_amount": D("84"),
    "delivery_to_customer_amount": D("25"),
    "return_logistics_amount": D("84"),
    "return_processing_amount": D("15"),
    "buyout_rate": D("0.92"),
    "tax_rate": D("0.06"),
    "other_expenses": D("0"),
}


class GoldenCalculatorTests(unittest.TestCase):
    def test_uf_001b_matches_validated_ecomunit_checkpoint(self):
        result = calculate_unit_economics(seller_price=D("910"), **GOLDEN_INPUTS)

        self.assertEqual(result.seller_price, D("910.00"))
        self.assertEqual(result.commission_amount, D("382.20"))
        self.assertEqual(result.acquiring_amount, D("13.65"))
        self.assertEqual(result.tax_amount, D("54.60"))
        self.assertEqual(result.failed_order_cost, D("218.00"))
        self.assertEqual(result.expected_nonbuyout_cost, D("18.96"))
        self.assertEqual(result.profit, D("155.59"))
        self.assertLess(abs(result.margin - D("0.170981844243")), D("0.000000000001"))

        exact_profit = D("155.59347826086956521739130434782608695652173913043")
        with localcontext() as context:
            context.prec = 50
            self.assertLessEqual(abs(result.margin * D("910") - exact_profit), D("1e-47"))

    def test_golden_price_search_returns_minimum_integer_prices(self):
        targets = ((D("0.10"), D("751"), D("750")),
                   (D("0.12"), D("790"), D("789")),
                   (D("0.15"), D("857"), D("856")))

        for target, expected_price, prior_price in targets:
            with self.subTest(target=target):
                found = find_price_for_margin(
                    target_margin=target,
                    search_from=D("700"),
                    search_to=D("1000"),
                    **GOLDEN_INPUTS,
                )
                self.assertEqual(found, expected_price)
                self.assertLess(
                    calculate_unit_economics(
                        seller_price=prior_price,
                        **GOLDEN_INPUTS,
                    ).margin,
                    target,
                )
                self.assertGreaterEqual(
                    calculate_unit_economics(
                        seller_price=found,
                        **GOLDEN_INPUTS,
                    ).margin,
                    target,
                )


class CalculatorDomainTests(unittest.TestCase):
    def test_zero_variable_rates_and_full_buyout(self):
        cases = (
            ("commission_rate", D("0"), "commission_amount"),
            ("acquiring_rate", D("0"), "acquiring_amount"),
            ("tax_rate", D("0"), "tax_amount"),
        )
        for input_name, input_value, result_name in cases:
            with self.subTest(input_name=input_name):
                inputs = {**GOLDEN_INPUTS, input_name: input_value}
                result = calculate_unit_economics(seller_price=D("910"), **inputs)
                self.assertEqual(getattr(result, result_name), D("0.00"))

        full_buyout = calculate_unit_economics(
            seller_price=D("910"),
            **{**GOLDEN_INPUTS, "buyout_rate": D("1")},
        )
        self.assertEqual(full_buyout.expected_nonbuyout_cost, D("0.00"))

    def test_invalid_economics_inputs_raise_domain_error(self):
        for seller_price in (D("0"), D("-1")):
            with self.subTest(seller_price=seller_price):
                with self.assertRaises(CalculatorValidationError):
                    calculate_unit_economics(seller_price=seller_price, **GOLDEN_INPUTS)

        for buyout_rate in (D("0"), D("1.01")):
            with self.subTest(buyout_rate=buyout_rate):
                with self.assertRaises(CalculatorValidationError):
                    calculate_unit_economics(
                        seller_price=D("910"),
                        **{**GOLDEN_INPUTS, "buyout_rate": buyout_rate},
                    )

        with self.assertRaises(CalculatorValidationError):
            calculate_unit_economics(
                seller_price=D("910"),
                **{**GOLDEN_INPUTS, "processing_amount": D("-0.01")},
            )

    def test_price_search_returns_none_when_target_is_not_found(self):
        self.assertIsNone(
            find_price_for_margin(
                target_margin=D("0.15"),
                search_from=D("700"),
                search_to=D("700"),
                **GOLDEN_INPUTS,
            )
        )

    def test_non_progressing_decimal_price_step_raises_domain_error(self):
        with self.assertRaises(CalculatorValidationError):
            find_price_for_margin(
                target_margin=D("1"),
                search_from=D("1e20"),
                search_to=D("2e20"),
                price_step=D("1e-20"),
                **GOLDEN_INPUTS,
            )

    def test_seller_price_preserves_exact_input_value(self):
        exact_price = D("910.001")
        result = calculate_unit_economics(seller_price=exact_price, **GOLDEN_INPUTS)
        rounded_price_result = calculate_unit_economics(seller_price=D("910.00"), **GOLDEN_INPUTS)

        self.assertEqual(result.seller_price, exact_price)
        self.assertNotEqual(result.margin, rounded_price_result.margin)

    def test_margin_classification_boundaries(self):
        policy = MarginPolicy(D("0.10"), D("0.12"), D("0.15"))
        cases = (
            (D("0.099999"), MarginClassification.HARD_FLOOR_VIOLATION),
            (D("0.10"), MarginClassification.BELOW_WORKING_MINIMUM),
            (D("0.12"), MarginClassification.BELOW_TARGET),
            (D("0.15"), MarginClassification.TARGET_OR_ABOVE),
        )
        for margin, expected in cases:
            with self.subTest(margin=margin):
                self.assertEqual(classify_margin(margin, policy), expected)


if __name__ == "__main__":
    unittest.main()
