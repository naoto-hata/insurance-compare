import unittest
from inventory_embedded_assets import inventory

class EmbeddedAssetInventoryTests(unittest.TestCase):
    def test_flags_hidden_internal_content_without_exposing_payload(self):
        html=('<html><iframe id="agentdocs" title="募集人用資料" hidden '
              'srcdoc="&lt;p&gt;CUSTOMER_SECRET_TOKEN&lt;/p&gt;'
              '&lt;img src=&quot;data:image/png;base64,QUJD&quot;&gt;">'
              '</iframe></html>')
        report=inventory(html)
        self.assertTrue(report["privileged_section_detected"])
        self.assertFalse(report["publication_allowed"])
        self.assertEqual(report["iframe_total"],1)
        self.assertEqual(report["iframe_inline_content"],1)
        self.assertEqual(report["embedded_mime_type_counts"].get("image/png"),1)
        self.assertNotIn("CUSTOMER_SECRET_TOKEN",str(report))
        self.assertNotIn("QUJD",str(report))
    def test_non_internal_frame_not_marked_approved(self):
        report=inventory('<iframe id="single" srcdoc="&lt;p&gt;hello&lt;/p&gt;"></iframe>')
        self.assertFalse(report["privileged_section_detected"])
        self.assertFalse(report["publication_allowed"])
    def test_never_includes_phone_or_email(self):
        report=inventory('<iframe id="agentdocs" srcdoc="a@internal.example 090-1234-5678"></iframe>')
        self.assertNotIn("internal.example",str(report))
        self.assertNotIn("090-",str(report))
if __name__=="__main__":
    unittest.main()
