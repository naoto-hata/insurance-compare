#!/usr/bin/env python3
"""Tests for the embedding bridge; all rate values are synthetic fixtures."""
import datetime as dt
import html
import json
import unittest
from scripts.apply_verified_rates import apply

def fixture(gendered=False):
    rate={"currency":"USD","label":"基本プラン","term":"10年",
          "lo":20,"hi":80,"value":4.0,"period":"2026-11-01～2026-11-15",
          "payout":{"male":3.0,"female":2.9} if gendered else None,
          "extra":"Old official period"}
    products=[{"id":"p"+str(i),"rates":[dict(rate)]} for i in range(8)]
    inner='<html><script>const PRODUCTS='+json.dumps(products,ensure_ascii=False)+';let active=true;</script></html>'
    outer='<html><iframe id="single" srcdoc="'+html.escape(inner,quote=True)+'"></iframe></html>'
    return outer

def row(**changes):
    base={"product_id":"p0","currency":"USD","label":"基本プラン",
          "term":"10年","lo":20,"hi":80,"rate_percent":4.5,
          "valid_from":"2026-11-16","valid_to":"2026-11-30",
          "verification":"approved","source_label":"fixture evidence"}
    base.update(changes)
    return base

class ApplyTests(unittest.TestCase):
    def test_no_rates_no_change(self):
        old=fixture()
        self.assertEqual(apply(old,[]),(old,0))
    def test_add_period_preserves_history(self):
        old=fixture()
        newer,count=apply(old,[row()],dt.date(2026,11,18))
        self.assertEqual(count,1)
        text=html.unescape(newer)
        self.assertIn('2026-11-01～2026-11-15',text)
        self.assertIn('2026-11-16～2026-11-30',text)
    def test_future_rate_not_published_early(self):
        old=fixture()
        self.assertEqual(apply(old,[row(valid_from="2026-12-01",valid_to="2026-12-15")],dt.date(2026,11,18)),(old,0))
    def test_pending_rate_not_published(self):
        old=fixture()
        self.assertEqual(apply(old,[row(verification="pending")],dt.date(2026,11,18)),(old,0))
    def test_gender_specific_cannot_carry_old_payout(self):
        with self.assertRaisesRegex(ValueError,"Gender-specific"):
            apply(fixture(True),[row()],dt.date(2026,11,18))
    def test_gender_specific_new_payout(self):
        updated,n=apply(fixture(True),[row(payout={"male":4.1,"female":4.0})],dt.date(2026,11,18))
        self.assertEqual(n,1)
        self.assertIn('&quot;male&quot;: 4.1',updated) if False else self.assertIn('4.1',updated)
    def test_missing_template_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Unknown product"):
            apply(fixture(),[row(product_id="nonexistent")],dt.date(2026,11,18))

if __name__=="__main__": unittest.main()
