/* Topic research workspace: deterministic actions use the existing panel and API; AI starts only via chat Send. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const R = PL.research = { tid: "", topics: [], selected: new Map(), actions: [], query: "", offset: 0 };
  let epoch = 0, request = null, timer = 0;
  const tr = (vi, en) => PL.lang === "en" ? en : vi;
  const button = (label, run, cls) => h("button.btn.sm" + (cls ? "." + cls : ""), { type: "button", onclick: async (e) => { const control = e.currentTarget; control.disabled = true; await PL.safe(run); control.disabled = false; } }, label);
  const label = (name, input) => h("label.field", {}, h("span", {}, name), input);
  const input = (value, attrs) => h("input.input", Object.assign({ value: value == null ? "" : String(value) }, attrs || {}));
  const select = (items, value) => h("select.input", {}, items.map(([id, name]) => h("option", { value: id, selected: String(value) === String(id) || null }, name)));
  const base = () => "/api/research/topics/" + encodeURIComponent(R.tid);
  const topic = () => R.topics.find(t => t.id === R.tid);

  R.reset = function () { R.tid = ""; R.topics = []; R.selected.clear(); R.query = ""; PL.chat.atts = []; epoch++; if (request) request.abort(); R.chips(); };
  R.onSession = function (s) {
    if (s && (s.topic_id || "") !== R.tid) { R.selected.clear(); PL.chat.atts = []; R.tid = s.topic_id || ""; R.query = ""; }
    R.chips();
  };
  R.sources = () => Array.from(R.selected.keys());
  R.chips = function () {
    const b = PL.$("#research-chips");
    if (b) {
      b.replaceChildren();
      for (const [id, title] of R.selected) b.append(button(title + " ×", () => { R.selected.delete(id); R.chips(); }));
    }
    const t = PL.$("#topic-btn");
    if (t) t.textContent = R.tid ? (topic() || {}).title || tr("chủ đề đang mở", PL.ui("Active Topic")) : tr("chủ đề · Dự án", PL.ui("Topic · Project"));
  };
  R.toggle = function (id, title, on) { if (on) R.selected.set(id, title); else R.selected.delete(id); R.chips(); };
  async function loadTopics() { const r = await PL.get("/api/research/topics"); R.topics = r.topics; R.schedules = r.schedules || {}; R.chips(); }
  R.switchTopic = async function (tid) {
    if (PL.chat.busy) { PL.toast(tr("Hãy dừng hoặc chờ lượt chat hiện tại", "Stop or wait for the current chat turn")); return; }
    // A topic owns a separate conversation; history from another topic is never reused.
    const session = await PL.post("/api/chat/sessions", { topic_id: tid, title: tid ? (topic() || {}).title : undefined });
    R.selected.clear(); PL.chat.atts = []; R.tid = tid; R.query = ""; R.offset = 0;
    R.chips();
    PL.go("#/chat/" + session.id);
  };
  function shell(mode) {
    epoch++;
    if (request) request.abort();
    const nav = h("div.research-nav", {}, [["papers", tr(PL.ui("Paper"), PL.ui("Papers"))], ["topics", PL.ui("Topics")], ["workspaces", PL.ui("Workspaces")], ["artifacts", tr("Nguồn gốc", "Provenance")], ["jobs", PL.ui("Jobs")]]
      .concat([["monitor",PL.ui("Mission Monitor")],["teams",PL.ui("Teams")],["workstreams",PL.ui("Workstreams")],["missions", PL.ui("Missions")],["protocols",PL.ui("Experiments")],["claims",PL.ui("Review Room")]]).map(([key, title]) => button(title, () => R.open(key), key === mode ? "accent" : "ghost")));
    const body = h("div.research-body", { dataset: { mode } });
    PL.panels.open(tr("Không gian nghiên cứu", "Research workspace"), h("div", {}, nav, body), { kind: "research", arg: mode });
    body.append(h("p.muted", {}, tr("Đang tải…", "Loading…")));
    return body;
  }
  R.open = async function (mode) {
    mode = mode || "papers";
    if (mode === "papers" && R.flags && R.flags.paper_explorer_v2 === false) { PL.toast(PL.ui("Paper Explorer is disabled in UI settings")); return; }
    const body = shell(mode), revision = epoch;
    try {
      await loadTopics();
      if (revision !== epoch) return;
      body.replaceChildren();
      if (mode === "topics") return renderTopics(body);
      if (!R.tid) { body.append(h("p", {}, tr("Chọn hoặc tạo chủ đề trước.", "Choose or create a Topic first.")), button(PL.ui("Topics"), () => R.open("topics"))); return; }
      body.append(h("p.research-context", {}, (topic() || {}).title || R.tid));
      if (mode === "papers") await renderPapers(body, revision);
      else if (mode === "workspaces") await renderWorkspaces(body, revision);
      else if (mode === "artifacts") await renderArtifacts(body, revision);
      else if (mode === "jobs") await renderJobs(body, revision);
      else if (mode === "missions") await renderMissions(body, revision);
      else if (mode === "protocols") await renderProtocols(body, revision);
      else if (mode === "claims") await renderClaims(body, revision);
      else if (mode === "monitor") await renderMonitor(body, revision);
      else if (mode === "teams") await renderTeams(body, revision);
      else if (mode === "workstreams") await renderWorkstreams(body, revision);
    } catch (e) { if (revision === epoch) { body.replaceChildren(h("p.error", {}, e.message), button(tr("Thử lại", PL.ui("Retry")), () => R.open(mode))); } }
  };

  function renderTopics(body) {
    body.append(button(tr("＋ chủ đề mới", "＋ New Topic"), () => editTopic(null)), button(tr("Chat toàn dự án", "Project chat"), () => R.switchTopic("")));
    for (const t of R.topics) {
      const schedule = R.schedules[t.id] || {};
      const card = h("article.research-card", {}, h("b", {}, t.title), h("p.muted", {}, t.objectives || t.description),
        h("p.muted", {}, `${t.sources.join(", ")} · ${t.cadence} · ${PL.ui(t.enabled ? "enabled" : "paused")} · ≤${t.pdf_limit} ${PL.ui("PDFs/run")}`),
        h("p.muted", {}, `${tr("Lần trước", "Last")}: ${schedule.last_run || "—"} ${PL.ui(schedule.last_status || "")} · ${tr("Lần tới", "Next")}: ${schedule.next_run || "—"} (UTC)`),
        h("div.row.wrap", {}, button(tr("Mở chủ đề", "Open Topic"), () => R.switchTopic(t.id)), button(tr("Sửa", "Edit"), () => editTopic(t)),
          button(PL.ui(t.archived ? "Restore Topic" : "Archive Topic"), async () => {
            const { id, created, updated, ...data } = t;
            await PL.put("/api/research/topics/" + id, { ...data, archived: !t.archived, enabled: false }); await R.open("topics");
          }),
          (!R.flags || R.flags.topic_scheduler_ui !== false) ? button(t.enabled ? tr("Tạm dừng", PL.ui("Pause")) : tr("Bật lịch", "Enable schedule"), async () => {
            const { id, created, updated, ...data } = t;
            await PL.put("/api/research/topics/" + id, { ...data, enabled: !t.enabled }); await R.open("topics");
          }) : null));
      body.append(card);
    }
    body.append(button(tr("Tình trạng tích hợp cục bộ", "Local integration status"), async () => {
      const r = await PL.get("/api/research/capabilities");
      PL.modal({ title: PL.ui("Optional integrations"), body: h("div", {}, ...r.plugins.map(p => h("p", {}, `${p.id} · ${p.version || PL.ui("not installed")} · ${p.status}`)), h("p.muted", {}, r.retrieval)), actions: [{ label: PL.ui("Close") }] });
    }));
    if (!R.topics.length) body.append(h("p.muted", {}, tr("Chưa có chủ đề. Thư viện và chat cũ vẫn ở cấp dự án.", "No Topics yet. Existing library and chats remain at project level.")));
  }
  function editTopic(t) {
    const title = input(t && t.title), objectives = h("textarea.input", { rows: 3 }, t && t.objectives || "");
    const keywords = input((t && t.keywords || []).join("; ")), synonyms = input((t && t.synonyms || []).join("; ")), exclusions = input((t && t.exclusions || []).join("; "));
    const cadence = select([["manual", PL.ui("Manual")], ["off", PL.ui("Off")], ["daily", PL.ui("Daily (UTC)")], ["weekly", PL.ui("Weekly (UTC)")]], t && t.cadence || "manual");
    const providers = input((t && t.sources || ["openalex", "arxiv", "semantic_scholar", "crossref"]).join("; "));
    const pdf = input(t ? t.pdf_limit : 10, { type: "number", min: 0, max: 25 }), storage = input(t ? t.storage_mb : 1024, { type: "number", min: 1 });
    const metadata = input(t ? t.metadata_limit : 30, { type: "number", min: 1, max: 100 }), size = input(t ? t.max_pdf_mb : 25, { type: "number", min: 1, max: 30 });
    const year = input(t ? t.min_year : 2019, { type: "number", min: 1900, max: 2100 });
    const auto = input("", { type: "checkbox", checked: t && t.auto_download || null }), enabled = input("", { type: "checkbox", checked: t && t.enabled || null });
    const parser = select([["existing", PL.ui("Existing PDF parser (default)")], ["docling", PL.ui("Docling (optional local artifacts required)")]], t && t.parser || "existing");
    if (R.flags && R.flags.topic_scheduler_ui === false) { cadence.disabled = true; enabled.disabled = true; }
    PL.modal({ title: t ? tr("Sửa chủ đề", "Edit Topic") : tr("chủ đề mới", "New Topic"), body: h("div", {}, label(PL.ui("Title"), title), label(PL.ui("Objectives"), objectives),
      label(PL.ui("Keywords (;)"), keywords), label(PL.ui("Synonyms (;)"), synonyms), label(PL.ui("Exclusions (;)"), exclusions), label(PL.ui("Sources (;): openalex, arxiv, semantic_scholar, crossref"), providers),
      h("p.muted", {}, PL.ui("Additional sources: cvf, pmlr, neurips, acl_anthology, openreview, zenodo, europe_pmc, hal. Order sets priority; omit a source to disable it.")), label(PL.ui("From year"), year), label(PL.ui("Cadence"), cadence), label(PL.ui("Schedule enabled"), enabled), label(PL.ui("Metadata/run"), metadata), label(PL.ui("PDFs/run"), pdf), label("MB/PDF", size), label(PL.ui("Storage MB/topic"), storage), label(PL.ui("Auto-download eligible OA"), auto), label(PL.ui("Parser"), parser)),
      actions: [{ label: tr("Huỷ", PL.ui("Cancel")) }, { label: tr("Lưu", PL.ui("Save")), kind: "accent", onClick: async () => {
        const split = (s) => s.value.split(";").map(x => x.trim()).filter(Boolean);
        const { id, created, updated, ...old } = t || {};
        const data = { ...old, title: title.value, objectives: objectives.value, keywords: split(keywords), synonyms: split(synonyms), exclusions: split(exclusions), sources: split(providers),
          cadence: cadence.value, pdf_limit: Number(pdf.value), storage_mb: Number(storage.value), metadata_limit: Number(metadata.value), max_pdf_mb: Number(size.value), min_year: Number(year.value), enabled: enabled.checked, auto_download: auto.checked, parser: parser.value };
        const result = await PL.safe(() => t ? PL.put("/api/research/topics/" + t.id, data) : PL.post("/api/research/topics", data));
        if (!result) return false;
        await R.open("topics"); return true;
      } }] });
  }

  async function renderPapers(body, revision) {
    const controls = h("div.research-filters"), results = h("div"), q = input(R.query, { type: "search", placeholder: tr("Tìm tài liệu trong chủ đề…", "Search Topic papers…"), "aria-label": "Search Topic papers" });
    const level = select([["-1", "L0–L4"], ...[0, 1, 2, 3, 4].map(n => [n, "L" + n])], -1);
    const state = select([["", PL.ui("All")], ...(!R.flags || R.flags.discovery_inbox !== false ? [["candidate", PL.ui("Discovery Inbox")]] : []), ["accepted", PL.ui("Accepted")], ["dismissed", PL.ui("Dismissed")], ["deferred", PL.ui("Deferred")]], "");
    const year = input("", { type: "number", placeholder: PL.ui("From year"), "aria-label": PL.ui("From year") }), source = input("", { placeholder: PL.ui("Source"), "aria-label": PL.ui("Source") });
    const sort = select([["relevance", PL.ui("Lexical matches")], ["year", PL.ui("Year")], ["citations", PL.ui("Citation count (unknown last)")]], "relevance"), oa = input("", { type: "checkbox", "aria-label": PL.ui("Open access only") });
    const advanced = h("details", {}, h("summary", {}, PL.ui("More filters")));
    const extra = {};
    for (const [key, text] of [["max_year", "To year"], ["venue", "Venue"], ["publication_type", "Publication type"], ["tag", "Tag"], ["flag", "Risk or version flag"]]) {
      extra[key] = input("", { "aria-label": PL.ui(text), placeholder: PL.ui(text) }); advanced.append(extra[key]);
    }
    extra.pdf = select([["", PL.ui("Any PDF status")], ["true", PL.ui("Downloaded PDF")], ["false", PL.ui("PDF not downloaded")]], "");
    extra.pdf.setAttribute("aria-label", PL.ui("PDF status")); advanced.append(extra.pdf);
    controls.append(q, level, state, year, source, sort, label("OA", oa), advanced);
    body.append(controls, h("div.row.wrap", {}, button(tr("Khám phá ngay", "Discover now"), async () => { await PL.post(base() + "/discover"); await R.open("jobs"); }),
      button(PL.ui("Dry run"), async () => { await PL.post(base() + "/discover", { dry_run: true }); await R.open("jobs"); }),
      button(tr("Nhập thư viện cũ", "Import existing library"), async () => { await PL.post(base() + "/papers/import-library"); await load(); }),
      button(tr("Nhập Zotero JSON", "Import Zotero JSON"), () => importZotero()),
      button(PL.ui("Read local Zotero"), async () => {
        if (!(await PL.confirm(PL.ui("Read up to 1000 items from the local Zotero library? References remain pending curation; Zotero is not modified.")))) return;
        const receipt = await PL.post(base() + "/zotero/sync", { allow_network: true, max_items: 1000 });
        PL.modal({ title: PL.ui("Zotero read-only sync receipt"), body: h("pre", {}, JSON.stringify(receipt, null, 2)), actions: [{ label: PL.ui("Close") }] });
        await load();
      }),
      button(PL.ui("Citation graph"), async () => {
        const graph = await PL.get(base() + "/citation-graph");
        PL.modal({ title: PL.ui("Source-declared citations"), body: h("pre", {}, JSON.stringify(graph, null, 2)), actions: [{ label: PL.ui("Close") }] });
      })), results);
    const bulk = h("div.row.wrap.research-bulk", {}, ...[["accept", tr("Chấp nhận", "Accept")], ["defer", PL.ui("Defer")], ["dismiss", PL.ui("Dismiss")], ["download", PL.ui("OA PDF")], ["index", PL.ui("Reprocess PDF")], ["tag", PL.ui("Add tags")], ["untag", PL.ui("Remove tags")], ["screen", PL.ui("L3 screen")], ["verify", PL.ui("L4 attest")]].map(([action, name]) => button(name, async () => {
      const ids = R.sources().filter(id => id.startsWith("paper:")).map(id => id.slice(6));
      if (!ids.length) { PL.toast(tr("Chọn tài liệu trước", "Select papers first")); return; }
      let note = "";
      let tags = [];
      if (action === "tag" || action === "untag") {
        const value = await PL.prompt(PL.ui("Paper tags"), PL.ui("Tags separated by semicolons"), "");
        if (!value) return;
        tags = value.split(";").map(x => x.trim()).filter(Boolean);
      }
      if (action === "verify") { note = await PL.prompt(PL.ui("L4 · User attestation"), PL.ui("Review note (not a universal validity guarantee)"), ""); if (!note) return; }
      if (action === "dismiss" && !(await PL.confirm(PL.ui("Dismiss selected candidates? They remain recoverable in Dismissed.")))) return;
      await PL.post(base() + "/papers/bulk", { action, paper_ids: ids, note, tags });
      if (action === "download" || action === "index") await R.open("jobs"); else await load();
    })), button(tr("Thêm vào chủ đề khác", "Add to another Topic"), async () => {
      const target = await PL.prompt(PL.ui("Target Topic"), R.topics.map(t => t.title + " = " + t.id).join("\n"), "");
      if (target) await PL.post(base() + "/papers/bulk", { action: "associate", target_topic_id: target, paper_ids: R.sources().filter(s => s.startsWith("paper:")).map(s => s.slice(6)) });
    }), button(tr("So sánh với AI", "Compare with AI"), () => R.ai("compare")), button(tr("Phản biện với AI", PL.ui("Review with AI")), () => R.ai("review")),
      h("a.btn.sm", { href: base() + "/bibliography", download: "topic-references.bib" }, PL.ui("BibTeX · accepted only")));
    body.insertBefore(bulk, results);
    let serial = 0;
    async function load() {
      const seq = ++serial;
      if (request) request.abort(); request = new W.AbortController();
      const params = new W.URLSearchParams({ q: q.value, level: level.value, state: state.value, year: year.value || 0, source: source.value, sort: sort.value, oa: String(oa.checked), offset: R.offset, limit: 25 });
      for (const [key, control] of Object.entries(extra)) if (control.value) params.set(key, control.value);
      try {
        const r = await PL.api("GET", base() + "/papers?" + params, undefined, { signal: request.signal });
        if (revision !== epoch || seq !== serial) return;
        results.replaceChildren(h("p.muted", {}, `${r.total} ${PL.ui("Papers")} · ${R.offset + 1}–${Math.min(R.offset + 25, r.total)}`));
        if (!r.papers.length) results.append(h("p", {}, tr("Chưa có kết quả. Khám phá hoặc nhập metadata.", "No results. Discover or import metadata.")));
        for (const p of r.papers) {
          const checkbox = input("", { type: "checkbox", checked: R.selected.has("paper:" + p.id) || null, "aria-label": PL.ui("Select ") + p.title });
          checkbox.onchange = () => R.toggle("paper:" + p.id, p.title, checkbox.checked);
          results.append(h("article.research-card", {}, h("label.row", {}, checkbox, h("b", {}, p.title)), h("p.muted", {}, `${p.year || "?"} · ${p.venue || PL.ui("unknown venue")} · ${p.sources.join(", ")}`),
            h("div.row.wrap", {}, h("span.chip", {}, "L" + p.level), h("span.chip", {}, PL.ui(p.state)), h("span.chip", {}, p.oa_locations.length ? PL.ui("OA candidate") : PL.ui("Metadata only")), ...p.flags.map(f => h("span.chip.warn", {}, f))),
            h("p.muted", {}, PL.ui("Matched terms: ") + (p.association.matched_terms || []).join(", ")),
            h("p.muted", {}, PL.ui("Tags") + ": " + (p.association.tags || []).join(", ")),
            p.association.review_reset ? h("p.muted", {}, PL.ui("Review reset: ") + p.association.review_reset.reason) : null,
            button(tr("Phiên bản & bằng chứng", "Versions & evidence"), () => paperDetail(p))));
        }
        results.append(h("div.row", {}, button("←", async () => { R.offset = Math.max(0, R.offset - 25); await load(); }), button("→", async () => { if (R.offset + 25 < r.total) { R.offset += 25; await load(); } })));
      } catch (e) { if (e.name !== "AbortError" && revision === epoch) results.replaceChildren(h("p.error", {}, e.message)); }
    }
    q.oninput = () => { R.query = q.value; R.offset = 0; W.clearTimeout(timer); timer = W.setTimeout(load, 250); };
    for (const x of [level, state, year, source, sort, oa, ...Object.values(extra)]) x.onchange = () => { R.offset = 0; load(); };
    await load();
  }
  function paperDetail(p) {
    const body = h("div", {}, h("p", {}, p.abstract || PL.ui("Abstract unavailable")), h("p.muted", {}, "DOI: " + (p.doi || "unknown")));
    for (const v of p.versions) {
      body.append(h("p", {}, `${v.id} · ${v.source} · ${v.version}`));
      if (v.document) body.append(h("p.muted", {}, PL.ui(v.document.status) + " · " + v.document.sha256), h("a.btn.sm", { href: base() + `/papers/${p.id}/pdf/${v.id}`, target: "_blank", rel: "noopener" }, PL.ui("Open PDF")));
      else body.append(h("p.muted", {}, PL.ui("Full text unavailable for this version")));
    }
    const search = input("", { placeholder: PL.ui("Find page evidence"), "aria-label": PL.ui("Find page evidence") }), evidence = h("div");
    body.append(search, button(PL.ui("Evidence"), async () => { const r = await PL.get(base() + "/evidence?paper_id=" + encodeURIComponent(p.id) + "&q=" + encodeURIComponent(search.value)); evidence.replaceChildren(); for (const e of r.evidence.filter(e => e.paper_id === p.id)) evidence.append(h("div", {}, h("p", {}, `[${e.id}] v${e.version_id} p.${e.page}: ${e.text}`),
        e.version_id && e.page ? h("a.btn.sm", { href: base() + `/papers/${p.id}/pdf/${e.version_id}#page=${e.page}`, target: "_blank", rel: "noopener" }, PL.ui("Open cited page")) : h("p.muted", {}, PL.ui("Page location unavailable")))); }), evidence);
    PL.modal({ title: p.title, body, actions: [{ label: tr("Đóng", PL.ui("Close")) }] });
  }
  function importZotero() {
    const file = h("input", { type: "file", accept: ".json,application/json", onchange: async () => {
      if (!file.files[0]) return;
      await PL.safe(async () => { await PL.upload(base() + "/zotero/import", file.files[0]); await R.open("papers"); });
    } }); file.click();
  }
  R.ai = function (skill) {
    if (R.flags && R.flags.contextual_actions === false) { PL.toast(PL.ui("Contextual AI actions are disabled")); return; }
    if (!R.selected.size) { PL.toast(tr("Chọn nguồn trước", "Select sources first")); return; }
    PL.chat.setInput("/" + skill + " " + tr("Phân tích các nguồn đã chọn; dẫn ID, phiên bản và trang khi có. Nêu rõ điều chưa kiểm chứng.", "Analyze the selected sources; cite IDs, versions and pages when available. State what is unverified."));
    PL.$("#input").focus();
  };

  async function renderWorkspaces(body, revision) {
    body.append(h("p.help", {}, PL.ui("Open the engine in its own window on this computer, or edit its files in VS Code. Sync saved artifacts back when ready.")), h("p.muted", {}, tr("Chỉ đồng bộ file đã lưu; không đọc được toàn bộ phiên, suy luận riêng hoặc hoạt động chưa lưu của engine.", "Only saved files are observable; full external sessions, private reasoning and unsaved activity are not captured.")),
      button(tr("＋ Tạo / liên kết workspace", "＋ Create / link workspace"), () => {
        const engine = select([["openscience", "OpenScience"], ["feynman", "Feynman"]], "openscience"), path = input("", { placeholder: PL.ui("Empty = managed folder; otherwise absolute existing folder") }), interval = input(0, { type: "number", min: 0 });
        PL.modal({ title: PL.ui("Engine workspace"), body: h("div", {}, label(PL.ui("Engine"), engine), label(PL.ui("Path"), path), label(PL.ui("Sync interval minutes (0 = manual)"), interval)), actions: [{ label: PL.ui("Cancel") }, { label: PL.ui("Link"), kind: "accent", onClick: async () => {
          const result = await PL.safe(() => PL.post(base() + "/workspaces", { engine: engine.value, path: path.value, sync_interval_minutes: Number(interval.value) }));
          if (!result) return false; await R.open("workspaces"); return true;
        } }] });
      }));
    const r = await PL.get(base() + "/workspaces"); if (revision !== epoch) return;
    for (const w of r.workspaces) body.append(h("article.research-card", {}, h("b", {}, w.engine), h("p.research-path", {}, w.path),
      h("p.muted", {}, `${w.capabilities.binary_available ? PL.ui("CLI found") : PL.ui("CLI missing")} · ${w.artifact_count} ${tr("hiện vật", "artifacts")} · ${w.checkpoint ? w.checkpoint.status + " / " + w.checkpoint.at : PL.ui("Never synced")}`),
      w.checkpoint && w.checkpoint.error ? h("p.error", {}, w.checkpoint.error) : null,
      h("div.row.wrap", {}, button(PL.ui("Open ") + w.engine + " ↗", async () => {
        const result = await PL.post("/api/research/workspaces/" + w.id + "/open");
        PL.modal({ title: PL.ui(result.status), body: h("div", {}, h("p", {}, PL.ui(result.detail || result.status)), result.command ? h("pre", {}, result.command) : null, result.log ? h("p", {}, result.log) : null), actions: [{ label: PL.ui("Close") }] });
      }), button(PL.ui("Open in VS Code"), () => PL.post("/api/research/workspaces/" + w.id + "/editor").then(() => PL.toast(PL.ui("Opened in a separate window")))), button(PL.ui("Sync Now"), async () => { await PL.post("/api/research/workspaces/" + w.id + "/sync"); await R.open("jobs"); }), button(PL.ui("View changes"), () => R.open("artifacts")),
      button(PL.ui("Relink / schedule"), () => {
        const path = input(w.path), interval = input(w.sync_interval_minutes || 0, { type: "number", min: 0 });
        PL.modal({ title: PL.ui("Relink workspace (no files moved)"), body: h("div", {}, label(PL.ui("Existing folder"), path), label(PL.ui("Sync interval minutes (0 = manual)"), interval)), actions: [{ label: PL.ui("Cancel") }, { label: PL.ui("Save"), kind: "accent", onClick: async () => {
          const r = await PL.safe(() => PL.put("/api/research/workspaces/" + w.id, { engine: w.engine, path: path.value, sync_interval_minutes: Number(interval.value) }));
          if (!r) return false; await R.open("workspaces"); return true;
        } }] });
      })),
      w.checkpoint ? h("details", {}, h("summary", {}, PL.ui("Sync transparency report")), h("pre", {}, JSON.stringify(w.checkpoint, null, 2))) : null));
    if (!r.workspaces.length) body.append(h("p.muted", {}, PL.ui("No workspaces linked")), h("p.help", {}, PL.ui("Create a workspace above to open OpenScience or Feynman independently. Each Topic keeps its own files.")));
  }
  async function renderArtifacts(body, revision) {
    const [a, p, findings] = await Promise.all([PL.get(base() + "/artifacts?history=true"), PL.get(base() + "/provenance"), PL.get(base() + "/findings")]);
    if (revision !== epoch) return;
    const filter = input("", { placeholder: PL.ui("Filter artifact / engine"), "aria-label": PL.ui("Filter artifact / engine") }), list = h("div");
    body.append(filter, button(PL.ui("Review with AI"), () => R.ai("review")), button(PL.ui("Propose finding"), async () => {
      const text = await PL.prompt(PL.ui("Finding proposal"), PL.ui("Claim linked to selected evidence; pending human review"), "");
      if (text) { await PL.post(base() + "/findings", { text, source_evidence_ids: R.sources() }); await R.open("artifacts"); }
    }), list);
    function paint() {
      list.replaceChildren();
      for (const x of a.artifacts.filter(x => (x.path + " " + x.engine).toLowerCase().includes(filter.value.toLowerCase()))) {
        const checkbox = input("", { type: "checkbox", checked: R.selected.has("artifact:" + x.id) || null, "aria-label": PL.ui("Select artifact ") + x.path });
        checkbox.onchange = () => R.toggle("artifact:" + x.id, x.path + " v" + x.version, checkbox.checked);
        list.append(h("article.research-card", {}, h("label.row", {}, checkbox, h("b", {}, x.path)), h("p.muted", {}, `${x.engine} · v${x.version} · ${PL.ui(x.available ? "observed" : "unavailable / tombstone")} · ${x.bytes} bytes`), h("p.research-path", {}, x.sha256 || PL.ui("Hash not computed: metadata only")),
          button(PL.ui("Inspect artifact version"), async () => {
            const detail = await PL.get(base() + "/artifacts/" + encodeURIComponent(x.id));
            PL.modal({ title: detail.title, body: h("pre", {}, detail.text), actions: [{ label: PL.ui("Close") }] });
          })));
      }
    }
    filter.oninput = paint; paint();
    for (const f of findings.findings) body.append(h("article.research-card", {}, h("b", {}, PL.ui("Finding · ") + PL.ui(f.status)), h("p", {}, f.text), h("p.muted", {}, f.source_evidence_ids.join(", ")),
      f.status === "pending" ? h("div.row", {}, ...[true, false].map(approve => button(approve ? PL.ui("Approve") : PL.ui("Reject"), async () => {
        const note = await PL.prompt(PL.ui("Human review"), PL.ui("Review note"), ""); if (!note) return;
        await PL.post(base() + "/findings/" + f.id + "/review", { approve, note }); await R.open("artifacts");
      }))) : null));
    const timelineFilter = input("", { type: "search", "aria-label": PL.ui("Filter timeline by engine, session, artifact or date"), placeholder: PL.ui("Filter timeline by engine, session, artifact or date") }), timeline = h("div.provenance-events");
    body.append(h("h3", {}, PL.ui("Provenance timeline")), h("p.muted", {}, PL.ui("Latest 100 events; filter applies to this loaded window.")), timelineFilter, timeline);
    const paintTimeline = () => {
      timeline.replaceChildren();
      for (const e of p.events.filter(e => JSON.stringify(e).toLowerCase().includes(timelineFilter.value.toLowerCase())))
        timeline.append(h("details.research-card", {}, h("summary", {}, e.type + " · " + e.observed), h("pre", {}, JSON.stringify(e.payload, null, 2))));
    };
    timelineFilter.oninput = paintTimeline; paintTimeline();
  }
  async function renderJobs(body, revision) {
    body.append(button(tr("Làm mới", PL.ui("Refresh")), () => R.open("jobs")));
    const r = await PL.get("/api/research/jobs?topic_id=" + R.tid); if (revision !== epoch) return;
    if (!r.jobs.length) body.append(h("p.muted", {}, PL.ui("No jobs")));
    for (const j of r.jobs) body.append(h("article.research-card", {}, h("b", {}, j.kind + " · " + PL.ui(j.status)), h("p.muted", {}, j.updated),
      h("pre", {}, JSON.stringify(j.payload.result || { error: j.payload.error || "", ...j.payload }, null, 2)),
      ["queued", "running"].includes(j.status) ? button(PL.ui("Cancel"), async () => { await PL.post("/api/research/jobs/" + j.id + "/cancel"); await R.open("jobs"); }) : null,
      ["failed", "partial", "interrupted", "cancelled"].includes(j.status) ? button(PL.ui("Retry"), async () => { await PL.post("/api/research/jobs/" + j.id + "/retry"); await R.open("jobs"); }) : null));
  }
  R.dispatch = async function (action) {
    const view = action.route_or_component_key;
    if (action.availability !== "available") { PL.toast(PL.ui("Action unavailable")); return; }
    if (view === "library") return PL.panels.library();
    if (view === "settings") return PL.settings.open();
    if (["papers", "topics", "workspaces", "artifacts", "jobs", "missions", "protocols", "claims", "monitor", "teams", "workstreams"].includes(view)) return R.open(view);
    throw new Error("Unregistered UI component");
  };
  async function renderMissions(body, revision) {
    body.append(button(PL.ui("New mission / JSON plan"), () => {
      const plan=h("textarea.input",{rows:16,"aria-label":PL.ui("Mission JSON plan")},JSON.stringify({topic_id:R.tid,objective:"Inspect selected topic evidence",permissions:["workspace_write"],tasks:[{id:"inspect",capability:"paper.inspect",args:{paper_ids:R.sources().filter(s=>s.startsWith("paper:")).map(s=>s.slice(6)),limit:2}},{id:"report",capability:"mission.report",depends_on:["inspect"]}]},null,2));
      PL.modal({title:PL.ui("Mission preview · creation does not execute"),body:plan,actions:[{label:PL.ui("Cancel")},{label:PL.ui("Create draft"),kind:"accent",onClick:async()=>{
        const r=await PL.safe(()=>PL.post(base()+"/missions",JSON.parse(plan.value)));if(!r)return false;await R.open("missions");return true;
      }}]});
    }),button(PL.ui("Draft with AI · one call"),async()=>{const objective=await PL.prompt(PL.ui("AI planning uses the configured provider"),PL.ui("One reasoning/network call creates a draft; it cannot approve execution"),"");if(objective){await PL.post(base()+"/missions/plan",{objective,allow_reasoning:true});await R.open("missions");}}),button(PL.ui("Refresh"),()=>R.open("missions")));
    const result=await PL.get(base()+"/missions");if(revision!==epoch)return;
    for(const m of result.missions)body.append(h("article.research-card",{},h("b",{},m.payload.spec.objective+" · "+PL.ui(m.status)),
      h("p.muted",{},PL.ui("Permissions: ")+m.payload.spec.permissions.join(", ")+PL.ui(" · reasoning calls ")+m.payload.reasoning_calls+" · "+m.payload.active_seconds.toFixed(2)+"s"),
      h("details",{},h("summary",{},PL.ui("Review immutable plan & limits")),h("pre",{},JSON.stringify(m.payload.spec,null,2))),
      ...m.tasks.map(t=>h("details",{},h("summary",{},t.id+" · "+PL.ui(t.status)),h("pre",{},JSON.stringify(t.payload,null,2)),["failed","interrupted"].includes(t.status)?button(PL.ui("Reconcile / retry task"),async()=>{const reconcile_note=await PL.prompt(PL.ui("Retry requires fresh mission approval"),PL.ui("Confirm known admission outcome; never repeat an uncertain external action blindly"),"");if(reconcile_note){await PL.post(base()+"/missions/"+m.id+"/retry",{task_id:t.id,reconcile_note});await R.open("missions");}}):null)),
      ["draft","awaiting_approval","paused"].includes(m.status)?button(PL.ui("Approve this plan"),async()=>{const note=await PL.prompt(PL.ui("Approve exact plan"),PL.ui("Review permissions, engine, limits and scientific intent"),"");if(note){await PL.post(base()+"/missions/"+m.id+"/approve",{plan_digest:m.payload.plan_digest,note});await R.open("missions");}}):null,
      button(PL.ui("Cancel"),async()=>{await PL.post(base()+"/missions/"+m.id+"/cancel");await R.open("missions");})));
  }
  R.editContract=function(title,initial,submit) {
    const text=h("textarea.input",{rows:18,"aria-label":title},JSON.stringify(initial,null,2));
    PL.modal({title,body:text,actions:[{label:PL.ui("Cancel")},{label:PL.ui("Save draft"),kind:"accent",onClick:async()=>{const result=await PL.safe(()=>submit(JSON.parse(text.value)));return result?true:false;}}]});
  };
  async function renderMonitor(body,revision) {
    const [settings,project,result]=await Promise.all([PL.get("/api/research/os-settings"),PL.get("/api/research/charters"),PL.get(base()+"/missions")]);if(revision!==epoch)return;
    body.append(h("p.muted",{},PL.ui("Experimental supervised operation. Runs while this app and machine are active. Exact approvals, finite budgets, no hidden API billing; mission completion does not approve scientific claims.")),
      button(settings.enabled?PL.ui("Disable Research OS"):PL.ui("Enable experimental Research OS"),async()=>{await PL.put("/api/research/os-settings",{enabled:!settings.enabled});await R.open("monitor");}),
      button(PL.ui("New project charter"),()=>R.editContract(PL.ui("Project charter JSON"),{goal:"Medical Image Restoration",topics:[{topic_id:R.tid,goal:(topic()||{}).title||"Research topic"}],permissions:["workspace_write"],retrieval:[],max_reasoning_calls:0,max_active_seconds:600},async spec=>{const result=await PL.post("/api/research/charters",spec);await R.open("monitor");return result;})),
      button(PL.ui("New supervised mission"),()=>R.editContract(PL.ui("Supervised mission JSON"),{topic_id:R.tid,objective:"Inspect scoped evidence and report",permissions:["workspace_write"],control:{success_criteria:["Evidence report is available for human review"],allowed_engines:["deterministic"],end_date:new Date(Date.now()+86400000).toISOString(),allow_api_billing:false},tasks:[{id:"inspect",capability:"paper.inspect",args:{paper_ids:R.sources().filter(s=>s.startsWith("paper:")).map(s=>s.slice(6)),limit:2}},{id:"report",capability:"mission.report",depends_on:["inspect"]}]},async spec=>{const result=await PL.post(base()+"/missions",spec);await R.open("monitor");return result;})),button(PL.ui("Refresh"),()=>R.open("monitor")));
    for(const ch of project.charters)body.append(h("details.research-card",{},h("summary",{},PL.ui("Charter: ")+ch.payload.goal),h("pre",{},JSON.stringify(ch,null,2))));
    for(const m of result.missions.filter(m=>m.payload.spec.control)) {
      const url=base()+"/missions/"+m.id;
      body.append(h("article.research-card",{},h("b",{},m.payload.spec.objective+" · "+PL.ui(m.status)),h("p",{},m.payload.blocking_reason||PL.ui("Next decision: ")+(m.status==="awaiting_review"?PL.ui("Human mission review"):PL.ui("Inspect plan and approvals"))),h("p.muted",{},PL.ui("Reasoning requests: ")+m.payload.reasoning_calls+PL.ui(" · active seconds: ")+m.payload.active_seconds.toFixed(2)+PL.ui(" · token/currency cost unknown")),h("details",{},h("summary",{},PL.ui("Brief, limits and run history")),h("pre",{},JSON.stringify(m,null,2))),
        m.status==="draft"?button(PL.ui("Request approval"),async()=>{await PL.post(url+"/request-approval");await R.open("monitor");}):null,
        ["draft","awaiting_approval","paused"].includes(m.status)?button(PL.ui("Approve / resume exact plan"),async()=>{const note=await PL.prompt(PL.ui("Review permissions, engines, API billing and limits"),PL.ui("Approval note"),"");if(note){await PL.post(url+"/approve",{plan_digest:m.payload.plan_digest,note});await R.open("monitor");}}):null,
        ["queued","scheduled","running"].includes(m.status)?button(PL.ui("Pause"),async()=>{const note=await PL.prompt(PL.ui("Pause after current bounded work"),PL.ui("Pause note"),"");if(note){await PL.post(url+"/pause",{note});await R.open("monitor");}}):null,
        m.status==="awaiting_review"?button(PL.ui("Complete human review"),async()=>{const note=await PL.prompt(PL.ui("Mission completion is separate from approving scientific claims"),PL.ui("Review note"),"");if(note){await PL.post(url+"/review",{note});await R.open("monitor");}}):null,
        h("a.btn.sm",{href:url+"/report",target:"_blank",rel:"noopener"},PL.ui("Evidence report bundle")),button(PL.ui("Cancel"),async()=>{await PL.post(url+"/cancel");await R.open("monitor");})));
    }
  }
  async function renderTeams(body,revision) {
    const [settings,result]=await Promise.all([PL.get("/api/research/os-settings"),PL.get(base()+"/missions")]);if(revision!==epoch)return;
    const template=select([["adaptive",PL.ui("Adaptive minimal team")],["single",PL.ui("Single worker + required verifier")],["fixed",PL.ui("Fixed team template")]],"adaptive");
    body.append(h("p.muted",{},PL.ui("Logical bounded roles on the existing worker; one task at a time. Suggested roles are not running model processes. Source text cannot grant permissions.")),template,
      button(settings.team_enabled?PL.ui("Disable teams"):PL.ui("Enable experimental teams"),async()=>{await PL.put("/api/research/os-settings",{enabled:settings.enabled,team_enabled:!settings.team_enabled});await R.open("teams");}),
      button(PL.ui("Propose team"),()=>R.editContract(PL.ui("Mission to compose"),{topic_id:R.tid,objective:"Inspect and report selected evidence",permissions:["workspace_write"],control:{success_criteria:["Scoped evidence report"],end_date:new Date(Date.now()+86400000).toISOString()},tasks:[{id:"inspect",capability:"paper.inspect",args:{paper_ids:R.sources().filter(s=>s.startsWith("paper:")).map(s=>s.slice(6))}},{id:"report",capability:"mission.report",depends_on:["inspect"]}]},async spec=>{
        const proposal=await PL.post("/api/research/teams/propose?mode="+template.value,spec);
        // Open the editable proposal after closing the first modal.
        setTimeout(()=>R.editContract(PL.ui("Review roles, permissions and assignments"),proposal.spec,async edited=>{const draft=await PL.post(base()+"/missions",edited);await R.open("monitor");return draft;}),0);return proposal;
      })),button(PL.ui("Capability evidence"),async()=>{const registry=await PL.get("/api/research/team-capabilities");PL.modal({title:PL.ui("Registered capabilities and observed outcomes"),body:h("pre",{},JSON.stringify(registry,null,2)),actions:[{label:PL.ui("Close")}]});}),button(PL.ui("Refresh"),()=>R.open("teams")));
    for(const m of result.missions.filter(m=>m.payload.spec.team)) {
      const team=m.payload.spec.team;
      body.append(h("article.research-card",{},h("b",{},m.payload.spec.objective+" · "+PL.ui(m.status)+" · "+team.mode),h("p",{},m.payload.blocking_reason||PL.ui("No reported blocker")),
        ...team.agents.map(role=>h("details",{},h("summary",{},role.id+PL.ui(" · logical role · ")+role.purpose),h("pre",{},JSON.stringify(role,null,2)))),
        ...team.assignments.map(a=>h("p",{},a.task_id+" → "+a.owner+(a.verifier?PL.ui(" · verifier ")+a.verifier:"")+" · "+((m.tasks.find(t=>t.id===a.task_id)||{}).status||"planned"))),
        button(PL.ui("Inspect handoffs and usage"),async()=>{const data=await PL.get(base()+"/missions/"+m.id+"/team");PL.modal({title:PL.ui("Durable task envelopes and execution records"),body:h("pre",{},JSON.stringify(data,null,2)),actions:[{label:PL.ui("Close")}]});}),
        button(PL.ui("Mission approvals / pause / review"),()=>R.open("monitor")),
        ["failed","paused"].includes(m.status)?button(PL.ui("Propose bounded reassignment"),()=>R.editContract(PL.ui("Reassign only known failed work"),{task_id:(m.tasks.find(t=>t.status==="failed")||{}).id||"",engine:"app",note:""},async body=>{const draft=await PL.post(base()+"/missions/"+m.id+"/replan",body);await R.open("monitor");return draft;})):null));
    }
  }
  async function renderWorkstreams(body,revision) {
    const [settings,result]=await Promise.all([PL.get("/api/research/os-settings"),PL.get(base()+"/missions")]);if(revision!==epoch)return;
    body.append(h("p.muted",{},PL.ui("Subordinate workstreams share the existing bounded worker. Cross-topic execution is isolated. Handoffs have source hashes and receipts; disagreements require a recorded PI decision.")),
      button(settings.multi_team_enabled?PL.ui("Disable multi-team"):PL.ui("Enable experimental multi-team"),async()=>{await PL.put("/api/research/os-settings",{enabled:settings.enabled,team_enabled:settings.team_enabled,multi_team_enabled:!settings.multi_team_enabled});await R.open("workstreams");}),
      button(PL.ui("Propose workstreams"),()=>R.editContract(PL.ui("Partition a supervised Mission"),{topic_id:R.tid,objective:"Inspect evidence and report",permissions:["workspace_write"],control:{success_criteria:["Owned evidence and review"],end_date:new Date(Date.now()+86400000).toISOString()},tasks:[{id:"inspect",capability:"paper.inspect"},{id:"report",capability:"mission.report",depends_on:["inspect"]}]},async spec=>{
        const proposal=await PL.post("/api/research/workstreams/propose",spec);
        setTimeout(()=>R.editContract(PL.ui("Review team charters, handoffs and budgets"),proposal.spec,async edited=>{const draft=await PL.post(base()+"/missions",edited);await R.open("monitor");return draft;}),0);return proposal;
      })),button(PL.ui("Refresh"),()=>R.open("workstreams")));
    for(const m of result.missions.filter(m=>m.payload.spec.collaboration)) {
      const url=base()+"/missions/"+m.id;
      const view=await PL.get(url+"/workstreams");if(revision!==epoch)return;
      body.append(h("article.research-card",{},h("b",{},m.payload.spec.objective+" · "+PL.ui(m.status)),h("p",{},m.payload.spec.collaboration.rationale),
        ...m.payload.spec.collaboration.workstreams.map(w=>h("details",{},h("summary",{},w.id+" · "+w.objective),h("pre",{},JSON.stringify({charter:w,usage:view.usage.find(u=>u.team_id===w.id),tasks:m.tasks.filter(t=>w.task_ids.includes(t.id)).map(t=>({id:t.id,status:t.status}))},null,2)))),
        h("p",{},PL.ui("Handoffs: ")+view.messages.length+PL.ui(" · receipts: ")+view.receipts.length+PL.ui(" · open disputes: ")+view.disputes.filter(d=>d.status==="open").length),
        h("details",{},h("summary",{},PL.ui("Evidence bundles, acknowledgments and output revisions")),h("pre",{},JSON.stringify({messages:view.messages,receipts:view.receipts,outputs:view.canonical_outputs},null,2))),
        ...view.disputes.map(d=>h("div.research-card",{},h("b",{},PL.ui(d.status)+" · "+d.payload.reason),h("pre",{},JSON.stringify(d.payload,null,2)),d.status==="open"?button(PL.ui("Resolve with PI note"),async()=>{const note=await PL.prompt(PL.ui("Resolution does not approve a scientific claim"),PL.ui("Human decision and follow-up"),"");if(note){await PL.post(url+"/disputes/"+d.id+"/resolve",{expected_revision:d.revision,note});await R.open("workstreams");}}):null)),
        button(PL.ui("Register canonical output"),()=>{const source=m.tasks.find(t=>t.payload&&t.payload.result&&t.payload.result.artifacts&&t.payload.result.artifacts.length);const owner=source&&m.payload.spec.collaboration.workstreams.find(w=>w.task_ids.includes(source.id));R.editContract(PL.ui("Compare-and-swap output reference"),{team_id:owner?owner.id:"",key:"research-report",source_task:source?source.id:"report",artifact_index:0,expected_revision:0,note:""},async body=>{const output=await PL.post(url+"/outputs",body);await R.open("workstreams");return output;});}),
        button(PL.ui("Mission approvals / pause / review"),()=>R.open("monitor")),h("a.btn.sm",{href:url+"/report",target:"_blank",rel:"noopener"},PL.ui("Mission evidence"))));
    }
  }
  async function renderProtocols(body,revision) {
    body.append(h("p.muted",{},PL.ui("Fixed protocol → human approval → mission draft → approve mission. CPU toy benchmark; no GPU or paid inference.")),button(PL.ui("New protocol revision"),()=>{
      const text=h("textarea.input",{rows:16,"aria-label":PL.ui("Experiment protocol JSON")},JSON.stringify({topic_id:R.tid,hypothesis:"Smoothing reduces Gaussian noise in generated smooth images",seeds:[11,23,37],alphas:[0.5,1.0],max_trials:6,max_seconds:120},null,2));
      PL.modal({title:PL.ui("Pre-register scientific intent & budgets"),body:text,actions:[{label:PL.ui("Cancel")},{label:PL.ui("Create immutable protocol"),kind:"accent",onClick:async()=>{const r=await PL.safe(()=>PL.post(base()+"/protocols",JSON.parse(text.value)));if(!r)return false;await R.open("protocols");return true;}}]});
    }),button(PL.ui("Refresh"),()=>R.open("protocols")));
    const r=await PL.get(base()+"/protocols");if(revision!==epoch)return;
    for(const p of r.protocols)body.append(h("article.research-card",{},h("b",{},p.payload.spec.hypothesis+PL.ui(" · revision ")+p.revision),h("pre",{},JSON.stringify(p.payload,null,2)),
      button(PL.ui("Approve fixed protocol"),async()=>{const note=await PL.prompt(PL.ui("Protocol approval"),PL.ui("Review splits, metrics, baseline, CPU/time/storage limits"),"");if(note){await PL.post(base()+"/protocols/"+p.id+"/approve",{digest:p.digest,note});await R.open("protocols");}}),
      p.approval?button(PL.ui("Prepare execution mission"),async()=>{await PL.post(base()+"/protocols/"+p.id+"/mission");await R.open("missions");}):null));
    for(const run of r.runs)body.append(h("details.research-card",{},h("summary",{},run.id+" · "+run.status+PL.ui(" · scientific review pending")),h("a.btn.sm",{href:base()+"/experiments/"+run.id+"/verification",target:"_blank",rel:"noopener"},PL.ui("Independent artifact checks")),h("pre",{},JSON.stringify(run.payload,null,2)),...run.trials.map(t=>h("details",{},h("summary",{},t.trial_key+" · "+PL.ui(t.status)),h("pre",{},JSON.stringify(t.payload,null,2))))));
  }
  async function renderClaims(body,revision) {
    body.append(h("p.muted",{},PL.ui("Source claim ≠ measurement ≠ interpretation ≠ human decision. Checks do not guarantee correctness or novelty.")),
      button(PL.ui("Propose claim"),()=>{
        const text=h("textarea.input",{rows:14,"aria-label":PL.ui("Claim JSON")},JSON.stringify({text:"Pending scientific claim",kind:"source_claim",evidence:R.sources().map(source_id=>({source_id,quote:""}))},null,2));
        PL.modal({title:PL.ui("Claim with exact evidence IDs / quotes"),body:text,actions:[{label:PL.ui("Cancel")},{label:PL.ui("Propose (not approve)"),kind:"accent",onClick:async()=>{const r=await PL.safe(()=>PL.post(base()+"/claims",JSON.parse(text.value)));if(!r)return false;await R.open("claims");return true;}}]});
      }),button(PL.ui("Resolve DOI · network"),async()=>{const doi=await PL.prompt(PL.ui("Authorize Crossref metadata lookup"),PL.ui("One network lookup; metadata does not certify scientific correctness"),"");if(doi){await PL.post(base()+"/citations/resolve",{doi,allow_network:true});await R.open("claims");}}),button(PL.ui("Refresh"),()=>R.open("claims")),h("a.btn.sm",{href:base()+"/claims/export",download:"scientific-review.md"},PL.ui("Export claim statuses")),button(PL.ui("Audit"),async()=>{const r=await PL.get(base()+"/audit");PL.modal({title:r.project_chain_valid?PL.ui("Audit chain valid"):PL.ui("Audit discrepancy"),body:h("pre",{},JSON.stringify(r,null,2)),actions:[{label:PL.ui("Close")}]});}));
    const r=await PL.get(base()+"/claims");if(revision!==epoch)return;
    for(const c of r.claims)body.append(h("article.research-card",{},h("div.claim-evidence-grid",{},h("section",{},h("b",{},PL.ui(c.status)+" · "+PL.ui(c.payload.kind)),h("p",{},c.payload.text),
      button(PL.ui("Use in chat"),()=>R.toggle("claim:"+c.id,PL.ui("Claim · ")+PL.ui(c.status),true))),h("section",{},
      ...c.evidence.map(e=>{const p=e.payload.provenance;return h("details",{},h("summary",{},PL.ui("Source ")+e.payload.source_id),p&&p.paper_id?h("a.btn.sm",{href:base()+"/papers/"+p.paper_id+"/pdf/"+p.version_id+"#page="+p.page,target:"_blank",rel:"noopener"},PL.ui("Open source page")):null,e.payload.source_id.startsWith("experiment:")?h("a.btn.sm",{href:base()+"/experiments/"+e.payload.source_id.slice(11)+"/verification",target:"_blank",rel:"noopener"},PL.ui("Verify measured artifacts")):null,h("pre",{},JSON.stringify(e.payload,null,2)));}),
      ...c.checks.slice(0,1).map(v=>h("details",{},h("summary",{},PL.ui("Independent checks: ")+PL.ui(v.outcome)),h("pre",{},JSON.stringify(v,null,2)))))),
      !["rejected","retracted"].includes(c.status)?button(PL.ui("Check evidence"),async()=>{await PL.post(base()+"/claims/"+c.id+"/check");await R.open("claims");}):null,
      ...["approve","contest","reject","retract","reopen"].map(action=>button(PL.ui(action),async()=>{const note=await PL.prompt(PL.ui("Human scientific decision: ")+action,PL.ui("Review evidence, discrepancies, limitations and uncertainty"),"");if(note){await PL.post(base()+"/claims/"+c.id+"/decision",{action,note});await R.open("claims");}}))));
  }
  R.command = function (text) {
    const match = /^\/([\w-]+)(?:\s.*)?$/.exec(text);
    const action = match && R.actions.find(a => a.name === match[1]);
    if (!action) return false;
    PL.safe(() => R.dispatch(action)); return true;
  };
  PL.on("research.", (event) => {
    const panel = PL.store.get("panel", null);
    if (panel && panel.kind === "research" && panel.arg === "jobs" && !PL.$("#panel").hidden &&
        (!PL.state || !PL.state.project || event.project_dir === PL.state.project.data_dir)) R.open("jobs");
  });
})(window);
