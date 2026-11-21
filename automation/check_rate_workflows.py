#!/usr/bin/env python3
"""Policy checks for GitHub Actions workflows touching sensitive app sources.

Fail closed on artifact uploads, auto-deploy, or repo write permissions in
rate review/monitoring workflows. Do not treat a clean scan as approval to
publish to GitHub Pages or to distribute source data externally.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github/workflows/rate-tests.yml",
    ROOT / ".github/workflows/half-monthly-rates.yml",
)
BANNED = {
    "artifact_upload": re.compile(r"uses:\s*actions/upload-artifact@", re.I),
    "pages_deploy": re.compile(r"uses:\s*actions/deploy-pages@", re.I),
    "pages_publish": re.compile(r"uses:\s*peaceiris/actions-gh-pages@", re.I),
    "repository_write": re.compile(r"(?m)^\s*contents:\s*write\s*$", re.I),
    "unreviewed_github_push": re.compile(r"(?m)^\s*(?:git push|git add\s+.*v117)", re.I),
    "full_app_preview_runner": re.compile(r"(?m)^\s*run:\s*python\s+automation/(?:smoke_preview|smoke_live_preview|prepare_review_preview)\.py\s*$"),
}

def evaluate(files=WORKFLOWS):
    findings=[]
    for file in files:
        text=pathlib.Path(file).read_text(encoding="utf-8")
        for label,pattern in BANNED.items():
            if pattern.search(text):
                findings.append((pathlib.Path(file).name,label))
    return findings

if __name__=="__main__":
    problems=evaluate()
    if problems:
        print("RATE WORKFLOW PRIVACY POLICY FAILED:",problems)
        raise SystemExit(1)
    print("PASS: Rate automation workflows cannot upload artifacts, deploy Pages or write to repo.")
