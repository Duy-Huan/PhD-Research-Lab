/* Topic research workspace: deterministic actions use the existing panel and API; AI starts only via chat Send. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const R = PL.research = { tid: "", topics: [], selected: new Map(), actions: [], query: "", offset: 0 };
  let epoch = 0, request = null, timer = 0;
  const tr = (vi, en) => PL.lang === "en" ? en : vi;
  const button = (label, run, cls) => h("button.btn.sm" + (cls ? "." + cls : ""), { type: "button", onclick: () => PL.safe(run) }, label);
  const label = (name, input) => h("label.field", {}, h("span", {}, name), input);
  const input = (value, attrs) => h("input.input", Object.assign({ value: value == null ? "" : String(value) }, attrs || {}));
  const select = (items, value) => h("select.input", {}, items.map(([id, name]) => h("option", { value: id, selected: String(value) === String(id) || null }, name)));
  const base = () => "/api/research/topics/" + encodeURIComponent(R.tid);
  const topic = () => R.topics.find(t => t.id === R.tid);

  R.reset = function () { R.tid = ""; R.topics = []; R.selected.clear(); R.query = ""; if (PL.chat) PL.chat.atts = []; epoch++; if (request) request.abort(); R.chips(); };
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
    if (t) t.textContent = R.tid ? (topic() || {}).title || tr("Topic đang mở", "Active Topic") : tr("Topic · Dự án", "Topic · Project");
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
    const nav = h("div.research-nav", {}, [["papers", tr("Paper", "Papers")], ["topics", "Topics"], ["workspaces", "Workspaces"], ["artifacts", tr("Nguồn gốc", "Provenance")], ["jobs", "Jobs"]]
      .concat([["missions", "Missions"],["protocols","Experiments"],["claims","Review Room"]]).map(([key, title]) => button(title, () => R.open(key), key === mode ? "accent" : "ghost")));
    const body = h("div.research-body", { dataset: { mode } });
    PL.panels.open(tr("Không gian nghiên cứu", "Research workspace"), h("div", {}, nav, body), { kind: "research", arg: mode });
    body.append(h("p.muted", {}, tr("Đang tải…", "Loading…")));
    return body;
  }
  R.open = async function (mode) {
    mode = mode || "papers";
    if (mode === "papers" && R.flags && R.flags.paper_explorer_v2 === false) { PL.toast("Paper Explorer is disabled in UI settings"); return; }
    const body = shell(mode), revision = epoch;
    try {
      await loadTopics();
      if (revision !== epoch) return;
      body.replaceChildren();
      if (mode === "topics") return renderTopics(body);
      if (!R.tid) { body.append(h("p", {}, tr("Chọn hoặc tạo Topic trước.", "Choose or create a Topic first.")), button("Topics", () => R.open("topics"))); return; }
      body.append(h("p.research-context", {}, (topic() || {}).title || R.tid));
      if (mode === "papers") await renderPapers(body, revision);
      else if (mode === "workspaces") await renderWorkspaces(body, revision);
      else if (mode === "artifacts") await renderArtifacts(body, revision);
      else if (mode === "jobs") await renderJobs(body, revision);
      else if (mode === "missions") await renderMissions(body, revision);
      else if (mode === "protocols") await renderProtocols(body, revision);
      else if (mode === "claims") await renderClaims(body, revision);
    } catch (e) { if (revision === epoch) { body.replaceChildren(h("p.error", {}, e.message), button(tr("Thử lại", "Retry"), () => R.open(mode))); } }
  };

  function renderTopics(body) {
    body.append(button(tr("＋ Topic mới", "＋ New Topic"), () => editTopic(null)), button(tr("Chat toàn dự án", "Project chat"), () => R.switchTopic("")));
    for (const t of R.topics) {
      const schedule = (R.schedules || {})[t.id] || {};
      const card = h("article.research-card", {}, h("b", {}, t.title), h("p.muted", {}, t.objectives || t.description),
        h("p.muted", {}, `${t.sources.join(", ")} · ${t.cadence} · ${t.enabled ? "enabled" : "paused"} · ≤${t.pdf_limit} PDFs/run`),
        h("p.muted", {}, `Last: ${schedule.last_run || "—"} ${schedule.last_status || ""} · Next: ${schedule.next_run || "—"} (UTC)`),
        h("div.row.wrap", {}, button(tr("Mở Topic", "Open Topic"), () => R.switchTopic(t.id)), button(tr("Sửa", "Edit"), () => editTopic(t)),
          (!R.flags || R.flags.topic_scheduler_ui !== false) ? button(t.enabled ? tr("Tạm dừng", "Pause") : tr("Bật lịch", "Enable schedule"), async () => {
            const { id, created, updated, ...data } = t;
            await PL.put("/api/research/topics/" + id, { ...data, enabled: !t.enabled }); await R.open("topics");
          }) : null));
      body.append(card);
    }
    body.append(button(tr("Tình trạng tích hợp local", "Local integration status"), async () => {
      const r = await PL.get("/api/research/capabilities");
      PL.modal({ title: "Optional integrations", body: h("div", {}, ...r.plugins.map(p => h("p", {}, `${p.id} · ${p.version || "not installed"} · ${p.status}`)), h("p.muted", {}, r.retrieval)), actions: [{ label: "Close" }] });
    }));
    if (!R.topics.length) body.append(h("p.muted", {}, tr("Chưa có Topic. Thư viện và chat cũ vẫn ở cấp dự án.", "No Topics yet. Existing library and chats remain at project level.")));
  }
  function editTopic(t) {
    const title = input(t && t.title), objectives = h("textarea.input", { rows: 3 }, t && t.objectives || "");
    const keywords = input((t && t.keywords || []).join("; ")), synonyms = input((t && t.synonyms || []).join("; ")), exclusions = input((t && t.exclusions || []).join("; "));
    const cadence = select([["manual", "Manual"], ["off", "Off"], ["daily", "Daily (UTC)"], ["weekly", "Weekly (UTC)"]], t && t.cadence || "manual");
    const providers = input((t && t.sources || ["openalex", "arxiv", "semantic_scholar", "crossref"]).join("; "));
    const pdf = input(t ? t.pdf_limit : 10, { type: "number", min: 0, max: 25 }), storage = input(t ? t.storage_mb : 1024, { type: "number", min: 1 });
    const metadata = input(t ? t.metadata_limit : 30, { type: "number", min: 1, max: 100 }), size = input(t ? t.max_pdf_mb : 25, { type: "number", min: 1, max: 30 });
    const year = input(t ? t.min_year : 2019, { type: "number", min: 1900, max: 2100 });
    const auto = input("", { type: "checkbox", checked: t && t.auto_download || null }), enabled = input("", { type: "checkbox", checked: t && t.enabled || null });
    const parser = select([["existing", "Existing PDF parser (default)"], ["docling", "Docling (optional local artifacts required)"]], t && t.parser || "existing");
    if (R.flags && R.flags.topic_scheduler_ui === false) { cadence.disabled = true; enabled.disabled = true; }
    PL.modal({ title: t ? tr("Sửa Topic", "Edit Topic") : tr("Topic mới", "New Topic"), body: h("div", {}, label("Title", title), label("Objectives", objectives),
      label("Keywords (;)", keywords), label("Synonyms (;)", synonyms), label("Exclusions (;)", exclusions), label("Sources (;): openalex, arxiv, semantic_scholar, crossref", providers),
      label("From year", year), label("Cadence", cadence), label("Schedule enabled", enabled), label("Metadata/run", metadata), label("PDFs/run", pdf), label("MB/PDF", size), label("Storage MB/topic", storage), label("Auto-download eligible OA", auto), label("Parser", parser)),
      actions: [{ label: tr("Huỷ", "Cancel") }, { label: tr("Lưu", "Save"), kind: "accent", onClick: async () => {
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
    const controls = h("div.research-filters"), results = h("div"), q = input(R.query, { type: "search", placeholder: tr("Tìm paper trong Topic…", "Search Topic papers…"), "aria-label": "Search Topic papers" });
    const level = select([["-1", "L0–L4"], ...[0, 1, 2, 3, 4].map(n => [n, "L" + n])], -1);
    const state = select([["", "All"], ...(!R.flags || R.flags.discovery_inbox !== false ? [["candidate", "Discovery Inbox"]] : []), ["accepted", "Accepted"], ["dismissed", "Dismissed"], ["deferred", "Deferred"]], "");
    const year = input("", { type: "number", placeholder: "From year", "aria-label": "From year" }), source = input("", { placeholder: "Source", "aria-label": "Source" });
    const sort = select([["relevance", "Lexical matches"], ["year", "Year"]], "relevance"), oa = input("", { type: "checkbox", "aria-label": "Open access only" });
    controls.append(q, level, state, year, source, sort, label("OA", oa));
    body.append(controls, h("div.row.wrap", {}, button(tr("Khám phá ngay", "Discover now"), async () => { await PL.post(base() + "/discover"); await R.open("jobs"); }),
      button("Dry run", async () => { await PL.post(base() + "/discover", { dry_run: true }); await R.open("jobs"); }),
      button(tr("Nhập thư viện cũ", "Import existing library"), async () => { await PL.post(base() + "/papers/import-library"); await load(); }),
      button(tr("Nhập Zotero JSON", "Import Zotero JSON"), () => importZotero())), results);
    const bulk = h("div.row.wrap.research-bulk", {}, ...[["accept", tr("Chấp nhận", "Accept")], ["defer", "Defer"], ["dismiss", "Dismiss"], ["download", "OA PDF"], ["screen", "L3 screen"], ["verify", "L4 attest"]].map(([action, name]) => button(name, async () => {
      const ids = R.sources().filter(id => id.startsWith("paper:")).map(id => id.slice(6));
      if (!ids.length) { PL.toast(tr("Chọn paper trước", "Select papers first")); return; }
      let note = "";
      if (action === "verify") { note = await PL.prompt("L4 · User attestation", "Review note (not a universal validity guarantee)", ""); if (!note) return; }
      if (action === "dismiss" && !(await PL.confirm("Dismiss selected candidates? They remain recoverable in Dismissed."))) return;
      await PL.post(base() + "/papers/bulk", { action, paper_ids: ids, note });
      if (action === "download") await R.open("jobs"); else await load();
    })), button(tr("Thêm vào Topic khác", "Add to another Topic"), async () => {
      const target = await PL.prompt("Target Topic", R.topics.map(t => t.title + " = " + t.id).join("\n"), "");
      if (target) await PL.post(base() + "/papers/bulk", { action: "associate", target_topic_id: target, paper_ids: R.sources().filter(s => s.startsWith("paper:")).map(s => s.slice(6)) });
    }), button(tr("So sánh với AI", "Compare with AI"), () => R.ai("compare")), button(tr("Phản biện với AI", "Review with AI"), () => R.ai("review")),
      h("a.btn.sm", { href: base() + "/bibliography", download: "topic-references.bib" }, "BibTeX · accepted only"));
    body.insertBefore(bulk, results);
    let serial = 0;
    async function load() {
      const seq = ++serial;
      if (request) request.abort(); request = new W.AbortController();
      const params = new W.URLSearchParams({ q: q.value, level: level.value, state: state.value, year: year.value || 0, source: source.value, sort: sort.value, oa: String(oa.checked), offset: R.offset, limit: 25 });
      try {
        const r = await PL.api("GET", base() + "/papers?" + params, undefined, { signal: request.signal });
        if (revision !== epoch || seq !== serial) return;
        results.replaceChildren(h("p.muted", {}, `${r.total} papers · ${R.offset + 1}–${Math.min(R.offset + 25, r.total)}`));
        if (!r.papers.length) results.append(h("p", {}, tr("Chưa có kết quả. Khám phá hoặc nhập metadata.", "No results. Discover or import metadata.")));
        for (const p of r.papers) {
          const checkbox = input("", { type: "checkbox", checked: R.selected.has("paper:" + p.id) || null, "aria-label": "Select " + p.title });
          checkbox.onchange = () => R.toggle("paper:" + p.id, p.title, checkbox.checked);
          results.append(h("article.research-card", {}, h("label.row", {}, checkbox, h("b", {}, p.title)), h("p.muted", {}, `${p.year || "?"} · ${p.venue || "unknown venue"} · ${p.sources.join(", ")}`),
            h("div.row.wrap", {}, h("span.chip", {}, "L" + p.level), h("span.chip", {}, p.state), h("span.chip", {}, p.oa_locations.length ? "OA candidate" : "Metadata only"), ...p.flags.map(f => h("span.chip.warn", {}, f))),
            h("p.muted", {}, "Matched terms: " + (p.association.matched_terms || []).join(", ")),
            p.association.review_reset ? h("p.muted", {}, "Review reset: " + p.association.review_reset.reason) : null,
            button(tr("Phiên bản & bằng chứng", "Versions & evidence"), () => paperDetail(p))));
        }
        results.append(h("div.row", {}, button("←", async () => { R.offset = Math.max(0, R.offset - 25); await load(); }), button("→", async () => { if (R.offset + 25 < r.total) { R.offset += 25; await load(); } })));
      } catch (e) { if (e.name !== "AbortError" && revision === epoch) results.replaceChildren(h("p.error", {}, e.message)); }
    }
    q.oninput = () => { R.query = q.value; R.offset = 0; W.clearTimeout(timer); timer = W.setTimeout(load, 250); };
    for (const x of [level, state, year, source, sort, oa]) x.onchange = () => { R.offset = 0; load(); };
    await load();
  }
  function paperDetail(p) {
    const body = h("div", {}, h("p", {}, p.abstract || "Abstract unavailable"), h("p.muted", {}, "DOI: " + (p.doi || "unknown")));
    for (const v of p.versions) {
      body.append(h("p", {}, `${v.id} · ${v.source} · ${v.version}`));
      if (v.document) body.append(h("p.muted", {}, v.document.status + " · " + v.document.sha256), h("a.btn.sm", { href: base() + `/papers/${p.id}/pdf/${v.id}`, target: "_blank", rel: "noopener" }, "Open PDF"));
      else body.append(h("p.muted", {}, "Full text unavailable for this version"));
    }
    const search = input("", { placeholder: "Find page evidence", "aria-label": "Find page evidence" }), evidence = h("div");
    body.append(search, button("Evidence", async () => { const r = await PL.get(base() + "/evidence?q=" + encodeURIComponent(search.value)); evidence.replaceChildren(); for (const e of r.evidence.filter(e => e.paper_id === p.id)) evidence.append(h("p", {}, `[${e.id}] v${e.version_id} p.${e.page}: ${e.text}`)); }), evidence);
    PL.modal({ title: p.title, body, actions: [{ label: tr("Đóng", "Close") }] });
  }
  function importZotero() {
    const file = h("input", { type: "file", accept: ".json,application/json", onchange: async () => {
      if (!file.files[0]) return;
      await PL.safe(async () => { await PL.upload(base() + "/zotero/import", file.files[0]); await R.open("papers"); });
    } }); file.click();
  }
  R.ai = function (skill) {
    if (R.flags && R.flags.contextual_actions === false) { PL.toast("Contextual AI actions are disabled"); return; }
    if (!R.selected.size) { PL.toast(tr("Chọn nguồn trước", "Select sources first")); return; }
    PL.chat.setInput("/" + skill + " " + tr("Phân tích các nguồn đã chọn; dẫn ID, phiên bản và trang khi có. Nêu rõ điều chưa kiểm chứng.", "Analyze the selected sources; cite IDs, versions and pages when available. State what is unverified."));
    PL.$("#input").focus();
  };

  async function renderWorkspaces(body, revision) {
    body.append(h("p.muted", {}, tr("Chỉ đồng bộ file đã lưu; không đọc được toàn bộ phiên, suy luận riêng hoặc hoạt động chưa lưu của engine.", "Only saved files are observable; full external sessions, private reasoning and unsaved activity are not captured.")),
      button(tr("＋ Tạo / liên kết workspace", "＋ Create / link workspace"), () => {
        const engine = select([["openscience", "OpenScience"], ["feynman", "Feynman"]], "openscience"), path = input("", { placeholder: "Empty = managed folder; otherwise absolute existing folder" }), interval = input(0, { type: "number", min: 0 });
        PL.modal({ title: "Engine workspace", body: h("div", {}, label("Engine", engine), label("Path", path), label("Sync interval minutes (0 = manual)", interval)), actions: [{ label: "Cancel" }, { label: "Link", kind: "accent", onClick: async () => {
          const result = await PL.safe(() => PL.post(base() + "/workspaces", { engine: engine.value, path: path.value, sync_interval_minutes: Number(interval.value) }));
          if (!result) return false; await R.open("workspaces"); return true;
        } }] });
      }));
    const r = await PL.get(base() + "/workspaces"); if (revision !== epoch) return;
    for (const w of r.workspaces) body.append(h("article.research-card", {}, h("b", {}, w.engine), h("p.research-path", {}, w.path),
      h("p.muted", {}, `${w.capabilities.binary_available ? "CLI found" : "CLI missing"} · ${w.artifact_count} artifacts · ${w.checkpoint ? w.checkpoint.status + " / " + w.checkpoint.at : "Never synced"}`),
      w.checkpoint && w.checkpoint.error ? h("p.error", {}, w.checkpoint.error) : null,
      h("div.row.wrap", {}, button("Open " + w.engine, async () => {
        const result = await PL.post("/api/research/workspaces/" + w.id + "/open");
        PL.modal({ title: result.status, body: h("div", {}, h("p", {}, result.detail || result.status), result.command ? h("pre", {}, result.command) : null, result.log ? h("p", {}, result.log) : null), actions: [{ label: "Close" }] });
      }), button("Sync Now", async () => { await PL.post("/api/research/workspaces/" + w.id + "/sync"); await R.open("jobs"); }), button("View changes", () => R.open("artifacts")),
      button("Relink / schedule", () => {
        const path = input(w.path), interval = input(w.sync_interval_minutes || 0, { type: "number", min: 0 });
        PL.modal({ title: "Relink workspace (no files moved)", body: h("div", {}, label("Existing folder", path), label("Sync interval minutes (0 = manual)", interval)), actions: [{ label: "Cancel" }, { label: "Save", kind: "accent", onClick: async () => {
          const r = await PL.safe(() => PL.put("/api/research/workspaces/" + w.id, { engine: w.engine, path: path.value, sync_interval_minutes: Number(interval.value) }));
          if (!r) return false; await R.open("workspaces"); return true;
        } }] });
      })),
      w.checkpoint ? h("details", {}, h("summary", {}, "Sync transparency report"), h("pre", {}, JSON.stringify(w.checkpoint, null, 2))) : null));
    if (!r.workspaces.length) body.append(h("p.muted", {}, "No workspaces linked"));
  }
  async function renderArtifacts(body, revision) {
    const [a, p, findings] = await Promise.all([PL.get(base() + "/artifacts?history=true"), PL.get(base() + "/provenance"), PL.get(base() + "/findings")]);
    if (revision !== epoch) return;
    const filter = input("", { placeholder: "Filter artifact / engine", "aria-label": "Filter artifact / engine" }), list = h("div");
    body.append(filter, button("Review with AI", () => R.ai("review")), button("Propose finding", async () => {
      const text = await PL.prompt("Finding proposal", "Claim linked to selected evidence; pending human review", "");
      if (text) { await PL.post(base() + "/findings", { text, source_evidence_ids: R.sources() }); await R.open("artifacts"); }
    }), list);
    function paint() {
      list.replaceChildren();
      for (const x of a.artifacts.filter(x => (x.path + " " + x.engine).toLowerCase().includes(filter.value.toLowerCase()))) {
        const checkbox = input("", { type: "checkbox", checked: R.selected.has("artifact:" + x.id) || null, "aria-label": "Select artifact " + x.path });
        checkbox.onchange = () => R.toggle("artifact:" + x.id, x.path + " v" + x.version, checkbox.checked);
        list.append(h("article.research-card", {}, h("label.row", {}, checkbox, h("b", {}, x.path)), h("p.muted", {}, `${x.engine} · v${x.version} · ${x.available ? "observed" : "unavailable / tombstone"} · ${x.bytes} bytes`), h("p.research-path", {}, x.sha256 || "Hash not computed: metadata only")));
      }
    }
    filter.oninput = paint; paint();
    for (const f of findings.findings) body.append(h("article.research-card", {}, h("b", {}, "Finding · " + f.status), h("p", {}, f.text), h("p.muted", {}, f.source_evidence_ids.join(", ")),
      f.status === "pending" ? h("div.row", {}, ...[true, false].map(approve => button(approve ? "Approve" : "Reject", async () => {
        const note = await PL.prompt("Human review", "Review note", ""); if (!note) return;
        await PL.post(base() + "/findings/" + f.id + "/review", { approve, note }); await R.open("artifacts");
      }))) : null));
    body.append(h("h3", {}, "Provenance timeline"));
    for (const e of p.events) body.append(h("details.research-card", {}, h("summary", {}, e.type + " · " + e.observed), h("pre", {}, JSON.stringify(e.payload, null, 2))));
  }
  async function renderJobs(body, revision) {
    body.append(button(tr("Làm mới", "Refresh"), () => R.open("jobs")));
    const r = await PL.get("/api/research/jobs?topic_id=" + R.tid); if (revision !== epoch) return;
    if (!r.jobs.length) body.append(h("p.muted", {}, "No jobs"));
    for (const j of r.jobs) body.append(h("article.research-card", {}, h("b", {}, j.kind + " · " + j.status), h("p.muted", {}, j.updated),
      h("pre", {}, JSON.stringify(j.payload.result || { error: j.payload.error || "", ...j.payload }, null, 2)),
      ["queued", "running"].includes(j.status) ? button("Cancel", async () => { await PL.post("/api/research/jobs/" + j.id + "/cancel"); await R.open("jobs"); }) : null,
      ["failed", "partial", "interrupted", "cancelled"].includes(j.status) ? button("Retry", async () => { await PL.post("/api/research/jobs/" + j.id + "/retry"); await R.open("jobs"); }) : null));
  }
  R.dispatch = async function (action) {
    const view = action.route_or_component_key;
    if (action.availability !== "available") { PL.toast("Action unavailable"); return; }
    if (view === "library") return PL.panels.library();
    if (view === "settings") return PL.settings.open();
    if (["papers", "topics", "workspaces", "artifacts", "jobs", "missions", "protocols", "claims"].includes(view)) return R.open(view);
    throw new Error("Unregistered UI component");
  };
  async function renderMissions(body, revision) {
    body.append(button("New mission / JSON plan", () => {
      const plan=h("textarea.input",{rows:16,"aria-label":"Mission JSON plan"},JSON.stringify({topic_id:R.tid,objective:"Inspect selected topic evidence",permissions:["workspace_write"],tasks:[{id:"inspect",capability:"paper.inspect",args:{paper_ids:R.sources().filter(s=>s.startsWith("paper:")).map(s=>s.slice(6)),limit:2}},{id:"report",capability:"mission.report",depends_on:["inspect"]}]},null,2));
      PL.modal({title:"Mission preview · creation does not execute",body:plan,actions:[{label:"Cancel"},{label:"Create draft",kind:"accent",onClick:async()=>{
        const r=await PL.safe(()=>PL.post(base()+"/missions",JSON.parse(plan.value)));if(!r)return false;await R.open("missions");return true;
      }}]});
    }),button("Draft with AI · one call",async()=>{const objective=await PL.prompt("AI planning uses the configured provider","One reasoning/network call creates a draft; it cannot approve execution","");if(objective){await PL.post(base()+"/missions/plan",{objective,allow_reasoning:true});await R.open("missions");}}),button("Refresh",()=>R.open("missions")));
    const result=await PL.get(base()+"/missions");if(revision!==epoch)return;
    for(const m of result.missions)body.append(h("article.research-card",{},h("b",{},m.payload.spec.objective+" · "+m.status),
      h("p.muted",{},"Permissions: "+m.payload.spec.permissions.join(", ")+" · reasoning calls "+m.payload.reasoning_calls+" · "+m.payload.active_seconds.toFixed(2)+"s"),
      h("details",{},h("summary",{},"Review immutable plan & limits"),h("pre",{},JSON.stringify(m.payload.spec,null,2))),
      ...m.tasks.map(t=>h("details",{},h("summary",{},t.id+" · "+t.status),h("pre",{},JSON.stringify(t.payload,null,2)),["failed","interrupted"].includes(t.status)?button("Reconcile / retry task",async()=>{const reconcile_note=await PL.prompt("Retry requires fresh mission approval","Confirm known admission outcome; never repeat an uncertain external action blindly","");if(reconcile_note){await PL.post(base()+"/missions/"+m.id+"/retry",{task_id:t.id,reconcile_note});await R.open("missions");}}):null)),
      ["draft","paused","failed","interrupted"].includes(m.status)?button("Approve this plan",async()=>{const note=await PL.prompt("Approve exact plan","Review permissions, engine, limits and scientific intent","");if(note){await PL.post(base()+"/missions/"+m.id+"/approve",{plan_digest:m.payload.plan_digest,note});await R.open("missions");}}):null,
      button("Cancel",async()=>{await PL.post(base()+"/missions/"+m.id+"/cancel");await R.open("missions");})));
  }
  async function renderProtocols(body,revision) {
    body.append(h("p.muted",{},"Fixed protocol → human approval → mission draft → approve mission. CPU toy benchmark; no GPU or paid inference."),button("New protocol revision",()=>{
      const text=h("textarea.input",{rows:16,"aria-label":"Experiment protocol JSON"},JSON.stringify({topic_id:R.tid,hypothesis:"Smoothing reduces Gaussian noise in generated smooth images",seeds:[11,23,37],alphas:[0.5,1.0],max_trials:6,max_seconds:120},null,2));
      PL.modal({title:"Pre-register scientific intent & budgets",body:text,actions:[{label:"Cancel"},{label:"Create immutable protocol",kind:"accent",onClick:async()=>{const r=await PL.safe(()=>PL.post(base()+"/protocols",JSON.parse(text.value)));if(!r)return false;await R.open("protocols");return true;}}]});
    }),button("Refresh",()=>R.open("protocols")));
    const r=await PL.get(base()+"/protocols");if(revision!==epoch)return;
    for(const p of r.protocols)body.append(h("article.research-card",{},h("b",{},p.payload.spec.hypothesis+" · revision "+p.revision),h("pre",{},JSON.stringify(p.payload,null,2)),
      button("Approve fixed protocol",async()=>{const note=await PL.prompt("Protocol approval","Review splits, metrics, baseline, CPU/time/storage limits","");if(note){await PL.post(base()+"/protocols/"+p.id+"/approve",{digest:p.digest,note});await R.open("protocols");}}),
      p.approval?button("Prepare execution mission",async()=>{await PL.post(base()+"/protocols/"+p.id+"/mission");await R.open("missions");}):null));
    for(const run of r.runs)body.append(h("details.research-card",{},h("summary",{},run.id+" · "+run.status+" · scientific review pending"),h("a.btn.sm",{href:base()+"/experiments/"+run.id+"/verification",target:"_blank",rel:"noopener"},"Independent artifact checks"),h("pre",{},JSON.stringify(run.payload,null,2)),...run.trials.map(t=>h("details",{},h("summary",{},t.trial_key+" · "+t.status),h("pre",{},JSON.stringify(t.payload,null,2))))));
  }
  async function renderClaims(body,revision) {
    body.append(h("p.muted",{},"Source claim ≠ measurement ≠ interpretation ≠ human decision. Checks do not guarantee correctness or novelty."),
      button("Propose claim",()=>{
        const text=h("textarea.input",{rows:14,"aria-label":"Claim JSON"},JSON.stringify({text:"Pending scientific claim",kind:"source_claim",evidence:R.sources().map(source_id=>({source_id,quote:""}))},null,2));
        PL.modal({title:"Claim with exact evidence IDs / quotes",body:text,actions:[{label:"Cancel"},{label:"Propose (not approve)",kind:"accent",onClick:async()=>{const r=await PL.safe(()=>PL.post(base()+"/claims",JSON.parse(text.value)));if(!r)return false;await R.open("claims");return true;}}]});
      }),button("Resolve DOI · network",async()=>{const doi=await PL.prompt("Authorize Crossref metadata lookup","One network lookup; metadata does not certify scientific correctness","");if(doi){await PL.post(base()+"/citations/resolve",{doi,allow_network:true});await R.open("claims");}}),button("Refresh",()=>R.open("claims")),h("a.btn.sm",{href:base()+"/claims/export",download:"scientific-review.md"},"Export claim statuses"),button("Audit",async()=>{const r=await PL.get(base()+"/audit");PL.modal({title:r.project_chain_valid?"Audit chain valid":"Audit discrepancy",body:h("pre",{},JSON.stringify(r,null,2)),actions:[{label:"Close"}]});}));
    const r=await PL.get(base()+"/claims");if(revision!==epoch)return;
    for(const c of r.claims)body.append(h("article.research-card",{},h("div.claim-evidence-grid",{},h("section",{},h("b",{},c.status+" · "+c.payload.kind),h("p",{},c.payload.text),
      button("Use in chat",()=>R.toggle("claim:"+c.id,"Claim · "+c.status,true))),h("section",{},
      ...c.evidence.map(e=>{const p=e.payload.provenance;return h("details",{},h("summary",{},"Source "+e.payload.source_id),p&&p.paper_id?h("a.btn.sm",{href:base()+"/papers/"+p.paper_id+"/pdf/"+p.version_id+"#page="+p.page,target:"_blank",rel:"noopener"},"Open source page"):null,e.payload.source_id.startsWith("experiment:")?h("a.btn.sm",{href:base()+"/experiments/"+e.payload.source_id.slice(11)+"/verification",target:"_blank",rel:"noopener"},"Verify measured artifacts"):null,h("pre",{},JSON.stringify(e.payload,null,2)));}),
      ...c.checks.slice(0,1).map(v=>h("details",{},h("summary",{},"Independent checks: "+v.outcome),h("pre",{},JSON.stringify(v,null,2)))))),
      !["rejected","retracted"].includes(c.status)?button("Check evidence",async()=>{await PL.post(base()+"/claims/"+c.id+"/check");await R.open("claims");}):null,
      ...["approve","contest","reject","retract","reopen"].map(action=>button(action,async()=>{const note=await PL.prompt("Human scientific decision: "+action,"Review evidence, discrepancies, limitations and uncertainty","");if(note){await PL.post(base()+"/claims/"+c.id+"/decision",{action,note});await R.open("claims");}}))));
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
