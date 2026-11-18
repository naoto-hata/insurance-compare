#!/usr/bin/env python3
"""Integration tests for the actually published v117 chunk format."""
import datetime as dt
import html
import json
import re
import unittest
from scripts.apply_verified_rates_v117 import read, js_length, checksum
from scripts.apply_verified_rates import SINGLE, PREFIX, apply

class LivePublishedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outer,cls.files,cls.loader=read()
    def test_public_loader_integrity(self):
        self.assertIn('第117版・一時払利率11月16日確認',self.outer)
        self.assertIn('hash!==0x'+format(checksum(self.outer),'08x'),self.loader)
        self.assertIn('page.length!=='+str(js_length(self.outer)),self.loader)
        self.assertEqual(len(self.files),32)
    def test_single_premium_catalog(self):
        m=SINGLE.search(self.outer)
        self.assertIsNotNone(m)
        inner=html.unescape(m.group(2))
        products=json.JSONDecoder().raw_decode(inner.split(PREFIX,1)[1])[0]
        self.assertEqual(len(products),13)
        self.assertEqual(len({p['id'] for p in products}),13)
        sony=next(p for p in products if p['id']=='sony')
        current=[r for r in sony['rates'] if r.get('period')=='2026-11-16～2026-11-30']
        self.assertEqual(len(current),10)
    def test_synthetic_addition_never_committed(self):
        m=SINGLE.search(self.outer)
        products=json.JSONDecoder().raw_decode(html.unescape(m.group(2)).split(PREFIX,1)[1])[0]
        sony=next(p for p in products if p['id']=='sony')
        template=sony['rates'][0]
        row={"product_id":"sony","currency":template['currency'],"label":template['label'],
             "term":template['term'],"lo":template['lo'],"hi":template['hi'],
             "rate_percent":6.22,"valid_from":"2026-12-01","valid_to":"2026-12-15",
             "verification":"approved","source_label":"synthetic unit test"}
        new,count=apply(self.outer,[row],dt.date(2026,12,2))
        self.assertEqual(count,1)
        self.assertIn('2026-12-01～2026-12-15',new)
        self.assertNotIn('2026-12-01～2026-12-15',self.outer)

if __name__=='__main__':
    unittest.main()
