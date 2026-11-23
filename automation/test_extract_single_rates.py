import unittest
from extract_single_rates import extract

class EmbeddedRateExtractionTests(unittest.TestCase):
    def setUp(self):
        self.products = [{
            "id": "test_id", "company": "テスト生命", "name": "テスト商品",
            "kind": "一時払", "url": "https://example.co.jp/product",
            "rateurl": "https://example.co.jp/rates",
            "checked": "2026-11-16", "rates": [
                {"currency": "JPY", "label": "基本プラン", "value": 2.51,
                 "term": "10年", "lo": 20, "hi": 65,
                 "period": "2026-11-16～2026-11-30",
                 "payout": {"male": 2.1, "female": 2.2}}
            ], "thumbnail": "data:image/webp;base64,AAA"}]
    def test_export_preserves_dimensions(self):
        result = extract(self.products)
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(result["rates"][0]["age_min"],20)
        self.assertEqual(result["rates"][0]["payout"]["female"],2.2)
        self.assertEqual(result["rates"][0]["source_url"],"https://example.co.jp/rates")
        self.assertNotIn("thumbnail",str(result))
    def test_invalid_period_fails_closed(self):
        self.products[0]["rates"][0]["period"] = "11/16"
        with self.assertRaises(ValueError):
            extract(self.products)
    def test_duplicate_fails_closed(self):
        self.products[0]["rates"].append(dict(self.products[0]["rates"][0]))
        with self.assertRaises(ValueError):
            extract(self.products)
    def test_empty_fails_closed(self):
        self.products[0]["rates"] = []
        with self.assertRaises(ValueError):
            extract(self.products)
if __name__ == "__main__":
    unittest.main()
