"""Offline tests for the exact HTML renderer used by unattended v117 releases.

No network, customer records, insurer binary assets or publication occurs.
"""
import datetime as dt
import pathlib
import re
import sys
import unittest
from html.parser import HTMLParser

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from update_verified_rates import render, EXPECTED

ROOT=pathlib.Path(__file__).resolve().parents[1]
NAMES={"プレミアプレゼント5":"present","プレミアレシーブ2":"receive",
       "Moonshot（ムーンショット）":"moon"}
CURRENCIES={"米ドル":"USD","豪ドル":"AUD","円":"JPY"}

class DataRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_body=False;self.cell=None;self.row=None;self.records=[]
    def handle_starttag(self,tag,attrs):
        if tag=="tbody":self.in_body=True
        if self.in_body and tag=="tr":self.row=[]
        if self.row is not None and tag=="td":self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag=="td" and self.cell is not None:
            self.row.append("".join(self.cell).strip());self.cell=None
        if tag=="tr" and self.row is not None:
            self.records.append(self.row);self.row=None
        if tag=="tbody":self.in_body=False

def fixture():
    template=(ROOT/"rates-current.html").read_text(encoding="utf-8")
    match=re.search(r"const begins='(20\d{2}-\d{2}-\d{2})';",template)
    assert match
    start=dt.date.fromisoformat(match.group(1))
    end=dt.date.fromisoformat(re.search(r"const expires='(20\d{2}-\d{2}-\d{2})';",template).group(1))
    period=start.isoformat()+"～"+end.isoformat()
    parsed=DataRows();parsed.feed(template)
    records=[]
    for row in parsed.records:
        assert len(row)==8
        age=re.fullmatch(r"(\d+)～(\d+)歳",row[5])
        assert age
        payout=None
        if row[7]!="—":
            m=re.fullmatch(r"([\d.]+)%／([\d.]+)%",row[7]);assert m
            payout={"male":float(m.group(1)),"female":float(m.group(2))}
        records.append({
            "product_id":NAMES[row[1]],"currency":CURRENCIES[row[2]],
            "label":row[3],"term":row[4],
            "lo":int(age.group(1)),"hi":int(age.group(2)),
            "value":float(row[6].rstrip("%")),"period":period,
            "payout":payout
        })
    assert len(records)==sum(EXPECTED.values())
    return template,{"release_stage":"VALIDATED_NOT_PUBLISHED",
                     "period":period,"records":records},start

class V117AutoPublisherTests(unittest.TestCase):
    def setUp(self):
        self.template,self.stage,self.day=fixture()
    def test_existing_54_cells_roundtrip(self):
        rendered=render(self.template,self.stage,self.day)
        self.assertIn("rate-table",rendered)
        self.assertEqual(rendered.count("<tr><td>"),54)
        self.assertNotIn("srcdoc=",rendered)
    def test_future_half_month_updates_date_and_cells(self):
        start=dt.date(2026,12,1)
        period="2026-12-01～2026-12-15"
        stage={**self.stage,"period":period,
               "records":[{**r,"period":period} for r in self.stage["records"]]}
        out=render(self.template,stage,start)
        self.assertIn("const begins='2026-12-01';",out)
        self.assertIn("const expires='2026-12-15';",out)
        self.assertIn("対象：2026年12月1日～12月15日",out)
        self.assertEqual(out.count("<tr><td>"),54)
    def test_partial_batch_rejected(self):
        stage={**self.stage,"records":self.stage["records"][:-1]}
        with self.assertRaises(ValueError):render(self.template,stage,self.day)
    def test_bad_numeric_value_rejected(self):
        records=[dict(r) for r in self.stage["records"]]
        records[0]["value"]=999
        with self.assertRaises(ValueError):
            render(self.template,{**self.stage,"records":records},self.day)
    def test_internal_markup_rejected(self):
        records=[dict(r) for r in self.stage["records"]]
        records[0]["label"]='<script>private</script>'
        with self.assertRaises(ValueError):
            render(self.template,{**self.stage,"records":records},self.day)
    def test_bad_or_duplicate_dimension_rejected(self):
        records=[dict(r) for r in self.stage["records"]]
        records[1]=dict(records[0])
        with self.assertRaises(ValueError):
            render(self.template,{**self.stage,"records":records},self.day)
    def test_wrong_source_period_rejected(self):
        stage={**self.stage,"period":"2026-10-01～2026-10-15"}
        with self.assertRaises(ValueError):render(self.template,stage,self.day)
    def test_unknown_product_rejected(self):
        records=[dict(r) for r in self.stage["records"]]
        records[0]["product_id"]="customer"
        with self.assertRaises(ValueError):
            render(self.template,{**self.stage,"records":records},self.day)

if __name__=="__main__":
    unittest.main()
