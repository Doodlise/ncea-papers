/* Behavioural smoke test for the picker (needs jsdom; REQUIRE_UI=1 makes it fatal).
 * Run: REQUIRE_UI=1 node verify_ui.js   (after npm ci)
 */
const fs = require("fs");
const path = require("path");

let JSDOM;
try {
  JSDOM = require("jsdom").JSDOM;
} catch (e) {
  console.log("SKIP jsdom not installed — UI smoke test skipped");
  process.exit(process.env.REQUIRE_UI === "1" ? 1 : 0);
}

const dir = __dirname;
const html = fs.readFileSync(path.join(dir, "index.html"), "utf8");
const dataJs = fs.readFileSync(path.join(dir, "data.js"), "utf8");
const appJs = fs.readFileSync(path.join(dir, "app.js"), "utf8");

function boot(url, seed) {
  const dom = new JSDOM(html, { url, runScripts: "outside-only" });
  const w = dom.window;
  if (seed) w.localStorage.setItem("ncea-papers-last", JSON.stringify(seed));
  w.eval(dataJs);
  w.eval(appJs);
  return w;
}

let failures = 0;
function check(ok, name) {
  console.log((ok ? "  ok   " : "  FAIL ") + name);
  if (!ok) failures++;
}

let w = boot("http://localhost/#91174");
check(/Standard 91174/.test(w.document.getElementById("hint").textContent), "cold deep link restores standard");

w = boot("http://localhost/", { key: "91123" });
check(/Standard 91123/.test(w.document.getElementById("hint").textContent), "cold localStorage recall works");

w = new JSDOM(html, { url: "http://localhost/", runScripts: "outside-only" }).window;
w.localStorage.setItem("ncea-papers-last", "0");
w.eval(dataJs);
w.eval(appJs);
check(w.localStorage.getItem("ncea-papers-last") === null, "falsy corrupt saved state self-heals");

w = boot("http://localhost/#99999", { key: "91123" });
check(/No papers listed for 99999/.test(w.document.getElementById("hint").textContent), "invalid hash gives a clear hint");
check(w.localStorage.getItem("ncea-papers-last") === null, "invalid hash clears saved selection");
check(!w.location.hash, "invalid hash stripped from URL");

w = boot("http://localhost/#picker", { key: "91123" });
check(w.localStorage.getItem("ncea-papers-last") === null, "#picker cold load clears saved selection");

w = boot("http://localhost/");
let d = w.document;
d.getElementById("jump").value = "91174";
d.getElementById("jump-go").click();
check(/Standard 91174/.test(d.getElementById("hint").textContent), "jump selects standard");
w.location.hash = "#99999";
w.dispatchEvent(new w.Event("hashchange"));
check(d.querySelectorAll("#files a").length === 0, "invalid hash clears results");
w.location.hash = "#91174";
w.dispatchEvent(new w.Event("hashchange"));
check(/Standard 91174/.test(d.getElementById("hint").textContent), "valid hash recovers after typo");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "2025 91404";
d.getElementById("jump-go").click();
check(/Standard 91404/.test(d.getElementById("hint").textContent), "prose jump ignores year token");
const before = w.history.length;
d.getElementById("jump").value = "91404";
d.getElementById("jump-go").click();
check(w.history.length === before, "repeated jump does not pollute history");

w = boot("http://localhost/#%ZZ91174", { key: "91123" });
check(/invalid standard number/.test(w.document.getElementById("hint").textContent), "malformed hash gives feedback");
check(!w.location.hash, "malformed hash stripped from URL");

w = boot("http://localhost/");
d = w.document;
d.getElementById("level").value = "2";
d.getElementById("level").dispatchEvent(new w.Event("change"));
w.location.hash = "#picker";
w.dispatchEvent(new w.Event("hashchange"));
check(d.getElementById("level").value === "", "#picker mid-session resets level");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "091174";
d.getElementById("jump-go").click();
check(/Standard 91174/.test(d.getElementById("hint").textContent), "leading-zero jump resolves");

w = boot("http://localhost/#+91174");
check(/invalid standard number/.test(w.document.getElementById("hint").textContent), "signed hash rejected");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "2025 99999";
d.getElementById("jump-go").click();
check(/99999/.test(d.getElementById("hint").textContent), "invalid multi-token jump names the right token");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "2025 999";
d.getElementById("jump-go").click();
check(/999/.test(d.getElementById("hint").textContent), "short-digit jump echoes the short token");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "9".repeat(5000);
d.getElementById("jump-go").click();
const echoed = d.getElementById("hint").textContent;
check(echoed.length < 60 && echoed.includes("…"), "long invalid token is capped in the hint");

w = boot("http://localhost/#000091404");
check(/Standard 91404/.test(w.document.getElementById("hint").textContent),
      "leading-zero deep link is normalized");

w = boot("http://localhost/");
d = w.document;
d.getElementById("jump").value = "91174";
d.getElementById("jump-go").click();
w.location.hash = "#picker";
w.dispatchEvent(new w.Event("hashchange"));
check(d.getElementById("hint").textContent === "Start here — pick your level above.", "native #picker navigation resets picker");

async function finish() {
  // Full picker/static-page parity sweep across every standard, driven only
  // via the jump control (deterministic in jsdom), comparing labels AND hrefs
  // with entities decoded via the DOM.
  const pw = boot("http://localhost/");
  const pd = pw.document;
  const payload = JSON.parse(dataJs.replace(/^window\.NCEA_DATA\s*=\s*/, "").replace(/;\s*$/, ""));
  const numbers = [...new Set(payload.subjects.flatMap(s =>
    ["1", "2", "3"].flatMap(l => s.levels[l].standards.map(std => std.number))))];
  const allPath = path.join(dir, "all.html");
  if (!fs.existsSync(allPath)) {
    console.log("FAIL all.html missing — run build.py first");
    process.exit(1);
  }
  const allHtml = fs.readFileSync(allPath, "utf8");
  const staticDoc = new JSDOM(allHtml).window.document;
  const staticMap = new Map();
  for (const h4 of staticDoc.querySelectorAll("h4")) {
    const m = h4.textContent.match(/^(\d{5}) —/);
    if (!m) continue;
    const labels = [], hrefs = [];
    let node = h4.nextElementSibling;
    while (node && node.tagName !== "H4") {
      node.querySelectorAll('a[class^="pdf-"]').forEach(a => {
        labels.push(a.textContent);
        hrefs.push(a.getAttribute("href"));
      });
      node = node.nextElementSibling;
    }
    staticMap.set(m[1], { labels, hrefs });
  }
  let parityBad = [];
  for (const num of numbers) {
    pd.getElementById("jump").value = num;
    pd.getElementById("jump-go").click();
    const anchors = [...pd.querySelectorAll("#files tbody a")];
    const expected = staticMap.get(num) || { labels: [], hrefs: [] };
    const actual = {
      labels: anchors.map(a => a.textContent),
      hrefs: anchors.map(a => a.getAttribute("href")),
    };
    if (!actual.labels.length || actual.labels.join("|") !== expected.labels.join("|")
        || actual.hrefs.join("|") !== expected.hrefs.join("|")) parityBad.push(num);
  }
  check(parityBad.length === 0,
        `picker/static labels and URLs match for all ${numbers.length} standards (bad: ${parityBad.slice(0, 5)})`);

  const bw = boot("http://localhost/");
  const bd = bw.document;
  bd.getElementById("jump").value = "91174";
  bd.getElementById("jump-go").click();
  bw.history.back();
  await new Promise(resolve => setTimeout(resolve, 200));
  check(/Start here/.test(bd.getElementById("hint").textContent)
        && bd.getElementById("level").value === ""
        && bd.getElementById("subject").value === ""
        && bd.getElementById("external").value === ""
        && bd.querySelectorAll("#files a").length === 0,
        "popstate/back fully resets the picker");

  console.log(failures ? `\nUI smoke test FAILED: ${failures}` : "\nUI smoke test PASSED");
  process.exit(failures ? 1 : 0);
}

finish().catch(function (err) {
  console.log("FAIL UI smoke test crashed: " + (err && err.message ? err.message : err));
  process.exit(1);
});
