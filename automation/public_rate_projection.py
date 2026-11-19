#!/usr/bin/env python3
"""Allowlist-only projection of staged insurer rates for a future public UI.

This output contains no HTML, images, documents, customer details, agency
contact information, internal notes, proprietary source snippets, or website
credentials. Publication remains disabled pending policy and rendering review.
"""
import json
from collections import Counter

NAMES={
 "present":("第一フロンティア生命","プレミアプレゼント5"),
 "receive":("第一フロンティア生命","プレミアレシーブ2"),
 "moon":("オリックス生命","Moonshot（ムーンショット）"),
}
ALLOWED_FIELDS=("product_id","currency","label","term","lo","hi","value","period","payout")
PUBLIC_ROW_FIELDS=set(ALLOWED_FIELDS)|{"company","product"}
EXPECTED={"present":22,"receive":30,"moon":2}

def project(staged):
    if staged.get("release_stage")!="VALIDATED_NOT_PUBLISHED":
        raise ValueError("Only independently staged source rows may be projected")
    if set(staged.get("source_products",[]))!=set(EXPECTED):
        raise ValueError("Unreviewed products or partial product set")
    if len(staged.get("records",[]))!=sum(EXPECTED.values()):
        raise ValueError("Incomplete official rate inventory")
    records=[]
    for r in staged["records"]:
        pid=r["product_id"]
        if pid not in NAMES or set(ALLOWED_FIELDS)-set(r):
            raise ValueError("Unrecognized product or missing public rate field")
        if r["period"]!=staged.get("period"):
            raise ValueError("Mixed period")
        row={k:r[k] for k in ALLOWED_FIELDS}
        row["company"],row["product"]=NAMES[pid]
        if set(row)!=PUBLIC_ROW_FIELDS:
            raise ValueError("Leaked unexpected field in public projection")
        records.append(row)
    if dict(Counter(x["product_id"] for x in records))!=EXPECTED:
        raise ValueError("Incomplete or duplicated product inventory")
    return {
        "schema_version":1,
        "data_classification":"PUBLIC_CANDIDATE_UNREVIEWED",
        "publication_allowed":False,
        "effective_period":staged["period"],
        "records":records,
    }
