import datetime as dt
import unittest
from validate_rates import validate, japanese_period

class RateValidationTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 11, 19)
        self.row = {
            "company": "FWD生命", "product": "試験用商品", "rate_type": "積立利率",
            "currency": "JPY", "term_years": 10, "plan": "例示",
            "premium_band": "例示", "sex": "該当なし", "age_band": "例示",
            "effective_from": "2026-11-16", "effective_through": "2026-11-30",
            "rate_percent": 2.5, "source_url": "https://example.co.jp/rates",
            "source_published_at": "2026-11-16", "source_locator": "section 4 row 2",
            "retrieved_at": "2026-11-19T10:00:00+09:00",
            "source_verified": True, "source_type": "official_html"
        }
    def test_valid_structure(self):
        self.assertEqual(validate({"schema_version": 1, "records": [self.row]}, self.today), [])
    def test_old_period_blocked(self):
        row = {**self.row, "effective_through": "2026-11-15"}
        self.assertTrue(validate({"schema_version":1,"records":[row]},self.today))
    def test_unverified_blocked(self):
        row = {**self.row, "source_verified": False}
        self.assertTrue(validate({"schema_version":1,"records":[row]},self.today))
    def test_duplicate_blocked(self):
        self.assertTrue(validate({"schema_version":1,"records":[self.row,self.row]},self.today))
    def test_empty_blocked(self):
        self.assertTrue(validate({"schema_version":1,"records":[]},self.today))
    def test_period_boundary(self):
        self.assertEqual(japanese_period(dt.date(2026,12,1)),(dt.date(2026,12,1),dt.date(2026,12,15)))
        self.assertEqual(japanese_period(dt.date(2027,2,27)),(dt.date(2027,2,16),dt.date(2027,2,28)))
if __name__ == "__main__":
    unittest.main()
