import datetime as dt
import unittest
from parse_dfl import extract

DAY=dt.date(2026,11,19)
DATES='<p>2026年11月16日～2026年11月30日が契約日となる契約</p>'
CUR={"USD":"米ドル","AUD":"豪ドル","JPY":"円"}

def table(heading,rows):
    return '<h3>'+heading+'</h3><table><tr><th>契約年齢</th><th>積立利率</th></tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'

def present_html():
    death=[]
    for currency,ages in [("USD",[(20,80,"30年"),(81,90,"10年")]),
                          ("AUD",[(20,85,"20年"),(86,90,"10年")]),
                          ("JPY",[(20,80,"30年"),(81,90,"15年")])]:
        for lo,hi,term in ages:
            for suppress in ("9ヵ月","5年"):
                # The guarantee term appears only at the first new age-band row.
                cells=[CUR[currency],f"{lo}歳～{hi}歳",term,suppress,"2.53%"] if suppress=="9ヵ月" else [suppress,"2.53%"]
                death.append(cells)
    care=[]
    for curr,ages in [("USD",[(40,80,"30年"),(81,85,"10年")]),
                      ("AUD",[(40,85,"20年")]),
                      ("JPY",[(40,80,"30年"),(81,85,"15年")])]:
        for lo,hi,term in ages:
            care.append([CUR[curr],f"{lo}歳～{hi}歳",term,"2.31%"])
    return ('<h1>積立利率変動型終身保険（20）（通貨指定型）</h1>'+DATES+
            table("死亡保障プラン",death)+table("認知症・介護プラン(告知あり)",care)+
            table("認知症・介護プラン(告知なし)",care))

def receive_html():
    def rate_table(label):
        rows=[]
        for cur in ("USD","AUD","JPY"):
            for lo,hi in [(0,65),(66,75),(76,80),(81,85),(86,90)]:
                rows.append([CUR[cur],f"{lo}～{hi}歳","4.25%","4.12%","4.05%"])
        return '<h3>'+label+'</h3><table><tr><th>積立利率</th></tr><tr><th>男女別定期支払率</th></tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
    return ('<h1>定期支払金付積立利率変動型終身保険（23）（通貨指定型）</h1>'+
            DATES+rate_table("基本プラン")+rate_table("指数プラン"))

class OfficialDflAdapterTests(unittest.TestCase):
    def test_present_22_conditions(self):
        results=extract(present_html().encode(),"present",DAY)
        self.assertEqual(len(results["records"]),22)
        self.assertTrue(all(r["payout"] is None for r in results["records"]))
    def test_receive_30_payout_pairs(self):
        results=extract(receive_html().encode(),"receive",DAY)
        self.assertEqual(len(results["records"]),30)
        self.assertTrue(all(r["payout"]=={"male":4.12,"female":4.05} for r in results["records"]))
    def test_missing_present_plan_blocked(self):
        text=present_html().replace("認知症・介護プラン(告知なし)","不存在")
        with self.assertRaisesRegex(ValueError,"tables missing"):
            extract(text.encode(),"present",DAY)
    def test_invalid_percentage_blocked(self):
        with self.assertRaisesRegex(ValueError,"nonnumeric percent"):
            extract(receive_html().replace("4.25%","-").encode(),"receive",DAY)
    def test_old_date_blocked(self):
        with self.assertRaisesRegex(ValueError,"period"):
            extract(receive_html().replace("11月16日～2026年11月30日","11月1日～2026年11月15日").encode(),"receive",DAY)
    def test_missing_payout_blocked(self):
        with self.assertRaisesRegex(ValueError,"two payout rates"):
            extract(receive_html().replace("<td>4.05%</td>","").encode(),"receive",DAY)
if __name__=="__main__":
    unittest.main()
