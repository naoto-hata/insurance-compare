import datetime as dt
import unittest
from parse_moonshot import parse_official_html, SOURCE_URL

HTML = """<!doctype html><html lang="ja"><body>
<h1>一時払終身保険Moonshot 積立利率・為替レート照会</h1>
<p>2026年11月16日～2026年11月30日が契約日となる契約</p>
<table><thead><tr><th>指定通貨</th><th>積立利率保証期間</th><th>積立利率</th></tr></thead>
<tbody><tr><td>米ドル</td><td>10年</td><td>4.85%</td></tr>
<tr><td>円</td><td>10年</td><td>2.55%</td></tr></tbody></table>
</body></html>"""

class MoonshotAdapterTests(unittest.TestCase):
    def setUp(self):
        self.day=dt.date(2026,11,19)
    def parse(self,source):
        return parse_official_html(source.encode("utf-8"),self.day,"2026-11-19T10:00:00+09:00")
    def test_valid_pair(self):
        result=self.parse(HTML)
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(len(result["records"]),2)
        self.assertEqual(result["records"][0]["value"],4.85)
        self.assertEqual(result["records"][1]["source_url"],SOURCE_URL)
        self.assertEqual(result["records"][1]["source_value_text"],"2.55%")
    def test_missing_currency_blocks(self):
        with self.assertRaisesRegex(ValueError,"both Moonshot"):
            self.parse(HTML.replace("<tr><td>円</td><td>10年</td><td>2.55%</td></tr>",""))
    def test_duplicate_blocks(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            self.parse(HTML.replace("</tbody>",'<tr><td>円</td><td>10年</td><td>2.55%</td></tr></tbody>'))
    def test_old_period_blocks(self):
        with self.assertRaisesRegex(ValueError,"period"):
            self.parse(HTML.replace("11月16日～2026年11月30日","11月1日～2026年11月15日"))
    def test_changed_rate_format_blocks(self):
        with self.assertRaisesRegex(ValueError,"Invalid rate cell"):
            self.parse(HTML.replace("4.85%","not a rate"))
    def test_wrong_heading_blocks(self):
        with self.assertRaisesRegex(ValueError,"heading"):
            self.parse(HTML.replace("Moonshot","Test"))
if __name__=="__main__":
    unittest.main()
