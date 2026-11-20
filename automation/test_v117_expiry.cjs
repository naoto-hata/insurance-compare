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
  const table = { style: { display: "" }, hidden: false };
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

// 2026-11-30 23:59 JST (still in period).
let result = inspectAt("2026-11-30T14:59:00Z");
assert.equal(result.table.hidden, false, "Rate table hidden before the last valid minute");
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
console.log("PASS: JST date boundary hides expired v117 rate rows at 2026-12-01 00:00 JST.");
