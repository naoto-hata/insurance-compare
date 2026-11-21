import pathlib
import tempfile
import unittest
from check_rate_workflows import evaluate

class RateWorkflowSecurityTests(unittest.TestCase):
    def test_current_workflows_are_read_only_no_artifacts(self):
        self.assertEqual(evaluate(),[])
    def test_detects_upload_of_sensitive_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"bad.yml"
            path.write_text("steps:\n  - uses: actions/upload-artifact@v4\n",encoding="utf-8")
            self.assertIn(("bad.yml","artifact_upload"),evaluate([path]))
    def test_detects_write_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"bad.yml"
            path.write_text("permissions:\n  contents: write\n",encoding="utf-8")
            self.assertIn(("bad.yml","repository_write"),evaluate([path]))
    def test_detects_sensitive_legacy_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"bad.yml"
            path.write_text("  run: python automation/smoke_live_preview.py\n",encoding="utf-8")
            self.assertIn(("bad.yml","full_app_preview_runner"),evaluate([path]))
if __name__=="__main__":
    unittest.main()
