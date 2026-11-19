import pathlib
import tempfile
import unittest
from check_public_package import check_package

REVIEW='''<!doctype html><html lang="ja"><head><meta charset="utf-8"></head><body>
<p>publication_allowed: false</p><table>'''+''.join('<tr><td>2.00%</td></tr>' for _ in range(54))+'''</table></body></html>'''

class PackageGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        (self.root/"index.html").write_text(REVIEW,encoding="utf-8")
    def test_review_only_page_is_structurally_valid_not_approved(self):
        result=check_package(self.root)
        self.assertEqual(result["status"],"STRUCTURALLY_SAFE_NOT_APPROVED")
        self.assertFalse(result["publication_allowed"])
    def test_old_app_fragments_blocked(self):
        folder=self.root/"v117"
        folder.mkdir()
        (folder/"part000.js").write_text("window.__insuranceV117=[];")
        with self.assertRaisesRegex(ValueError,"Non-allowlisted"):
            check_package(self.root)
    def test_embedded_pdf_blocked(self):
        (self.root/"internal.pdf").write_bytes(b"%PDF-1.7")
        with self.assertRaises(ValueError):check_package(self.root)
    def test_hidden_agentdocs_in_public_html_blocked(self):
        (self.root/"index.html").write_text(REVIEW+"<iframe id='agentdocs'></iframe>")
        with self.assertRaises(ValueError):check_package(self.root)
    def test_nested_json_private_information_blocked(self):
        (self.root/"customer.json").write_text('{"name":"customer"}')
        with self.assertRaises(ValueError):check_package(self.root)
    def test_symlink_blocked(self):
        target=self.root/"secret.txt"
        target.write_text("test")
        (self.root/"link.txt").symlink_to(target)
        with self.assertRaises(ValueError):check_package(self.root)
if __name__=="__main__":
    unittest.main()
