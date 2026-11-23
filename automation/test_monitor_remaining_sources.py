import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from monitor_remaining_sources import analyze_sources, SOURCES, classify_response, MAX_BYTES
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
    def test_large_html_is_reachable_but_unparsed(self):
        self.assertEqual(classify_response(200,b"<html>"+b"a"*MAX_BYTES,"text/html"),
                         "LARGE_PAGE_ACCESSIBLE_NOT_PARSED")
    def test_pdf_source_is_not_rate_verified(self):
        self.assertEqual(classify_response(200,b"%PDF-test","application/pdf"),
                         "OFFICIAL_PDF_ACCESSIBLE_NOT_PARSED")
    def test_empty_or_failed_http_does_not_claim_values(self):
        self.assertEqual(classify_response(200,b"","text/html"),
                         "EMPTY_SOURCE_REVIEW_REQUIRED")
        self.assertEqual(classify_response(503,b"error","text/html"),
                         "HTTP_STATUS_REVIEW_REQUIRED")
    def test_regular_html_not_numeric_rate_verification(self):
        self.assertEqual(classify_response(200,b"<html>rate</html>","text/html"),
                         "REACHABLE_RATE_VALUES_UNVERIFIED")
    def test_duplicate_product_rejected(self):
        catalog=json.loads(json.dumps(self.catalog))
        catalog["sources"][0]["id"]=catalog["sources"][1]["id"]
        with self.assertRaises(ValueError):analyze_sources(catalog)
if __name__=="__main__":
    unittest.main()
