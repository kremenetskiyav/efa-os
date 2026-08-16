from copy import deepcopy
import json
from pathlib import Path
import unittest

from services.information_intelligence.openapi import OpenAPIContractError, canonicalize_openapi, diff_openapi, structural_contract
from services.information_intelligence.usage import route_impact
from services.information_intelligence.usage import USAGE_MAP


BASE = json.loads((Path(__file__).parent / "fixtures" / "base.json").read_text(encoding="utf-8"))


class CanonicalizationTests(unittest.TestCase):
    def test_whitespace_and_object_key_order_are_equivalent(self):
        compact = json.dumps(BASE, separators=(",", ":"))
        reversed_keys = json.dumps({key: BASE[key] for key in reversed(BASE)}, indent=7)
        self.assertEqual(canonicalize_openapi(compact).canonical_sha256, canonicalize_openapi(reversed_keys).canonical_sha256)

    def test_arrays_are_not_reordered(self):
        changed = deepcopy(BASE)
        changed["components"]["schemas"]["Response"]["properties"]["status"]["enum"].reverse()
        self.assertNotEqual(canonicalize_openapi(json.dumps(BASE)).canonical_sha256, canonicalize_openapi(json.dumps(changed)).canonical_sha256)

    def test_structural_model_has_required_contract_sections(self):
        model = structural_contract(BASE)
        self.assertEqual(model["spec_version"], "3.0.3")
        self.assertIn("post", model["paths"]["/items"])
        self.assertIn("Response", model["components"]["schemas"])
        self.assertIn("ApiKey", model["components"]["securitySchemes"])
        self.assertEqual(model["paths"]["/items"]["post"]["security"], [{"ApiKey": []}])

    def test_malformed_json_is_rejected(self):
        with self.assertRaises(OpenAPIContractError):
            canonicalize_openapi("{")


class DiffClassificationTests(unittest.TestCase):
    def changed(self):
        return deepcopy(BASE)

    def test_no_change(self):
        self.assertEqual(diff_openapi(BASE, deepcopy(BASE)).classification, "NO_CHANGE")

    def test_description_only_is_info(self):
        value = self.changed()
        value["paths"]["/items"]["post"]["description"] = "Changed words"
        self.assertEqual(diff_openapi(BASE, value).classification, "INFO_ONLY")

    def test_new_optional_field_is_non_breaking(self):
        value = self.changed()
        value["components"]["schemas"]["Response"]["properties"]["note"] = {"type": "string"}
        self.assertEqual(diff_openapi(BASE, value).classification, "NON_BREAKING")

    def test_new_endpoint_is_non_breaking(self):
        value = self.changed()
        value["paths"]["/health"] = {"get": {"responses": {"200": {}}}}
        self.assertEqual(diff_openapi(BASE, value).classification, "NON_BREAKING")

    def test_required_request_field_added_is_breaking(self):
        value = self.changed()
        value["components"]["schemas"]["Request"]["required"] = ["query"]
        self.assertEqual(diff_openapi(BASE, value).classification, "BREAKING")

    def test_required_response_field_removed_is_breaking(self):
        value = self.changed()
        del value["components"]["schemas"]["Response"]["properties"]["status"]
        result = diff_openapi(BASE, value)
        self.assertEqual(result.classification, "BREAKING")

    def test_field_type_change_is_breaking(self):
        value = self.changed()
        value["components"]["schemas"]["Response"]["properties"]["status"]["type"] = "integer"
        self.assertEqual(diff_openapi(BASE, value).classification, "BREAKING")

    def test_enum_addition_requires_review(self):
        value = self.changed()
        value["components"]["schemas"]["Response"]["properties"]["status"]["enum"].append("ERROR")
        self.assertEqual(diff_openapi(BASE, value).classification, "REVIEW")

    def test_enum_removal_is_breaking(self):
        value = self.changed()
        value["components"]["schemas"]["Response"]["properties"]["status"]["enum"] = ["OK"]
        self.assertEqual(diff_openapi(BASE, value).classification, "BREAKING")

    def test_endpoint_removal_is_breaking(self):
        value = self.changed()
        del value["paths"]["/items"]
        self.assertEqual(diff_openapi(BASE, value).classification, "BREAKING")

    def test_security_change_is_breaking(self):
        value = self.changed()
        value["paths"]["/items"]["post"]["security"] = []
        self.assertEqual(diff_openapi(BASE, value).classification, "BREAKING")

    def test_used_endpoint_break_routes_only_matching_subsystem(self):
        old = {"openapi": "3.0.3", "paths": {"/v1/analytics/data": {"post": {"responses": {"200": {}}}}}}
        new = {"openapi": "3.0.3", "paths": {}}
        routed = route_impact(diff_openapi(old, new), "SELLER")
        affected = [item for item in routed if item["impact"] == "AFFECTED"]
        self.assertEqual([(item["subsystem"], item["severity"]) for item in affected], [("SELLERDAILYV1", "CRITICAL")])

    def test_usage_map_contains_only_read_contracts_for_active_collectors(self):
        self.assertEqual({item.subsystem for item in USAGE_MAP}, {"PROMOAUTOV1", "SELLERDAILYV1", "Price Snapshot Automation", "CPCDAILYV1"})
        self.assertFalse(any(item.method in {"PUT", "PATCH", "DELETE"} for item in USAGE_MAP))


if __name__ == "__main__":
    unittest.main()
