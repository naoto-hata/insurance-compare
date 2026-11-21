#!/usr/bin/env python3
"""Read-only diagnostics of the official Daiichi Frontier tables; no rate publication."""
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from urllib.parse import urlsplit
import re
URLS={
"present":"https://www.d-frontier-life.co.jp/products/index_hendo_shushin_choice_20_6.html?agency=227&product=224",
"receive":"https://www.d-frontier-life.co.jp/products/index_recurrining_payment_shushin_23.html?agency=132&product=204"
}
class Tables(HTMLParser):
 def __init__(self):
  super().__init__();self.table=None;self.row=None;self.cell=None;self.tables=[];self.headings=[];self.h=None
 def handle_starttag(self,t,a):
  if t in ("h1","h2","h3","h4"):self.h=[]
  if t=="table":self.table={"heading":self.headings[-1] if self.headings else "","rows":[]}
  if t=="tr" and self.table is not None:self.row=[]
  if t in ("td","th") and self.row is not None:
   attrs=dict(a);self.cell={"txt":[],"rowspan":attrs.get("rowspan","1"),"colspan":attrs.get("colspan","1")}
 def handle_data(self,s):
  if self.h is not None:self.h.append(s)
  if self.cell is not None:self.cell["txt"].append(s)
 def handle_endtag(self,t):
  if t in ("h1","h2","h3","h4") and self.h is not None:self.headings.append(re.sub(r"\\s+","", "".join(self.h)));self.h=None
  if t in ("td","th") and self.cell is not None:self.cell["txt"]=re.sub(r"\\s+","", "".join(self.cell["txt"]));self.row.append(self.cell);self.cell=None
  if t=="tr" and self.row is not None:self.table["rows"].append(self.row);self.row=None
  if t=="table" and self.table is not None:self.tables.append(self.table);self.table=None
for product,url in URLS.items():
 try:
  with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=25) as res:raw=res.read(1500000)
  p=Tables();p.feed(raw.decode("utf-8","replace"))
  print("PRODUCT",product,"tables",len(p.tables),"headings",p.headings[-12:])
  for t in p.tables:
   print("TABLE",t["heading"],"rows",len(t["rows"]))
   for row in t["rows"][:7]:
    print(" ",[(c["txt"][:60],c["rowspan"],c["colspan"]) for c in row])
 except Exception as e:print("FAILED",product,str(e))
