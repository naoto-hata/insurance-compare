import copy
import datetime as dt
import unittest
from stage_rates import stage

class StageRatesTests(unittest.TestCase):
    def setUp(self):
        self.today=dt.date(2026,11,19)
        self.url="https://www.test-life.co.jp/rates"
        self.hash="a"*64
        self.snapshot={"release":"v117","publication_allowed":False,
            "catalog":[{"id":"test","rateurl":self.url}],
            "rates":[
                {"product_id":"test","currency":"JPY","label":"基本","term":"10年","lo":20,"hi":65,"period":"2026-10-16～2026-10-31"},
                {"product_id":"test","currency":"JPY","label":"基本","term":"10年","lo":66,"hi":80,"period":"2026-10-16～2026-10-31"}]}
        self.sources={"sources":[{"id":"test","url":self.url}]}
        self.audit={"sources":[{"id":"test","status":"reachable","sha256":self.hash,
                                  "checked_at_jst":"2026-11-19T10:00:00+09:00"}]}
        self.one={"product_id":"test","currency":"JPY","label":"基本","term":"10年",
                  "lo":20,"hi":65,"value":2.55,"period":"2026-11-16～2026-11-30",
                  "source_url":self.url,"source_sha256":self.hash,
                  "source_locator":"table A row 3","source_value_text":"2.55％",
                  "extraction_method":"official_html_table",
                  "source_observed_at":"2026-11-19T10:00:00+09:00",
                  "payout":None}
        self.two={**self.one,"lo":66,"hi":80,"value":2.65,"source_value_text":"2.65％",
                  "source_locator":"table A row 4"}
    def run_stage(self,records):
        return stage(self.snapshot,self.sources,self.audit,{"records":records},self.today)
    def test_valid_complete_product(self):
        result=self.run_stage([self.one,self.two])
        self.assertEqual(result["release_stage"],"VALIDATED_NOT_PUBLISHED")
        self.assertEqual(len(result["records"]),2)
    def test_partial_product_blocked(self):
        with self.assertRaisesRegex(ValueError,"expected rate condition"):
            self.run_stage([self.one])
    def test_unknown_condition_blocked(self):
        with self.assertRaisesRegex(ValueError,"unknown currency"):
            self.run_stage([self.one,{**self.two,"hi":90}])
    def test_old_period_blocked(self):
        with self.assertRaisesRegex(ValueError,"date period"):
            self.run_stage([{**self.one,"period":"2026-11-01～2026-11-15"},self.two])
    def test_source_hash_change_blocked(self):
        with self.assertRaisesRegex(ValueError,"source evidence hash"):
            self.run_stage([{**self.one,"source_sha256":"b"*64},self.two])
    def test_source_url_change_blocked(self):
        with self.assertRaisesRegex(ValueError,"source URL differs"):
            self.run_stage([{**self.one,"source_url":"https://random.co.jp"},self.two])
    def test_payout_evidence_required(self):
        with self.assertRaisesRegex(ValueError,"payout source locators"):
            self.run_stage([{**self.one,"payout":{"male":3.4,"female":3.2}},self.two])
    def test_duplicate_blocked(self):
        with self.assertRaisesRegex(ValueError,"duplicated rate dimension"):
            self.run_stage([self.one,self.two,copy.deepcopy(self.two)])
    def test_mismatched_quote_blocked(self):
        with self.assertRaisesRegex(ValueError,"differs from numeric"):
            self.run_stage([{**self.one,"source_value_text":"9.12％"},self.two])
    def test_no_records_blocked(self):
        with self.assertRaisesRegex(ValueError,"empty"):
            self.run_stage([])
if __name__=="__main__":
    unittest.main()
