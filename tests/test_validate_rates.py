#!/usr/bin/env python3
"""Deterministic tests; no website access or live source required."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from scripts.validate_rates import validate

TODAY = dt.date(2026, 11, 18)
GOOD = {"product_id":"present","currency":"USD","condition_id":"10-year_age-60","label":"基本プラン","term":"10年","lo":20,"hi":80,
        "rate_percent":4.2,"valid_from":"2026-11-16","valid_to":"2026-11-30",
        "official_url":"https://example.test/official","verified_on":"2026-11-17",
        "verification":"approved","source_label":"official product-specific condition table"}
class ValidatorTests(unittest.TestCase):
    def test_valid_record(self):
        self.assertEqual(validate([GOOD],TODAY),[])
    def test_duplicate(self):
        self.assertTrue(any("duplicate" in x for x in validate([GOOD,GOOD],TODAY)))
    def test_historical_approved_is_allowed_as_history(self):
        row={**GOOD,"valid_to":"2026-11-17"}
        self.assertEqual(validate([row],TODAY),[])
    def test_pending_expired_allowed_but_not_published(self):
        row={**GOOD,"verification":"pending","valid_to":"2026-11-17"}
        self.assertEqual(validate([row],TODAY),[])
    def test_missing_condition(self):
        row={k:v for k,v in GOOD.items() if k!="condition_id"}
        self.assertTrue(validate([row],TODAY))
    def test_bad_url(self):
        self.assertTrue(validate([{**GOOD,"official_url":"http://bad.example"}],TODAY))
    def test_unreasonable_rate(self):
        self.assertTrue(validate([{**GOOD,"rate_percent":40}],TODAY))
    def test_invalid_age_range(self):
        self.assertTrue(validate([{**GOOD,"lo":90,"hi":20}],TODAY))
    def test_boolean_not_number(self):
        self.assertTrue(validate([{**GOOD,"rate_percent":True}],TODAY))
if __name__=="__main__":
    unittest.main()
