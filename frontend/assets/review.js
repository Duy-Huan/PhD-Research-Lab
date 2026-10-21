/* PhD Research Lab — paper review session: manuscript → reviewers R1–R3 → area chair → issue list → quick fixes the
   researcher accepts or dismisses → apply to the LaTeX source → response letter. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const R = (PL.review = { rid: null, data: null, tab: "R1", busy: false });
  const SEV = { critical: "err", major: "warn", minor: "info", typo: "" };

  PL.route("review", async function (rid) {
    if (PL.chat.sse) { PL.chat.sse.close(); PL.chat.sse = null; }
    PL.chat.sid = null;
    PL.activeNav("review");
    PL.setTitle("Phản biện bài báo", "");
    R.rid = rid || null;
    const v = PL.$("#view");
    v.innerHTML = "";
    const inner = h("div.page-in");
    v.append(h("div.page", {}, inner));
    const list = await PL.get("/api/review").catch(() => ({ reviews: [], active: "" }));
    if (!R.rid && list.reviews.length) R.rid = list.active && list.reviews.some((x) => x.id === list.active) ? list.active : list.reviews[0].id;
    inner.append(h("h1", {}, "Phản biện bài báo"), h("p.lead", {}, "Ba reviewer độc lập, chủ tịch hội đồng, danh sách vấn đề và đề xuất sửa — bạn chấp nhận hoặc bỏ qua từng sửa."));
    const grid = h("div.review-grid");
    inner.append(grid);
    grid.append(sidebar(list.reviews), h("div#rv-main"));
    if (R.rid) await load(R.rid);
    else PL.$("#rv-main").append(dropZone());
  });

  async function uploadManuscript(f) {
    if (!f) return;
    const r = await PL.safe(() => PL.upload("/api/review/upload", f), "Đã tải lên " + f.name);
    if (r) PL.go("#/review/" + r.meta.id);
  }
  function dropZone() {
    const file = h("input", { type: "file", accept: ".pdf,.docx,.tex,.md,.txt,.markdown", hidden: true, onchange: (e) => uploadManuscript(e.target.files[0]) });
    const d = h("div.drop", { role: "button", tabindex: "0", style: "padding:48px 18px;cursor:pointer", onclick: () => file.click(),
      onkeydown: (e) => { if (e.key === "Enter") file.click(); } },
    h("div", { html: PL.icon("upload"), style: "width:28px;margin:0 auto 8px" }), "Kéo thả hoặc bấm để tải bản thảo (PDF, Word, LaTeX, Markdown).", file);
    d.addEventListener("dragover", (e) => { e.preventDefault(); d.classList.add("over"); });
    d.addEventListener("dragleave", () => d.classList.remove("over"));
    d.addEventListener("drop", (e) => { e.preventDefault(); d.classList.remove("over"); uploadManuscript(e.dataTransfer.files[0]); });
    return d;
  }
  function sidebar(items) {
    const file = h("input", { type: "file", accept: ".pdf,.docx,.tex,.md,.txt,.markdown", hidden: true, onchange: (e) => uploadManuscript(e.target.files[0]) });
    return h("div", {}, h("button.btn.accent", { type: "button", style: "width:100%", onclick: () => file.click() }, h("span", { html: PL.icon("upload") }), "Bản thảo mới"), file,
      h("div.list", { style: "margin-top:10px" }, items.map((it) => h("div.li" + (it.id === R.rid ? ".thread.active" : ""), { style: "cursor:pointer", onclick: () => PL.go("#/review/" + it.id) },
        h("div.m", {}, h("div.t", {}, it.title || it.file), h("div.s", {}, [it.decision, it.n_issues ? it.n_issues + " vấn đề" : "", (it.updated || "").slice(0, 10)].filter(Boolean).join(" · ")))))));
  }

  async function load(rid) {
    R.data = await PL.get("/api/review/" + rid).catch((e) => { PL.toast(e.message, "err"); return null; });
    if (R.data) paint();
  }

  function paint() {
    const box = PL.$("#rv-main");
    if (!box) return;
    box.innerHTML = "";
    const { meta, state } = R.data;
    const v = meta.venue || {};
    const type = h("select.input", {}, h("option", { value: "conference", selected: v.type !== "journal" || null }, "Hội nghị"), h("option", { value: "journal", selected: v.type === "journal" || null }, "Tạp chí"));
    const rank = h("select.input", {}, ["A*", "A", "B", "C"].map((x) => h("option", { value: x, selected: v.rank === x || null }, "CORE " + x)));
    const quart = h("select.input", {}, ["Q1", "Q2", "Q3", "Q4"].map((x) => h("option", { value: x, selected: v.quartile === x || null }, x)));
    const n = h("select.input", {}, [1, 2, 3].map((x) => h("option", { value: x, selected: meta.n_reviewers === x || null }, x + " reviewer")));
    const name = h("input.input", { value: v.name || "", placeholder: "Tên hội nghị / tạp chí (tuỳ chọn)" });
    const save = async () => PL.safe(() => PL.put(`/api/review/${meta.id}/settings`, { venue: { type: type.value, scale: "icore", rank: rank.value, quartile: quart.value, name: name.value }, n_reviewers: +n.value }), "Đã lưu");
    box.append(h("div.panelbox", { style: "margin-top:0" },
      h("div.row", { style: "margin-top:10px" }, h("b.grow", {}, meta.title || meta.file), h("span.muted", {}, `${meta.pages || "?"} trang · ${Math.round((meta.chars || 0) / 1000)}k ký tự`),
        h("a.btn.sm.ghost", { href: `/api/review/${meta.id}/original`, target: "_blank" }, "Bản gốc")),
      h("div.grid2", { style: "margin-top:10px" }, h("label.field", {}, h("span", {}, "Loại"), type), h("label.field", {}, h("span", {}, v.type === "journal" ? "Hạng tạp chí" : "Hạng hội nghị"), v.type === "journal" ? quart : rank),
        h("label.field", {}, h("span", {}, "Số reviewer"), n), h("label.field", {}, h("span", {}, "Venue"), name)),
      h("div.row", {}, h("button.btn.sm", { type: "button", onclick: async () => { await save(); load(meta.id); } }, "Lưu cài đặt"), h("span.grow"),
        h("button.btn.accent", { type: "button", disabled: R.busy || null, onclick: runAll }, h("span", { html: PL.icon("play") }), Object.keys(state.reviewers).length ? "Phản biện lại" : "Bắt đầu phản biện"))));
    const prog = h("div#rv-prog");
    box.append(prog);
    const tabs = [];
    for (let i = 1; i <= (meta.n_reviewers || 3); i++) tabs.push(["R" + i, "Reviewer " + i]);
    tabs.push(["meta", "Chủ tịch"], ["issues", `Vấn đề (${state.issues.length})`], ["response", "Thư phản hồi"]);
    const tb = h("div.rv-tabs", {}, tabs.map(([k, label]) => h("button" + (k === R.tab ? ".on" : ""), { type: "button", onclick: () => { R.tab = k; paint(); } }, label)));
    box.append(tb, h("div#rv-body"));
    tabBody();
    box.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Xuất & áp dụng"),
      h("div.row", { style: "flex-wrap:wrap" },
        h("a.btn.sm", { href: `/api/review/${meta.id}/download/report` }, "Báo cáo phản biện (.md)"),
        h("a.btn.sm", { href: `/api/review/${meta.id}/download/fixes` }, "Đề xuất sửa (.md)"),
        state.response ? h("a.btn.sm", { href: `/api/review/${meta.id}/download/response` }, "Thư phản hồi (.md)") : null,
        meta.source ? h("button.btn.sm.accent", { type: "button", onclick: async () => { const r = await PL.safe(() => PL.post(`/api/review/${meta.id}/apply`, {})); if (r) PL.toast(`Đã áp dụng ${(r.applied || []).length} sửa → source_revised.tex` + ((r.not_found || []).length ? ` · ${r.not_found.length} không khớp` : "")); } }, "Áp dụng sửa đã chấp nhận vào LaTeX") :
          h("button.btn.sm", { type: "button", onclick: () => srcFile.click() }, "Đính kèm mã nguồn LaTeX (.tex)"),
        meta.source ? h("a.btn.sm", { href: `/api/review/${meta.id}/download/source` }, "Tải .tex đã sửa") : null,
        h("span.grow"), h("button.btn.sm.danger", { type: "button", onclick: async () => { if (await PL.confirm("Xoá phiên phản biện này?", "Xoá")) { await PL.safe(() => PL.del("/api/review/" + meta.id)); PL.go("#/review"); } } }, "Xoá"))));
    const srcFile = h("input", { type: "file", accept: ".tex", hidden: true, onchange: async (e) => { if (e.target.files[0] && await PL.safe(() => PL.upload(`/api/review/${meta.id}/source`, e.target.files[0]), "Đã đính kèm LaTeX")) load(meta.id); } });
    box.append(srcFile);
  }

  function tabBody() {
    const b = PL.$("#rv-body");
    const { state } = R.data;
    b.innerHTML = "";
    if (R.tab.startsWith("R")) {
      const rv = Object.values(state.reviewers)[+R.tab.slice(1) - 1];
      b.append(rv ? h("div.panelbox", {}, h("div.row", { style: "margin:10px 0" }, h("b", {}, rv.persona || ""), rv.recommendation ? h("span.chip", {}, rv.recommendation) : null,
        rv.score ? h("span.chip", {}, "Điểm " + rv.score) : null), PL.rich(h("div.prose"), rv.text)) : h("p.muted", {}, "Chưa có báo cáo — bấm Bắt đầu phản biện."));
    } else if (R.tab === "meta") {
      b.append(state.meta ? h("div.panelbox", {}, state.meta.decision ? h("div.row", { style: "margin:10px 0" }, h("span.chip.accent", {}, state.meta.decision)) : null, PL.rich(h("div.prose"), state.meta.text)) : h("p.muted", {}, "Chưa có ý kiến chủ tịch hội đồng."));
    } else if (R.tab === "issues") {
      if (!state.issues.length) { b.append(h("p.muted", {}, "Chưa có danh sách vấn đề.")); return; }
      for (const it of state.issues) b.append(issueNode(it, state.fixes[it.id]));
    } else {
      b.append(state.response ? h("div.panelbox", {}, PL.rich(h("div.prose"), state.response.text)) :
        h("div", {}, h("p.muted", {}, "Thư phản hồi reviewer được soạn từ các vấn đề và trạng thái xử lý của bạn."),
          h("button.btn.accent", { type: "button", onclick: () => stage({ stage: "response" }, "Thư phản hồi") }, "Soạn thư phản hồi")));
    }
  }

  function issueNode(it, fx) {
    const node = h("div.issue", {},
      h("div.h", {}, h("span.chip." + (SEV[it.severity] || ""), {}, it.severity), h("span.t", {}, it.title), h("span.muted", { style: "font-size:12px" }, it.location),
        h("select.input", { style: "width:auto;height:26px;padding:0 6px;font-size:12px", onchange: (e) => setIssue(it, { status: e.target.value }) },
          [["open", "Chưa xử lý"], ["done", "Đã xử lý"], ["wontfix", "Không sửa"]].map(([k, l]) => h("option", { value: k, selected: it.status === k || null }, l)))),
      h("div", { style: "margin-top:6px;font-size:13.5px" }, it.problem),
      it.fix ? h("div.muted", { style: "font-size:13px;margin-top:4px" }, "Gợi ý: " + it.fix) : null);
    if (fx) {
      node.append(h("div.diff-pair", {}, h("pre.old", {}, fx.original || "(không trích được đoạn gốc)"), h("pre.new", {}, fx.revised || fx.plan || "")),
        fx.note ? h("div.muted", { style: "font-size:12.5px;margin-top:4px" }, fx.note) : null,
        h("div.row", { style: "margin-top:8px" }, h("span.chip" + (fx.status === "accepted" ? ".ok" : fx.status === "dismissed" ? "" : ".warn"), {}, { proposed: "chờ duyệt", accepted: "đã chấp nhận", dismissed: "đã bỏ qua" }[fx.status] || fx.status),
          !fx.original_found && fx.original ? h("span.chip.err", {}, "không khớp nguyên văn") : null, h("span.grow"),
          h("button.btn.sm", { type: "button", onclick: () => setIssue(it, { fix_status: "dismissed" }) }, "Bỏ qua"),
          h("button.btn.sm.accent", { type: "button", onclick: () => setIssue(it, { fix_status: "accepted", status: "done" }) }, "Chấp nhận sửa")));
    } else {
      node.append(h("div.row", { style: "margin-top:8px" }, h("span.grow"), h("button.btn.sm", { type: "button", onclick: () => stage({ issue_id: it.id }, "Sửa " + it.id, "fix") }, h("span", { html: PL.icon("spark") }), "Đề xuất sửa")));
    }
    return node;
  }
  async function setIssue(it, body) {
    await PL.safe(() => PL.put(`/api/review/${R.data.meta.id}/issue/${it.id}`, body));
    load(R.data.meta.id);
  }

  /** POST a stage and read its Server-Sent Events (start → delta… → done | error). */
  async function stage(body, label, path) {
    const prog = PL.$("#rv-prog");
    const out = h("div.prose");
    const box = h("div.card", {}, h("div.card-h", {}, h("span.spin"), h("span.ttl", {}, label)), h("div.card-b", {}, out));
    if (prog) { prog.innerHTML = ""; prog.append(box); }
    let text = "", done = null;
    try {
      const r = await W.fetch(`/api/review/${R.data.meta.id}/${path || "stage"}`, { method: "POST", headers: { "Content-Type": "application/json", "X-PhDLab-Client": "ui" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      const rd = r.body.getReader();
      const dec = new W.TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done: end } = await rd.read();
        if (end) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, i).replace(/^data: /, "");
          buf = buf.slice(i + 2);
          let ev;
          try { ev = JSON.parse(line); } catch (e) { continue; }
          if (ev.type === "delta") { text += ev.text; out.textContent = text.slice(-1500); }
          else if (ev.type === "error") throw new Error(ev.detail);
          else if (ev.type === "done") done = ev;
        }
      }
    } catch (e) {
      if (prog) prog.innerHTML = "";
      PL.toast(label + ": " + e.message, "err");
      return null;
    }
    if (prog) prog.innerHTML = "";
    await load(R.data.meta.id);
    return done;
  }

  async function runAll() {
    if (R.busy) return;
    R.busy = true;
    const n = R.data.meta.n_reviewers || 3;
    try {
      for (let i = 1; i <= n; i++) {
        R.tab = "R" + i;
        if (!(await stage({ stage: "reviewer", idx: i, fresh: i === 1 }, `Reviewer ${i}/${n} đang đọc bản thảo…`))) return;
      }
      R.tab = "meta";
      if (!(await stage({ stage: "meta" }, "Chủ tịch hội đồng tổng hợp…"))) return;
      R.tab = "issues";
      await stage({ stage: "issues" }, "Lập danh sách vấn đề…");
      PL.toast("Phản biện xong — duyệt từng vấn đề và đề xuất sửa");
    } finally {
      R.busy = false;
      paint();
    }
  }
  R.runAll = runAll;
})(window);
