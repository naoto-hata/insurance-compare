import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from monitor_remaining_sources import analyze_sources, SOURCES
import json

class RemainingSourcesTests(unittest.TestCase):
    def setUp(self):
        self.catalog=json.loads(SOURCES.read_text(encoding="utf-8"))
    def test_expected_ten_remaining_products(self):
        other=analyze_sources(self.catalog)
        self.assertEqual(len(other),10)
        self.assertNotIn("present",[p["id"] for p in other])
    def test_unofficial_host_rejected(self):
        catalog=json.loads(json.dumps(self.catalog))
        catalog["sources"][0]["url"]="https://untrusted.example/rates"
        with self.assertRaises(ValueError):analyze_sources(catalog)
    def test_insecure_http_rejected(self):
        catalog=json.loads(json.dumps(self.catalog))
        catalog["sources"][0]["url"]="http://www.metlife.co.jp/rates"
        with self.assertRaises(ValueError):analyze_sources(catalog)
    def test_duplicate_product_rejected(self):
        catalog=json.loads(json.dumps(self.catalog))
        catalog["sources"][0]["id"]=catalog["sources"][1]["id"]
        with self.assertRaises(ValueError):analyze_sources(catalog)
if __name__=="__main__":
    unittest.main()
