// Test the actual public page JavaScript across each published period boundary.
// No network, credentials, old v117 binary fragments, or artifact output.
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const path=require("node:path");
const html=fs.readFileSync(path.join(__dirname,"..","rates-current.html"),"utf8");
const index=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length,1);
assert.equal((html.match(/<tr><td>/g)||[]).length,54);
assert.match(html,/id="rate-table" hidden style="display:none"/);
const begin=html.match(/const begins='(20\d{2}-\d{2}-\d{2})';/);
const end=html.match(/const expires='(20\d{2}-\d{2}-\d{2})';/);
assert.ok(begin && end);
const atJstMidnight=day=>Date.parse(day+"T00:00:00+09:00");
const dt=ms=>new Date(ms).toISOString();
function simulate(instant){
  const table={hidden:true,style:{display:"none"}};
  const notice={style:{display:"none"}};
  const document={
    title:"利率一覧",
    getElementById(id){
      if(id==="rate-table")return table;
      if(id==="rate-expired")return notice;
      throw Error("Unexpected document lookup");
    }
  };
  const millis=Date.parse(instant);
  class FixedDate extends Date {
    constructor(...args){super(...(args.length?args:[millis]));}
    static now(){return millis;}
  }
  vm.runInNewContext(scripts[0][1],{Date:FixedDate,Intl,document},{timeout:1000});
  return {table,notice};
}
let p=simulate(dt(atJstMidnight(begin[1])-60_000));
assert.equal(p.table.hidden,true);
p=simulate(dt(atJstMidnight(begin[1])));
assert.equal(p.table.hidden,false);
assert.equal(p.table.style.display,"block");
const oneDayAfterEnd=atJstMidnight(end[1])+86_400_000;
p=simulate(dt(oneDayAfterEnd-60_000));
assert.equal(p.table.hidden,false);
p=simulate(dt(oneDayAfterEnd));
assert.equal(p.table.hidden,true);
assert.equal(p.table.style.display,"none");
assert.equal(p.notice.style.display,"block");
assert.match(index,/公式利率の自動更新一覧（3商品）/);
assert.match(index,/rates-current\.html/);
console.log("PASS: JST start/end boundaries, default-hidden expiry, evergreen v117 link.");
