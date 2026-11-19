/* Plain JS: Level -> Subject -> External -> all PDFs for that external. */
(function () {
  "use strict";

  if (!window.NCEA_DATA || !window.NCEA_DATA.subjects) {
    document.getElementById("hint").textContent =
      "The local data file did not load. Open all.html instead, or re-run build.py.";
    return;
  }
  var data = window.NCEA_DATA;
  var levelEl = document.getElementById("level");
  var subjectEl = document.getElementById("subject");
  var externalEl = document.getElementById("external");
  var hintEl = document.getElementById("hint");
  var filesEl = document.getElementById("files");
  var generatedEl = document.getElementById("generated");
  if (generatedEl && data.generated) {
    generatedEl.textContent = "List last checked " + data.generated + ". ";
  }
  var jumpEl = document.getElementById("jump");
  var jumpGo = document.getElementById("jump-go");

  function isPdfUrl(url) {
    try {
      var u = new URL(url, "https://www.nzqa.govt.nz/");
      return u.protocol === "https:"
        && (u.hostname === "www.nzqa.govt.nz" || u.hostname === "www2.nzqa.govt.nz")
        && u.pathname.toLowerCase().endsWith(".pdf");
    } catch (e) { return false; }
  }

  var lastHash = "";
  var navPush = false;
  var numberIndex = Object.create(null);
  data.subjects.forEach(function (s) {
    ["1", "2", "3"].forEach(function (lvl) {
      (((s.levels || {})[lvl] || {}).standards || []).forEach(function (std) {
        if (!numberIndex[std.number]) {
          numberIndex[std.number] = { slug: s.slug, lvl: lvl };
        }
      });
    });
  });

  function selectStandard(num, push) {
    var found = numberIndex[num];
    if (!found) {
      clearSaved();
      hintEl.textContent = "No papers listed for " + num + ". Check the number.";
      filesEl.innerHTML = "";
      return;
    }
    navPush = !!push;
    levelEl.value = found.lvl;
    onLevelChange(true);
    subjectEl.value = found.slug;
    onSubjectChange(true);
    externalEl.value = num;
    showFiles();
    navPush = false;
    if (jumpEl) jumpEl.select();
  }

  function decodeHash() {
    var raw = String(location.hash || "").replace(/^#/, "");
    var num = "";
    var bad = false;
    try { num = decodeURIComponent(raw).trim(); } catch (e) { bad = true; }
    if (!bad && /^\d+$/.test(num) && num.length > 5) {
      var trimmed = String(Number(num));
      if (/^\d{4,5}$/.test(trimmed)) num = trimmed;
    }
    if (raw && !bad && num.toLowerCase() !== "picker"
        && (!/^\d{4,5}$/.test(num) || /^0{4,5}$/.test(num))) bad = true;
    return { raw: raw, num: num, bad: bad };
  }

  function fromLocation() {
    var parsed = decodeHash();
    var num = parsed.num;
    if (!parsed.bad && /^\d+$/.test(parsed.raw) && parsed.raw !== num) {
      try { history.replaceState(null, "", "#" + num); } catch (e) {}
    }
    if (parsed.bad && parsed.raw) {
      clearSaved();
      levelEl.value = "";
      onLevelChange(true);
      hintEl.textContent = "That link has an invalid standard number. Check the number.";
      return;
    }
    if (num === lastHash) return;
    if (!num || num.toLowerCase() === "picker") {
      lastHash = "";
      clearSaved();
      levelEl.value = "";
      onLevelChange(true);
      return;
    }
    if (!numberIndex[num]) {
      clearSaved();
      levelEl.value = "";
      onLevelChange(true);
      filesEl.innerHTML = "";
      hintEl.textContent = "No papers listed for " + num + ". Check the number.";
      return;
    }
    if (externalEl.value !== num) selectStandard(num);
  }
  window.addEventListener("hashchange", fromLocation);
  window.addEventListener("popstate", fromLocation);

  function doJump() {
    var rawInput = String(jumpEl.value || "");
    var runs = rawInput.match(/\d+/g) || [];
    var num = "";
    for (var i = 0; i < runs.length; i++) {
      if (numberIndex[runs[i]]) { num = runs[i]; break; }
    }
    if (!num) {
      var digits = rawInput.replace(/\D/g, "");
      for (var len = 5; len >= 4 && !num; len--) {
        var candidate = digits.slice(-len);
        if (numberIndex[candidate]) num = candidate;
        else if (numberIndex[String(Number(candidate))]) num = String(Number(candidate));
      }
    }
    if (!num) {
      clearSaved();
      levelEl.value = "";
      onLevelChange(true);
      var candidates = runs.filter(function (r) { return !/^(19|20)\d{2}$/.test(r); });
      var typed = candidates.length ? candidates[candidates.length - 1]
        : (runs.length ? runs[runs.length - 1] : rawInput.replace(/\D/g, ""));
      if (/^(19|20)\d{2}$/.test(typed) || typed.length < 3) typed = "";
      if (typed.length > 12) typed = typed.slice(0, 12) + "…";
      hintEl.textContent = typed
        ? "No papers listed for " + typed + ". Check the number."
        : "Enter a standard number to jump straight to its papers.";
      filesEl.innerHTML = "";
      return;
    }
    selectStandard(num, externalEl.value !== num);
  }

  if (jumpGo) {
    jumpGo.addEventListener("click", doJump);
    jumpEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); doJump(); }
    });
  }

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  function reset(select, label) {
    select.innerHTML = "";
    select.appendChild(el("option", { value: "" }, [label]));
    select.disabled = true;
  }

  function fill(select, items, labelFn, valueFn, blankLabel) {
    reset(select, blankLabel);
    items.forEach(function (item) {
      select.appendChild(el("option", { value: valueFn(item) }, [labelFn(item)]));
    });
    select.disabled = items.length === 0;
  }

  function subjectsAt(lvl) {
    return data.subjects.filter(function (s) {
      var info = s.levels[lvl] || {};
      return (info.standards || []).length > 0;
    }).sort(function (a, b) {
      return a.name.localeCompare(b.name, "en");
    });
  }

  function getChoice(slug, lvl) {
    return subjectsAt(lvl).find(function (s) { return s.slug === slug; });
  }

  // Replace NZQA's assessment jargon with plain student language.
  // Rules come from friendly.json via data.js, shared with the renderer.
  var FRIENDLY_RE = (data.friendly || []).map(function (p) {
    try { return [new RegExp(p[0], "gi"), p[1]]; } catch (e) { return null; }
  }).filter(Boolean);

  function friendly(text) {
    var out = String(text || "");
    FRIENDLY_RE.forEach(function (p) {
      out = out.replace(p[0], p[1]);
    });
    // Raw NZQA filenames (common for Literacy & Numeracy) get readable wording.
    if (!/\s/.test(out) && /[-_]/.test(out)) {
      out = out.replace(/[_-]+/g, " ").replace(/\.(pdf|zip)$/i, "")
               .replace(/\bassessment schedule\b/gi, "schedule")
               .replace(/\bmarking schedule\b/gi, "schedule")
               .replace(/\bassessment paper\b/gi, "paper");
      if (/schedule|marking/i.test(out)) out = "Answer schedule — " + out.replace(/^\s*(schedule|marking)\s+/i, "");
      else if (/paper|exam/i.test(out)) out = "Exam paper — " + out;
    }
    return out;
  }

  function step3Prompt(count) {
    return "Next — pick the standard you want"
      + (count ? " (" + count + " available)" : "") + ".";
  }

  // Bare labels carry no detail; a compact token from the PDF filename can.
  var GENERIC = { "Exam paper": 1, "Answer schedule": 1, "paper": 1, "PDF": 1 };

  function urlQualifier(url) {
    var name = String(url || "").split(/[?#]/)[0].split("/").pop().replace(/\.pdf$/i, "");
    var code = name.match(/^(\d{4,5}[A-Za-z]?[-_]\d+)(?:[-_]|$)/);
    if (code) return code[1].replace(/_/g, "-");
    var week = name.match(/\bweek[-_ ]?(\d+)\b/i);
    if (week) return "week " + week[1];
    var part = name.match(/[-_](vtr|atr|part|pt)[-_]?(\d+)/i);
    if (part) return (part[1].toLowerCase() === "vtr" ? "video " : "part ") + part[2];
    return "";
  }

  // Make duplicate link labels within one year distinguishable.
  function labelsFor(docs) {
    var counts = {};
    docs.forEach(function (d) {
      var label = friendly(d.label) || "PDF";
      counts[label] = (counts[label] || 0) + 1;
    });
    var seen = {};
    return docs.map(function (d) {
      var label = friendly(d.label) || "PDF";
      var total = counts[label];
      if (total > 1 && (GENERIC[label] || /^Audio or video transcript/i.test(label))) {
        var quals = docs.filter(function (x) {
          return (friendly(x.label) || "PDF") === label;
        }).map(function (x) { return urlQualifier(x.url); });
        if (quals.every(function (q) { return !!q; }) &&
            new Set(quals).size === quals.length) {
          return label + " — " + urlQualifier(d.url);
        }
      }
      if (total > 1) {
        seen[label] = (seen[label] || 0) + 1;
        label += " (" + seen[label] + " of " + total + ")";
      }
      return label;
    });
  }

  // The third dropdown lists only standards that have papers or schedules.
  function externals(subject, lvl) {
    return (subject.levels[lvl].standards || []).filter(function (std) {
      return (std.documents || []).length > 0;
    }).map(function (std) {
      return {
        key: std.number,
        label: std.number + " — " + (std.title || ""),
        docs: std.documents || []
      };
    });
  }

  function showFiles() {
    filesEl.innerHTML = "";
    var lvl = levelEl.value;
    var slug = subjectEl.value;
    var key = externalEl.value;
    if (!lvl) { hintEl.textContent = "Start here — pick your level above."; return; }
    if (!slug) { hintEl.textContent = "Next — pick your subject."; return; }
    if (!key) {
      clearSaved();
      hintEl.textContent = step3Prompt(externalEl.options.length - 1);
      return;
    }

    var subject = getChoice(slug, lvl);
    if (!subject) { hintEl.textContent = "That subject isn't available. Please pick another."; return; }
    var chosen = externals(subject, lvl).find(function (x) { return x.key === key; });
    if (!chosen) { hintEl.textContent = "That standard isn't available. Please pick another."; return; }

    hintEl.textContent = subject.name + " — Level " + lvl + " — Standard " + chosen.key
      + " — " + chosen.docs.length + " PDF" + (chosen.docs.length === 1 ? "" : "s");
    lastHash = key;
    try {
      if (navPush && history.pushState) history.pushState(null, "", "#" + key);
      else history.replaceState(null, "", "#" + key);
    } catch (e) {
      try { location.hash = key; } catch (ignored) {}
    }
    try {
      localStorage.setItem("ncea-papers-last", JSON.stringify({ key: key }));
    } catch (e) { /* localStorage may be unavailable on file:// */ }

    if (!chosen.docs.length) {
      filesEl.appendChild(el("p", null, ["No PDFs are listed for this standard right now."]));
      return;
    }

    filesEl.appendChild(el("p", { class: "count" }, [chosen.docs.length + " PDF" + (chosen.docs.length === 1 ? "" : "s") + " ready to open"]));
    if (chosen.docs.every(function (d) { return /answer|schedul|marking/i.test(friendly(d.label)); })) {
      filesEl.appendChild(el("p", null, ["No question paper is listed — only answer booklets and schedules."]));
    }

    var byYear = Object.create(null);
    chosen.docs.forEach(function (d) {
      var y = d.year || "Other";
      (byYear[y] = byYear[y] || []).push(d);
    });
    Object.keys(byYear).sort(function (a, b) {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      return b.localeCompare(a);
    }).forEach(function (yearLabel) {
      var yearHeading = yearLabel === "Other"
        ? "Other papers and schedules (no year listed)" : yearLabel;
      yearHeading += " (" + byYear[yearLabel].length + ")";
      var box = el("section", { class: "year-box" }, [el("h2", null, [yearHeading])]);
      var table = el("table", null, [
        el("thead", null, [el("tr", null, [
          el("th", { scope: "col" }, ["PDF file"])
        ])])
      ]);
      var body = el("tbody");
      var docs = byYear[yearLabel].sort(function (a, b) {
        var la = a.label || "", lb = b.label || "";
        return la < lb ? 1 : la > lb ? -1 : 0;
      });
      var labels = labelsFor(docs);
      docs.forEach(function (d, i) {
        var url = d.url;
        var safe = isPdfUrl(url);
        var cls = /answer|schedul|marking/i.test(labels[i]) ? "pdf-answers" : "pdf-paper";
        var link = safe
          ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer", class: cls }, [labels[i]])
          : el("span", { class: cls }, [labels[i]]);
        body.appendChild(el("tr", null, [el("td", null, [link])]));
      });
      table.appendChild(body);
      box.appendChild(table);
      filesEl.appendChild(box);
    });
    // A native #picker navigation lets Back/Forward return to this standard,
    // and fromLocation() clears the saved state.
    filesEl.appendChild(el("p", { class: "back-link" }, [
      el("a", { href: "#picker" }, ["Back to the picker"])
    ]));
  }

  var booting = true;

  function clearSaved() {
    if (booting) return;
    lastHash = "";
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
    try { localStorage.removeItem("ncea-papers-last"); } catch (e) {}
  }

  function onLevelChange(silent) {
    if (!silent) clearSaved();
    reset(subjectEl, "Pick a subject");
    reset(externalEl, "Pick a standard");
    filesEl.innerHTML = "";
    var lvl = levelEl.value;
    if (!lvl) { hintEl.textContent = "Start here — pick your level above."; return; }
    var subjects = subjectsAt(lvl);
    fill(subjectEl, subjects, function (s) { return s.name; }, function (s) { return s.slug; }, "Pick a subject");
    hintEl.textContent = subjects.length
      ? "Next — pick your subject (" + subjects.length + " available)."
      : "No subjects with PDFs at this level.";
  }

  function onSubjectChange(silent) {
    if (!silent) clearSaved();
    reset(externalEl, "Pick a standard");
    filesEl.innerHTML = "";
    var lvl = levelEl.value;
    var slug = subjectEl.value;
    if (!slug) { hintEl.textContent = "Next — pick your subject."; return; }
    var subject = getChoice(slug, lvl);
    if (!subject) { hintEl.textContent = "That subject isn't available. Please pick another."; return; }
    var list = externals(subject, lvl);
    fill(externalEl, list, function (x) { return x.label; }, function (x) { return x.key; }, "Pick a standard");
    hintEl.textContent = list.length ? step3Prompt(list.length) : "No standards with papers for this subject.";
  }

  levelEl.addEventListener("change", function () { onLevelChange(false); });
  subjectEl.addEventListener("change", function () { onSubjectChange(false); });
  externalEl.addEventListener("change", showFiles);

  onLevelChange();

  var bootHash = decodeHash();
  var fromHash = bootHash.num;
  if (bootHash.bad && bootHash.raw) {
    try { localStorage.removeItem("ncea-papers-last"); } catch (e) {}
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
    hintEl.textContent = "That link has an invalid standard number. Check the number.";
  } else if (fromHash.toLowerCase() === "picker") {
    try { localStorage.removeItem("ncea-papers-last"); } catch (e) {}
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
  } else if (fromHash && !numberIndex[fromHash]) {
    try { localStorage.removeItem("ncea-papers-last"); } catch (e) {}
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
    hintEl.textContent = "No papers listed for " + fromHash + ". Check the number.";
  } else if (fromHash) {
    selectStandard(fromHash);
  } else {
    try {
      var last = JSON.parse(localStorage.getItem("ncea-papers-last") || "null");
      if (last && numberIndex[last.key]) selectStandard(last.key);
      else if (last) localStorage.removeItem("ncea-papers-last");
    } catch (e) {
      try { localStorage.removeItem("ncea-papers-last"); } catch (ignored) {}
    }
  }
  booting = false;
})();
