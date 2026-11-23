"""Enforce publication boundaries of unattended rate automations.
No source HTML, customer data, private worksheets, or downloadable assets
may be staged by the GitHub Actions public-rate updater.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
AUTO=ROOT/".github/workflows/v117-auto-rates.yml"
GUARD=ROOT/".github/workflows/v117-public-guard.yml"

class V117WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.auto=AUTO.read_text(encoding="utf-8")
        self.guard=GUARD.read_text(encoding="utf-8")
    def test_only_one_whitelisted_file_is_committed(self):
        self.assertIn("git add -- rates-current.html",self.auto)
        self.assertIn('"$(git diff --cached --name-only)" != "rates-current.html"',self.auto)
        self.assertIn('git status --porcelain --untracked-files=no -- index.html v117',self.auto)
        for risky in ("git add .","git add -A","git add v117","actions/upload-artifact@",
                      "actions/deploy-pages@","gh-pages","git push --force"):
            self.assertNotIn(risky,self.auto)
    def test_publication_is_preceded_by_source_and_privacy_checks(self):
        checks=[
            "py_compile automation/update_verified_rates.py",
            "test_update_verified_rates.py",
            "AUTO_RATE_DRY_RUN: '1'",
            "python automation/update_verified_rates.py",
            "python automation/verify_v117_public.py",
            "node automation/test_v117_expiry.cjs",
            "git add -- rates-current.html",
        ]
        positions=[self.auto.find(t) for t in checks]
        self.assertTrue(all(x>=0 for x in positions),positions)
        self.assertLess(positions[0],positions[2])
        self.assertLess(positions[2],positions[3])
        self.assertLess(positions[3],positions[6])
        self.assertIn("issues: write",self.auto)
    def test_public_check_only_reads_site(self):
        self.assertIn("contents: read",self.guard)
        for risky in ("contents: write","git push","actions/upload-artifact@","deploy-pages@"):
            self.assertNotIn(risky,self.guard)
    def test_failure_notification_has_no_raw_source_evidence(self):
        self.assertIn("if: failure()",self.auto)
        self.assertIn("gh issue create",self.auto)
        self.assertIn("gh issue edit",self.auto)
        self.assertIn("gh issue close",self.auto)
        self.assertNotIn("rate-monitor-report.json",self.auto)
        self.assertNotIn("source-audit.json",self.auto)

if __name__=="__main__":
    unittest.main()
