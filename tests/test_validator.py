import unittest

from ai.parser import normalize_expected, parse_fields_from_text
from validator.validator import validate, summarize


class ValidatorTests(unittest.TestCase):
    def test_normalize_aliases(self):
        data = normalize_expected({"brand_name": "CORONA", "abv": "4.5%", "volume": "355 ml", "country": "Mexico"})
        self.assertEqual(data["brand"], "CORONA")
        self.assertEqual(data["alcohol_content"], "4.5%")
        self.assertEqual(data["net_contents"], "355 ml")
        self.assertEqual(data["country_of_origin"], "Mexico")

    def test_parse_and_validate_pass(self):
        raw = "CORONA EXTRA Pale Lager 4.5% ABV 355 ml Produced and bottled in Mexico GOVERNMENT WARNING according to the surgeon general"
        extracted = parse_fields_from_text(raw)
        expected = normalize_expected({
            "brand": "CORONA",
            "class_type": "Pale Lager",
            "alcohol_content": "4.5% ABV",
            "net_contents": "355 ml",
            "country_of_origin": "Mexico",
            "government_warning_required": True,
        })
        rows = validate(expected, extracted, raw)
        summary = summarize(rows)
        self.assertEqual(summary["fail"], 0)
        self.assertIn(summary["overall"], ["PASS", "REVIEW REQUIRED"])

    def test_missing_warning_fails(self):
        rows = validate({"government_warning_required": True}, {}, "CORONA EXTRA")
        summary = summarize(rows)
        self.assertEqual(summary["fail"], 1)
        self.assertEqual(summary["overall"], "FAIL")


if __name__ == "__main__":
    unittest.main()
