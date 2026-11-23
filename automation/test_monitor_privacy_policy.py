"""Prevent accidental leakage of HTTP exception payloads in rate source reports."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
MONITOR=ROOT/"scripts/monitor_rates.py"
WORKFLOW=ROOT/".github/workflows/rate-monitor.yml"

class OfficialRateMonitoringPrivacyTests(unittest.TestCase):
    def test_raw_exception_messages_not_published(self):
        script=MONITOR.read_text(encoding="utf-8")
        self.assertNotIn('"error": str(exc)',script)
        self.assertNotIn('"error": repr(exc)',script)
        self.assertIn('"error_category": safe_type',script)
        self.assertIn("OtherAccessError",script)
    def test_report_artifact_has_only_monitoring_metadata(self):
        source=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("rate-monitor-report.md",source)
        self.assertIn("rate-monitor-report.json",source)
        for risky in ("v117/","rate-data-private","*.pdf","*.xlsx","source-audit.json"):
            self.assertNotIn(risky,source)

if __name__=="__main__":
    unittest.main()
