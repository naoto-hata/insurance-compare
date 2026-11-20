// Runtime test for the v117 *public rate-only page* (not the mixed-source app).
// No browser network, local files other than the published HTML, or uploads.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "..", "rates-current.html"), "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length, 1, "Public rate-only page must contain exactly one runtime script");
assert.equal((html.match(/<tr><td>/g) || []).length, 54);

function inspectAt(isoUtc) {
  const expired = { style: { display: "none" }, hidden: false };
  const table = { style: { display: "none" }, hidden: true };
  const document = {
    title: "第117版｜公式確認済み一時払利率",
    getElementById(id) {
      if (id === "rate-expired") return expired;
      if (id === "rate-table") return table;
      throw Error("Unexpected DOM access: " + id);
    },
  };
  const fixed = new Date(isoUtc);
  class FixedDate extends Date {
    constructor(...args) {
      super(...(args.length ? args : [fixed.getTime()]));
    }
    static now() { return fixed.getTime(); }
  }
  const sandbox = { Date: FixedDate, document, Intl };
  vm.runInNewContext(scripts[0][1], sandbox, { timeout: 1000 });
  return { expired, table, title: document.title };
}

// 2026-11-15 23:59 JST (not effective yet).
let early = inspectAt("2026-11-15T14:59:00Z");
assert.equal(early.table.hidden, true, "Future rates visible before beginning of period");

// 2026-11-16 00:00 JST (period begins).
let opening = inspectAt("2026-11-15T15:00:00Z");
assert.equal(opening.table.hidden, false, "Rates not visible on first effective minute");

// 2026-11-30 23:59 JST (still in period).
let result = inspectAt("2026-11-30T14:59:00Z");
assert.equal(result.table.hidden, false, "Rate table not released during valid period");
assert.equal(result.table.style.display, "block");
assert.equal(result.expired.style.display, "none");

// 2026-12-01 00:00 JST (one minute later).
result = inspectAt("2026-11-30T15:00:00Z");
assert.equal(result.table.hidden, true, "Old rates still presented as current");
assert.equal(result.table.style.display, "none");
assert.equal(result.expired.style.display, "block");
assert.match(result.title, /適用期間終了/);

// A computer in another timezone must still obey Japan time.
result = inspectAt("2026-12-02T12:00:00Z");
assert.equal(result.table.hidden, true);
console.log("PASS: JST date boundary reveals rates only while valid; expired/default state is hidden.");


const entry = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const linkStart = entry.indexOf("const rateLink=document.createElement('a');");
const linkEnd = entry.indexOf("document.body.appendChild(rateLink)", linkStart);
assert.ok(linkStart >= 0 && linkEnd > linkStart, "V117 rate link script missing");
const linkCode = entry.slice(linkStart, linkEnd + "document.body.appendChild(rateLink)".length);
function inspectLinkAt(isoUtc) {
  const date = new Date(isoUtc);
  let inserted;
  const doc = {
    createElement(tag) { assert.equal(tag, "a"); return { setAttribute() {}, style: {} }; },
    body: { appendChild(element) { inserted=element; } },
  };
  class DateAt extends Date {
    constructor(...args) { super(...(args.length ? args : [date.getTime()])); }
    static now() { return date.getTime(); }
  }
  vm.runInNewContext(linkCode, { document: doc, Date: DateAt, Intl }, { timeout: 1000 });
  return inserted;
}
assert.match(inspectLinkAt("2026-11-30T14:59:00Z").textContent, /公式確認済み利率/);
assert.match(inspectLinkAt("2026-11-30T15:00:00Z").textContent, /利率の確認待ち/);
assert.equal(inspectLinkAt("2026-11-30T15:00:00Z").href, "./rates-current.html");
console.log("PASS: V117 home-page link switches to confirmation-pending at Japanese midnight.");
