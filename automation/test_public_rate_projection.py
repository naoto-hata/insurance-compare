import unittest
from public_rate_projection import project, PUBLIC_ROW_FIELDS

class PublicProjectionTests(unittest.TestCase):
    def setUp(self):
        self.rows=[]
        for pid,count in (("present",22),("receive",30),("moon",2)):
            for i in range(count):
                self.rows.append({"product_id":pid,"currency":"JPY","label":f"プラン{i}",
                  "term":"10年","lo":20,"hi":90,"value":2.0,
                  "period":"2026-11-16～2026-11-30","payout":None,
                  "source_url":"https://private.example/agency-id",
                  "source_sha256":"secret-token",
                  "source_locator":"not public",
                  "extra":"募集人用資料・内部ノート",
                  "customer_name":"お客様の氏名"})
        self.stage={"release_stage":"VALIDATED_NOT_PUBLISHED",
          "source_products":["present","receive","moon"],
          "period":"2026-11-16～2026-11-30","records":self.rows}
    def test_strict_allowlist_excludes_all_extra_fields(self):
        result=project(self.stage)
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(len(result["records"]),54)
        self.assertTrue(all(set(r)==PUBLIC_ROW_FIELDS for r in result["records"]))
        text=str(result)
        for prohibited in ("customer_name","source_url","source_sha256","source_locator","募集人用資料"):
            self.assertNotIn(prohibited,text)
    def test_missing_product_blocked(self):
        stage={**self.stage,"records":self.rows[:-1]}
        with self.assertRaises(ValueError):project(stage)
    def test_unknown_product_blocked(self):
        self.rows[0]["product_id"]="unknown"
        with self.assertRaises(ValueError):project(self.stage)
    def test_wrong_stage_blocked(self):
        with self.assertRaises(ValueError):project({**self.stage,"release_stage":"UNVERIFIED"})
if __name__=="__main__":
    unittest.main()
