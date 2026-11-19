import unittest
from security_gate import inspect

class PublicExportSecurityTests(unittest.TestCase):
    def test_agent_document_iframe_blocks_export(self):
        page='<iframe id="agentdocs" srcdoc="&lt;p&gt;internal&lt;/p&gt;"></iframe>'
        result=inspect(page)
        self.assertFalse(result["publication_allowed"])
        self.assertIn("PRIVATE_SECTION_EMBEDDED",result["finding_codes"])
    def test_hidden_section_still_blocks_export(self):
        result=inspect('<iframe id="agentdocs" hidden srcdoc="private"></iframe>')
        self.assertIn("PRIVATE_SECTION_EMBEDDED",result["finding_codes"])
    def test_internal_material_marker_blocks_export(self):
        result=inspect('<p>募集人用資料</p>')
        self.assertIn("INTERNAL_DOCUMENT_MARKER_PRESENT",result["finding_codes"])
    def test_embedded_pdf_binary_blocks_export(self):
        result=inspect('<div>data:application/pdf;base64,AAAA</div>')
        self.assertIn("EMBEDDED_DOCUMENT_BINARY_UNREVIEWED",result["finding_codes"])
    def test_images_not_assumed_public(self):
        result=inspect('<img src="data:image/png;base64,AAAA">')
        self.assertIn("EMBEDDED_IMAGE_REQUIRES_CONTENT_REVIEW",result["finding_codes"])
    def test_no_false_all_clear_without_allowlist(self):
        result=inspect('<h1>公開文書</h1>')
        self.assertFalse(result["publication_allowed"])
        self.assertIn("NO_PUBLIC_CONTENT_ALLOWLIST_APPROVAL",result["finding_codes"])

if __name__=="__main__":
    unittest.main()
