/* PhD Research Lab — the side panel (opens next to the chat, Claude-style): run timeline, files, proposed files,
   the research outline (levels + attached proposal), the library and experiments in VS Code. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const P = (PL.panels = {});
  let stopLive = null;

  P.open = function (title, body, opts) {
    if (stopLive) { stopLive(); stopLive = null; }
    const panel = PL.$("#panel");
    PL.$("#panel-title").textContent = title;
    const acts = PL.$("#panel-actions");
    acts.innerHTML = "";
    (opts && opts.actions || []).forEach((a) => acts.append(a));
    const b = PL.$("#panel-body");
    b.innerHTML = "";
    if (body) b.append(body);
    panel.hidden = false;
    PL.store.set("panel", { kind: (opts && opts.kind) || "", arg: (opts && opts.arg) || "" });
    return b;
  };
  P.close = function () {
    if (stopLive) { stopLive(); stopLive = null; }
    PL.$("#panel").hidden = true;
    PL.store.set("panel", null);
  };
  // ------------------------------------------------------------------ research run: steps, timeline, outputs
  P.run = async function (rid) {
    const body = P.open("Run", h("div", {}, h("span.spin")), { kind: "run", arg: rid });
    let r;
    try { r = await PL.get("/api/runs/" + rid); } catch (e) { body.innerHTML = ""; body.append(h("p.muted", {}, e.message)); return; }
    PL.$("#panel-title").textContent = r.title;
    const paint = async () => {
      r = await PL.get("/api/runs/" + rid).catch(() => r);
      const ev = await PL.get(`/api/runs/${rid}/events`).catch(() => ({ events: [] }));
      body.innerHTML = "";
      body.append(h("div.row", {}, PL.statusChip(r.status), r.synthetic ? h("span.chip.warn", {}, "SYNTHETIC") : null,
        h("span.muted", { style: "font-size:12px" }, r.pipeline + " · " + PL.ago(r.created)), h("span.grow"),
        r.status === "APPROVAL_PENDING" ? h("button.btn.accent.sm", { type: "button", onclick: () => PL.runAct(r, "approve").then(paint) }, "Chấp nhận & chạy") : null,
        r.status === "NEEDS_USER_ACTION" ? h("button.btn.accent.sm", { type: "button", onclick: () => PL.runAct(r, "resume", { accept: true }).then(paint) }, "Tiếp tục") : null,
        !["COMPLETED", "CANCELLED"].includes(r.status) ? h("button.btn.sm", { type: "button", onclick: () => PL.runAct(r, "cancel").then(paint) }, "Huỷ") : null));
      if (r.next_decision || r.reason) body.append(h("p", {}, r.next_decision || r.reason));
      if (r.proposal && r.proposal.text) body.append(h("div.preview-box", {}, "Đề xuất phục hồi: " + r.proposal.text));
      body.append(h("div.section-h", {}, "Các bước"));
      const steps = h("ol.timeline");
      for (const s of r.steps) {
        const prov = h("select.input", { style: "width:auto;height:26px;padding:0 6px;font-size:12px", title: "Đổi provider cho bước này",
          disabled: ["done", "running"].includes(s.status) || null,
          onchange: async (e) => { await PL.safe(() => PL.post(`/api/runs/${rid}/provider`, { step: s.id, provider: e.target.value }), "Đã đổi provider"); paint(); } },
        ["app", "feynman", "claude_code", "codex", "gemini_cli", "antigravity", "python", "docker", "latex", "phdlab", "synthetic"]
          .filter((p, i, a) => a.indexOf(p) === i).map((p) => h("option", { value: p, selected: p === s.provider || null }, p)));
        steps.append(h("li." + (s.status === "pending" ? "pending" : s.status), {},
          h("div.row", {}, h("span.t.grow", {}, `${s.id} · ${s.label}`), prov),
          h("div.s", {}, `${s.status}${s.attempt > 1 ? " · lần " + s.attempt : ""}${s.resource ? " · " + s.resource : ""}${s.active_s ? " · " + s.active_s.toFixed(1) + " s" : ""}`),
          s.error ? h("div.err-line", {}, s.error) : null,
          (s.notes || []).length ? h("div.s", {}, s.notes.join(" · ")) : null,
          s.result && s.result.summary_line && !(s.notes || []).includes(s.result.summary_line) ? h("div.s", {}, s.result.summary_line) : null));
      }
      body.append(steps);
      if (r.outputs.length) {
        body.append(h("div.section-h", {}, "Kết quả"));
        body.append(h("div.list", {}, r.outputs.map((o) => h("div.li", { style: "cursor:pointer", onclick: () => P.file(o.path) },
          h("span", { html: PL.icon("file") }), h("div.m", {}, h("div.t", {}, o.path.split("/").pop()), h("div.s", {}, o.label))))));
      }
      const papers = P.runSources(r);
      if (papers.length) {
        body.append(h("div.section-h", {}, "Nguồn tìm được · lưu từng bài vào thư viện"),
          h("div", {}, papers.map((s) => P.paperCard(s))));
      }
      if (r.result && r.result.acceptance) {
        body.append(h("div.section-h", {}, "Nghiệm thu"));
        const t = h("table.grid", {}, h("tr", {}, h("th", {}, ""), h("th", {}, "Tiêu chí"), h("th", {}, "Kết luận")));
        r.result.acceptance.forEach((c) => t.append(h("tr", {}, h("td", {}, c.priority), h("td", {}, c.title), h("td", {}, h("span.chip" + (c.verdict === "PASS" ? ".ok" : c.verdict === "FAIL" ? ".err" : ".warn"), {}, c.verdict)))));
        body.append(t);
      }
      body.append(h("div.section-h", {}, "Dòng thời gian"));
      const tl = h("ol.timeline");
      for (const e of ev.events.slice(-120)) {
        const d = e.data || {};
        const cls = e.type === "step.completed" ? "done" : e.type === "step.failed" ? "failed" : e.type === "step.started" ? "running" : "state";
        let text = { "run.created": "Tạo run", "run.approved": "Bạn đã duyệt", "run.restart": "Máy chủ khởi động lại — khôi phục",
          "run.resumed": "Tiếp tục theo quyết định của bạn", "step.lost": "Tiến trình bị mất khi khởi động lại", "step.reattached": "Dùng lại kết quả job" }[e.type] || e.type;
        if (e.type === "step.provider") text = `Đổi provider ${d.step}: ${d.old} → ${d.new}` + (d.reason ? ` (${d.reason})` : "");
        if (e.type === "run.state") text = (PL.STATUS[d.status] || d.status) + (d.reason ? " — " + d.reason : "");
        else if (e.type === "step.started") text = `Bắt đầu ${d.step} · ${d.label} (${d.provider}, lần ${d.attempt})`;
        else if (e.type === "step.completed") text = `Xong ${d.step}${d.note ? " — " + d.note : ""}`;
        else if (e.type === "step.failed") text = `Lỗi ${d.step}: ${d.error}`;
        else if (e.type === "step.log") text = d.message;
        else if (e.type === "run.analysis") text = "Phân tích lỗi → " + ((d.proposal || {}).text || "");
        const li = h("li." + cls, {}, h("div", {}, text), h("div.s", {}, new Date(e.ts * 1000).toLocaleTimeString("vi-VN")));
        if (d.checkpoint) li.append(h("div.say", {}, h("b", {}, "Người dùng: "), d.user), h("div.say", {}, h("b", {}, "PhD Lab: "), d.assistant));
        tl.append(li);
      }
      body.append(tl);
    };
    await paint();
    stopLive = PL.on("run.", (e) => { if (e.run_id === rid) { W.clearTimeout(P._rt); P._rt = W.setTimeout(paint, 250); } });
  };

  // ------------------------------------------------------------------ files of the project
  P.file = async function (path) {
    const name = path.split("/").pop();
    const url = "/api/files?path=" + encodeURIComponent(path);
    const body = P.open(name, null, { kind: "file", arg: path, actions: [h("a.btn.sm.ghost", { href: url + "&download=1", title: "Tải về" }, h("span", { html: PL.icon("upload") }))] });
    const ext = (name.split(".").pop() || "").toLowerCase();
    if (ext === "pdf") { body.append(h("iframe.file-frame", { src: url, title: name })); return; }
    if (["png", "jpg", "jpeg", "svg", "gif", "webp"].includes(ext)) { body.append(h("img", { src: url, alt: name, style: "max-width:100%" })); return; }
    let text;
    try { const r = await W.fetch(url); if (!r.ok) throw new Error((await r.text()).slice(0, 200)); text = await r.text(); } catch (e) { body.append(h("p.muted", {}, e.message)); return; }
    if (ext === "md") body.append(PL.rich(h("div.prose"), text));
    else if (ext === "csv") body.append(csvTable(text));
    else if (ext === "json") { try { body.append(h("pre.preview-box.mono", { style: "max-height:none" }, JSON.stringify(JSON.parse(text), null, 2))); } catch (e) { body.append(h("pre.preview-box.mono", {}, text)); } }
    else body.append(h("pre.preview-box.mono", { style: "max-height:none" }, text));
  };
  function csvTable(text) {
    const rows = text.split(/\r?\n/).filter((l) => l && !l.startsWith("#")).slice(0, 500).map((l) => l.split(","));
    const t = h("table.grid");
    rows.forEach((r, i) => t.append(h("tr", {}, r.map((c) => h(i ? "td" : "th", {}, c)))));
    const note = text.split(/\r?\n/).filter((l) => l.startsWith("#")).join(" ");
    return h("div", {}, note ? h("p.chip.warn", {}, note.replace(/^#\s*/, "")) : null, t);
  }

  // ------------------------------------------------------------------ files proposed by a provider (artifacts)
  P.artifact = async function (sid, a, apply) {
    const body = P.open(a.path, h("span.spin"), { kind: "artifact" });
    try {
      const d = await PL.get(`/api/chat/sessions/${sid}/artifacts/${a.id}/diff`);
      body.innerHTML = "";
      body.append(h("p.muted", {}, d.exists ? "So sánh với file hiện có trong code project:" : "File mới trong code project."),
        h("pre.preview-box.mono", { style: "max-height:none" }, d.diff));
      if (a.status === "collected") {
        body.append(h("div.row", { style: "margin-top:12px" }, h("span.grow"),
          h("button.btn", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/chat/sessions/${sid}/artifacts/${a.id}/reject`, {})); P.close(); PL.chat.refresh(); } }, "Bỏ qua"),
          h("button.btn.accent" + (apply ? "" : ""), { type: "button", onclick: async () => {
            const r = await PL.safe(() => PL.post(`/api/chat/sessions/${sid}/artifacts/${a.id}/apply`, { target: a.path, expected_sha: d.target_sha256 }), "Đã áp dụng (có bản sao lưu)");
            if (r) { P.close(); PL.chat.refresh(); }
          } }, "Chấp nhận & áp dụng")));
      }
    } catch (e) { body.innerHTML = ""; body.append(h("p.err-line", {}, e.message)); }
  };

  // ------------------------------------------------------------------ research outline (levels 1–5 + attached proposal)
  const LEVELS = [["keywords", "Từ khoá", "vd: lightweight ViT, edge devices, pruning"], ["topic", "Chủ đề", "Một câu nêu vấn đề nghiên cứu"],
    ["direction", "Định hướng", "Gap / hướng giải quyết bạn muốn đi"], ["method", "Phương pháp", "Dữ liệu, baseline, metric, thí nghiệm"],
    ["proposal", "Đề cương đầy đủ", "Markdown: mục tiêu, câu hỏi, phương pháp, kế hoạch…"]];

  /** The card shown in an empty project: pick the level you start from, type it or attach your proposal. */
  P.outlineStarter = function (o) {
    let level = 0;
    const field = h("textarea.input", { rows: "3", placeholder: LEVELS[0][2] });
    const lv = h("div.levels");
    const paint = () => {
      lv.innerHTML = "";
      LEVELS.forEach(([k, label], i) => lv.append(h("button.level" + (i === level ? ".on" : ""), { type: "button", onclick: () => { level = i; field.placeholder = LEVELS[i][2]; field.rows = i === 4 ? 8 : 3; paint(); } }, h("b", {}, "Cấp " + (i + 1)), label)));
    };
    paint();
    const file = h("input", { type: "file", accept: ".pdf,.docx,.md,.markdown,.txt,.tex", hidden: true, onchange: (e) => attachOutline(e.target.files[0]) });
    return h("div.outline-card", {},
      h("div.card", {}, h("div.card-h", {}, h("span.kind", {}, "Bước 1"), h("span.ttl", {}, "Đưa vào đề cương nghiên cứu")),
        h("div.card-b", {}, h("p", { style: "margin:4px 0 0" }, "Bắt đầu ở cấp bạn đang có — từ vài từ khoá đến một đề cương hoàn chỉnh. AI sẽ đề xuất cấp tiếp theo để bạn duyệt."),
          lv, field),
        h("div.card-f", {}, h("button.btn.sm", { type: "button", onclick: () => file.click() }, h("span", { html: PL.icon("clip") }), "Đính kèm đề cương (PDF, Word, MD…)"), file,
          h("span.spacer"),
          h("button.btn.accent.sm", { type: "button", onclick: async () => {
            const v = field.value.trim();
            if (!v) { field.focus(); return; }
            const k = LEVELS[level][0];
            const r = await PL.safe(() => PL.put("/api/outline", { [k]: v }), "Đã lưu đề cương");
            if (r) PL.chat.submit(`/outline Mình đã có ${LEVELS[level][1].toLowerCase()}. Hãy đề xuất cấp tiếp theo.`);
          } }, "Lưu & để AI đề xuất tiếp"))));
  };
  async function attachOutline(f) {
    if (!f) return;
    const a = await PL.safe(() => PL.upload("/api/outline/attach", f), "Đã đính kèm " + f.name);
    if (a) PL.chat.submit(`/outline Mình vừa đính kèm đề cương "${a.name}". Hãy đọc, tóm tắt theo 5 cấp và đề xuất cập nhật.`);
  }

  P.outline = async function () {
    const body = P.open("Đề cương nghiên cứu", h("span.spin"), { kind: "outline" });
    const o = await PL.get("/api/outline").catch((e) => { body.textContent = e.message; return null; });
    if (!o) return;
    body.innerHTML = "";
    body.append(h("div.row", { style: "margin-bottom:12px" }, h("span.chip.accent", {}, `Cấp ${o.level}/5`), h("span.muted", {}, o.level_label || "chưa có")));
    const inputs = {};
    for (const [k, label, ph] of LEVELS) {
      const val = k === "keywords" ? (o.keywords || []).join(", ") : o[k] || "";
      const el = k === "keywords" ? h("input.input", { value: val, placeholder: ph }) :
        h("textarea.input", { rows: { topic: "2", proposal: "14" }[k] || "4", placeholder: ph }, val);
      inputs[k] = el;
      body.append(h("label.field", {}, h("span", {}, label), el));
    }
    body.append(h("div.row", {}, h("button.btn.sm", { type: "button", onclick: () => PL.chat.submit("/outline Hãy đề xuất cấp tiếp theo của đề cương.") }, h("span", { html: PL.icon("spark") }), "AI đề xuất cấp tiếp"),
      h("span.grow"), h("button.btn.accent.sm", { type: "button", onclick: async () => {
        const patch = {};
        for (const [k] of LEVELS) patch[k] = inputs[k].value;
        if (await PL.safe(() => PL.put("/api/outline", patch), "Đã lưu đề cương")) P.outline();
      } }, "Lưu")));
    body.append(h("div.section-h", {}, "File đề cương đính kèm"));
    const file = h("input", { type: "file", accept: ".pdf,.docx,.md,.markdown,.txt,.tex", hidden: true, onchange: (e) => attachOutline(e.target.files[0]).then(P.outline) });
    body.append(h("div.list", {}, (o.attachments || []).map((a) => h("div.li", {}, h("span", { html: PL.icon("file") }),
      h("div.m", {}, h("div.t", {}, a.name), h("div.s", {}, `${a.kind} · ${a.chars} ký tự`)),
      h("button.icon", { type: "button", title: "Gỡ", html: PL.icon("trash"), onclick: async () => { await PL.safe(() => PL.del("/api/outline/attach/" + a.id)); P.outline(); } })))),
    h("button.btn.sm", { type: "button", style: "margin-top:8px", onclick: () => file.click() }, "Đính kèm file…"), file);
    if ((o.versions || []).length) {
      body.append(h("div.section-h", {}, "Phiên bản trước"));
      body.append(h("div.list", {}, o.versions.slice().reverse().slice(0, 8).map((v, i) => h("div.li", {},
        h("div.m", {}, h("div.t", {}, v.reason || v.by), h("div.s", {}, PL.ago(v.ts))),
        h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post("/api/outline/restore", { index: o.versions.length - 1 - i }), "Đã khôi phục"); P.outline(); } }, "Khôi phục")))));
    }
  };

  // ------------------------------------------------------------------ literature discovery and saved sources
  function webURL(value) {
    try {
      const u = new W.URL(value);
      return ["https:", "http:"].includes(u.protocol) && !u.username && !u.password ? u.href : "";
    } catch (e) { return ""; }
  }
  function sourceLink(label, value) {
    const url = webURL(value);
    return url ? h("a.btn.sm.ghost", { href: url, target: "_blank", rel: "noopener noreferrer" }, label) : null;
  }
  function paperMeta(s) {
    return [(Array.isArray(s.authors) ? s.authors : []).slice(0, 3).join(", "), s.year, s.venue,
      Number.isFinite(s.citations) ? s.citations + " trích dẫn" : ""].filter(Boolean).join(" · ");
  }
  function ranking(s) {
    const r = s.journal_ranking || {};
    const fields = [];
    if (r.quartile) fields.push("Best quartile " + r.quartile);
    if (r.sjr != null) fields.push("SJR " + r.sjr);
    if (r.h_index != null) fields.push("h-index " + r.h_index);
    if (r.two_year_mean_citedness != null) fields.push("Trích dẫn TB 2 năm " + Number(r.two_year_mean_citedness).toFixed(2));
    const box = h("div", { style: "margin-top:8px;font-size:12px" },
      h("b", {}, "Tạp chí / nơi công bố: "),
      fields.length ? fields.join(" · ") + (r.year ? " (" + r.year + ")" : "") : "Chưa có dữ liệu xếp hạng xác thực.");
    if (r.source) box.append(h("div.muted", {}, "Nguồn: " + r.source + (r.year ? " · " + r.year : "")));
    if (r.categories) box.append(h("div.muted", {}, "Nhóm ngành: " + r.categories));
    const metrics = r.openalex_metrics;
    if (metrics && metrics.source && metrics.source !== r.source) {
      box.append(h("div", {}, h("div.muted", {}, "h-index / trích dẫn: " + metrics.source), sourceLink("Nguồn chỉ số trích dẫn", metrics.source_url)));
    }
    if (r.note) box.append(h("div.muted", {}, r.note));
    box.append(h("div.muted", {}, "Chỉ số của nơi công bố; không phải điểm chất lượng của riêng bài báo."));
    const link = sourceLink("Xem dữ liệu gốc", r.source_url);
    if (link) box.append(link);
    const lookup = sourceLink("Tra SJR / quartile", r.lookup_url);
    if (lookup) box.append(lookup);
    return box;
  }
  P.runSources = function (r) {
    const found = [], seen = new Set();
    const add = (s) => {
      if (!s || typeof s !== "object") return;
      const key = s.doi || s.url || s.title || s.id;
      if (!key || seen.has(key)) return;
      seen.add(key); found.push(s);
    };
    ((r.result || {}).sources || []).forEach(add);
    (r.steps || []).forEach((step) => ((step.result || {}).sources || []).forEach(add));
    return found;
  };
  P.paperCard = function (s) {
    const note = h("div.muted", { style: "font-size:12px", role: "status" });
    const save = h("button.btn.accent.sm", { type: "button", onclick: async () => {
      save.disabled = true; save.textContent = "Đang lưu…"; note.textContent = "";
      try {
        const r = await PL.post("/api/library/save", { source: s });
        save.textContent = r.upgraded ? "Đã bổ sung PDF vào thư viện" : r.already_saved ? "Đã có trong thư viện" : "Đã lưu vào thư viện";
        note.textContent = r.warning || (r.pdf_saved ? "Đã lưu cả PDF." : "Đã lưu thông tin bài báo; chưa có PDF truy cập mở.");
      } catch (e) {
        save.disabled = false; save.textContent = "Lưu vào thư viện"; note.textContent = e.message;
      }
    } }, "Lưu vào thư viện");
    return h("article.card.paper", {},
      h("div.card-h", {}, h("span.kind", {}, s.source || (s.kind === "web" ? "Web" : "Paper")), h("span.ttl", {}, s.title || s.url || "Nguồn tài liệu")),
      h("div.card-b", {}, h("div.muted", {}, paperMeta(s)), s.snippet ? h("p", {}, s.snippet) : null,
        s.doi ? h("div.muted", {}, "DOI: " + s.doi) : null, ranking(s), note),
      h("div.card-f", { style: "flex-wrap:wrap" }, sourceLink("Mở nguồn", s.url), sourceLink("PDF", s.pdf_url), h("span.spacer"), save));
  };
  P.literature = async function (initialQuery) {
    const body = P.open("Lit · Tìm paper & web", null, { kind: "literature", actions: [h("button.btn.sm", { type: "button", onclick: () => P.library() }, "Thư viện")] });
    const query = h("input.input", { type: "search", value: initialQuery || "", placeholder: "Từ khoá, tên bài báo hoặc DOI", "aria-label": "Từ khoá tìm paper" });
    const year = h("input.input", { type: "number", min: 1900, max: new Date().getFullYear() + 1, placeholder: "Từ năm", "aria-label": "Từ năm", style: "max-width:110px" });
    const mode = h("select.input", { "aria-label": "Phạm vi tìm kiếm", style: "width:auto" },
      h("option", { value: "both" }, "Paper + web"), h("option", { value: "papers" }, "Paper"), h("option", { value: "web" }, "Web"));
    const results = h("div.lit-results", { "aria-live": "polite" });
    const external = h("div.row", { style: "flex-wrap:wrap;margin:8px 0" });
    const directLinks = (q, links) => {
      links = links || {};
      external.innerHTML = "";
      external.append(sourceLink("IEEE Xplore", links.ieee || "https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText=" + encodeURIComponent(q)),
        sourceLink("arXiv", "https://arxiv.org/search/?searchtype=all&query=" + encodeURIComponent(q)),
        sourceLink("Google Scholar", links.google_scholar || "https://scholar.google.com/scholar?q=" + encodeURIComponent(q)));
    };
    const search = h("button.btn.accent", { type: "submit" }, "Tìm kiếm");
    const form = h("form", { onsubmit: async (e) => {
      e.preventDefault();
      const q = query.value.trim();
      if (!q) { query.focus(); return; }
      if (!year.checkValidity()) { year.reportValidity(); return; }
      search.disabled = true; results.innerHTML = ""; results.append(h("span.spin"));
      directLinks(q);
      try {
        const r = await PL.post("/api/search", { query: q, mode: mode.value, ...(year.value ? { year_from: Number(year.value) } : {}) });
        results.innerHTML = "";
        directLinks(q, r.search_links);
        if ((r.provider_status || {}).google_scholar === "requires_serpapi_key") {
          results.append(h("p.muted", {}, "Google Scholar chưa được truy vấn: cần SerpAPI key trong Cài đặt. Bấm Google Scholar ở trên để tìm trực tiếp."));
        }
        const sources = Array.isArray(r.sources) ? r.sources : [];
        results.append(h("div.section-h", {}, sources.length + " kết quả"));
        if (!sources.length) results.append(h("p.muted", {}, "Chưa tìm thấy kết quả. Thử từ khoá tiếng Anh hoặc mở nguồn tìm trực tiếp ở trên."));
        const errors = r.errors || [];
        (Array.isArray(errors) ? errors : Object.entries(errors).map(([k, v]) => k + ": " + v)).forEach((err) =>
          results.append(h("p.err-line", {}, typeof err === "string" ? err : JSON.stringify(err))));
        sources.forEach((s) => results.append(P.paperCard(s)));
      } catch (err) { results.innerHTML = ""; results.append(h("p.err-line", {}, err.message)); }
      finally { search.disabled = false; }
    } }, query, h("div.row", { style: "margin-top:8px;flex-wrap:wrap" }, mode, year, h("span.grow"), search));
    body.append(h("p.muted", {}, "Tìm đa nguồn: OpenAlex, Semantic Scholar, arXiv, IEEE và web. Google Scholar dùng SerpAPI khi có key; bạn luôn có thể mở tìm kiếm trực tiếp."),
      form, external, h("button.btn.sm.ghost", { type: "button", onclick: () => PL.settings.open("providers") }, "Cấu hình nguồn tìm kiếm"), results);
    if (initialQuery) form.requestSubmit(); else query.focus();
  };
  P.reference = function (e) {
    if (e.pdf_available !== false && /\.pdf$/i.test(e.file || "")) {
      P.open(e.title || e.file, h("iframe.file-frame", { src: "/api/library/file/" + encodeURIComponent(e.file) }));
      return;
    }
    P.open(e.title || e.file, h("div", {}, h("p.muted", {}, paperMeta(e)),
      e.abstract || e.snippet ? h("p", {}, e.abstract || e.snippet) : null,
      h("p.muted", {}, "Đã lưu thông tin bài báo. Chưa có PDF trong thư viện."), ranking(e), sourceLink("Mở nguồn bài báo", e.source_url || e.url)), { kind: "reference", arg: e.file });
  };

  // ------------------------------------------------------------------ library
  P.library = async function () {
    const body = P.open("Tài liệu", h("span.spin"), { kind: "library" });
    const paint = async () => {
      const r = await PL.get("/api/library").catch((e) => ({ references: [], error: e.message }));
      body.innerHTML = "";
      const file = h("input", { type: "file", accept: "application/pdf,.pdf", multiple: true, hidden: true, onchange: (e) => up(e.target.files) });
      const drop = h("div.drop", { onclick: () => file.click() }, "Kéo thả PDF vào đây hoặc bấm để chọn — dùng cho /lit, /gap, /write và kiểm chứng trích dẫn");
      drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); up(e.dataTransfer.files); });
      const up = async (fs) => { if (await PL.safe(() => PL.upload("/api/library/upload", Array.from(fs), "files"), "Đã thêm vào thư viện")) paint(); };
      body.append(h("div.row", { style: "margin-bottom:12px" }, h("button.btn.accent", { type: "button", onclick: () => P.literature() }, "Tìm paper & web")),
        drop, file, h("div.section-h", {}, `${r.references.length} tài liệu`));
      if (r.error) body.append(h("p.err-line", {}, r.error));
      body.append(h("div.list", {}, r.references.map((e) => h("div.li", {},
        h("input", { type: "checkbox", checked: e.include !== false || null, title: "Dùng trong ngữ cảnh", onchange: (ev) => PL.safe(() => PL.put("/api/library/" + encodeURIComponent(e.file), { include: ev.target.checked })) }),
        h("div.m", { style: "cursor:pointer", onclick: () => P.reference(e) },
          h("div.t", {}, e.title || e.file), h("div.s", {}, paperMeta(e) || e.key),
          e.pdf_available === false ? h("span.chip", {}, "Thông tin bài báo") : null),
        h("button.icon", { type: "button", title: "Xoá khỏi thư viện", html: PL.icon("trash"), onclick: async () => { if (await PL.confirm(`Xoá ${e.file} khỏi thư mục tài liệu?`, "Xoá")) { await PL.safe(() => PL.del("/api/library/" + encodeURIComponent(e.file))); paint(); } } })))));
    };
    await paint();
  };

  // ------------------------------------------------------------------ experiments = VS Code
  P.code = async function () {
    const body = P.open("Thí nghiệm · VS Code", h("span.spin"), { kind: "code" });
    const paint = async () => {
      const [cp, jobs] = await Promise.all([PL.get("/api/code").catch(() => ({ projects: [] })), PL.get("/api/jobs?limit=12").catch(() => ({ jobs: [] }))]);
      body.innerHTML = "";
      const act = (cp.projects || []).find((p) => p.active);
      body.append(h("p.muted", { style: "margin-top:0" }, "Viết và chạy code trong VS Code. Mỗi code project có git và môi trường Python (venv) riêng; Docker chỉ dùng ngầm khi tác vụ cần Linux."));
      const projects = cp.projects || [];
      const sel = h("select.input", { onchange: async (e) => { if (e.target.value === "__new") return newProject(); await PL.safe(() => PL.post("/api/code/open", { name: e.target.value })); paint(); } },
        projects.length ? null : h("option", { value: "", selected: true }, "— chưa có code project —"),
        projects.map((p) => h("option", { value: p.name, selected: p.active || null }, p.name)),
        h("option", { value: "__new" }, "＋ Code project mới…"));
      body.append(h("label.field", {}, h("span", {}, "Code project"), sel));
      body.append(h("div.row", { style: "flex-wrap:wrap" },
        h("button.btn.accent", { type: "button", disabled: !act || null, onclick: () => PL.safe(() => PL.post("/api/code/vscode"), "Đã mở VS Code") }, h("span", { html: PL.icon("ext") }), "Mở trong VS Code"),
        h("button.btn", { type: "button", disabled: !act || null, title: "Lấy thay đổi code, metrics và hình mới từ VS Code về dự án (bạn duyệt từng mục)", onclick: syncBack }, h("span", { html: PL.icon("sync") }), "Đồng bộ kết quả về")));
      body.append(h("div.section-h", {}, "Lần chạy gần đây"));
      if (!jobs.jobs.length) body.append(h("p.muted", {}, "Chưa có lần chạy nào. Gõ /run <lệnh> hoặc /idea <ý tưởng> trong chat."));
      body.append(h("div.list", {}, jobs.jobs.map((j) => h("div.li", {},
        h("span.dot." + (j.status === "done" ? "ok" : j.status === "failed" ? "err" : j.status === "running" ? "warn" : "")),
        h("div.m", {}, h("div.t.mono", {}, j.cmd || j.id), h("div.s", {}, `${j.status} · ${j.mode || ""} · ${j.metrics && Object.keys(j.metrics).length ? Object.entries(j.metrics).slice(0, 3).map(([k, v]) => k + "=" + v).join(", ") : "không có metrics"}`)),
        j.status === "running" ? h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/jobs/${j.id}/stop`)); paint(); } }, "Dừng") : null))));
    };
    async function newProject() {
      const name = await PL.prompt("Code project mới", "Tên (chữ, số, - _)", "exp1");
      if (name && await PL.safe(() => PL.post("/api/code", { name }), "Đã tạo " + name)) paint(); else paint();
    }
    async function syncBack() {
      let sid = PL.chat.sid;
      if (!sid) { const s = await PL.safe(() => PL.post("/api/chat/sessions", { title: "Đồng bộ từ VS Code" })); if (!s) return; sid = s.id; }
      const r = await PL.safe(() => PL.post("/api/code/sync", { session_id: sid }));
      if (!r) return;
      PL.toast(r.proposals ? `${r.proposals} đề xuất chờ bạn duyệt trong chat` : "Không có gì mới");
      PL.go("#/chat/" + sid);
    }
    await paint();
  };
})(window);
