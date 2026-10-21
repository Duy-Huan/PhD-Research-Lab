/* PhD Research Lab — paper review session: manuscript → reviewers R1–R3 → area chair → issue list → quick fixes the
   researcher accepts or dismisses → apply to the LaTeX source → response letter. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const R = (PL.review = { rid: null, data: null, tab: "R1", busy: false });
  const SEV = { critical: "err", major: "warn", minor: "info", typo: "" };

  PL.route("review", async function (rid) {
    PL.leaveChat();
    PL.activeNav("review");
    PL.setTitle(PL.t("Phản biện bài báo"), "");
    R.rid = rid || null;
    const v = PL.$("#view");
    v.innerHTML = "";
    const inner = h("div.page-in");
    v.append(h("div.page", {}, inner));
    const list = await PL.get("/api/review").catch(() => ({ reviews: [], active: "" }));
    if (!R.rid && list.reviews.length) R.rid = list.active && list.reviews.some((x) => x.id === list.active) ? list.active : list.reviews[0].id;
    inner.append(h("h1", {}, PL.t("Phản biện bài báo")), h("p.lead", {}, PL.t("Ba reviewer độc lập, chủ tịch hội đồng, danh sách vấn đề và đề xuất sửa — bạn chấp nhận hoặc bỏ qua từng sửa.")));
    const grid = h("div.review-grid");
    inner.append(grid);
    grid.append(sidebar(list.reviews), h("div#rv-main"));
    if (R.rid) await load(R.rid);
    else PL.$("#rv-main").append(dropZone());
  });

  async function uploadManuscript(f) {
    if (!f) return;
    const r = await PL.safe(() => PL.upload("/api/review/upload", f), PL.t("Đã tải lên ") + f.name);
    if (r) PL.go("#/review/" + r.meta.id);
  }
  function dropZone() {
    const file = h("input", { type: "file", accept: ".pdf,.docx,.tex,.md,.txt,.markdown", hidden: true, onchange: (e) => uploadManuscript(e.target.files[0]) });
    const d = h("div.drop", { role: "button", tabindex: "0", style: "padding:48px 18px;cursor:pointer", onclick: () => file.click(),
      onkeydown: (e) => { if (e.key === "Enter") file.click(); } },
    h("div", { html: PL.icon("upload"), style: "width:28px;margin:0 auto 8px" }), PL.t("Kéo thả hoặc bấm để tải bản thảo (PDF, Word, LaTeX, Markdown)."), file);
    d.addEventListener("dragover", (e) => { e.preventDefault(); d.classList.add("over"); });
    d.addEventListener("dragleave", () => d.classList.remove("over"));
    d.addEventListener("drop", (e) => { e.preventDefault(); d.classList.remove("over"); uploadManuscript(e.dataTransfer.files[0]); });
    return d;
  }
  function sidebar(items) {
    const file = h("input", { type: "file", accept: ".pdf,.docx,.tex,.md,.txt,.markdown", hidden: true, onchange: (e) => uploadManuscript(e.target.files[0]) });
    return h("div", {}, h("button.btn.accent", { type: "button", style: "width:100%", onclick: () => file.click() }, h("span", { html: PL.icon("upload") }), PL.t("Bản thảo mới")), file,
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
    const type = h("select.input", {}, h("option", { value: "conference", selected: v.type !== "journal" || null }, PL.t("Hội nghị")), h("option", { value: "journal", selected: v.type === "journal" || null }, PL.t("Tạp chí")));
    const rank = h("select.input", {}, ["A*", "A", "B", "C"].map((x) => h("option", { value: x, selected: v.rank === x || null }, "CORE " + x)));
    const quart = h("select.input", {}, ["Q1", "Q2", "Q3", "Q4"].map((x) => h("option", { value: x, selected: v.quartile === x || null }, x)));
    const n = h("select.input", {}, [1, 2, 3].map((x) => h("option", { value: x, selected: meta.n_reviewers === x || null }, x + " reviewer")));
    const rankNote = h("small.muted", { role: "status" });
    const name = h("input.input", { value: v.name || "", placeholder: PL.t("Tên hội nghị / tạp chí (tuỳ chọn)"), onchange: async () => {
      // automatic ranking check of the target venue (local SCImago / CORE data) → preselect the bar the reviewers apply
      const q = name.value.trim();
      rankNote.textContent = "";
      if (!q) return;
      const r = await PL.get("/api/ranking/lookup?venue=" + encodeURIComponent(q)).catch(() => null);
      if (r && r.conference && ["A*", "A", "B", "C"].includes(r.conference.rank)) {
        type.value = "conference"; rank.value = r.conference.rank;
        rankNote.textContent = PL.t("{0} · CORE {1} ({2})", r.conference.acronym || r.conference.title, r.conference.rank, r.conference.source);
      } else if (r && r.journal && r.journal.quartile) {
        type.value = "journal"; quart.value = r.journal.quartile;
        rankNote.textContent = PL.t("{0} · {1} · SJR {2} ({3})", r.journal.title, r.journal.quartile, r.journal.sjr, r.journal.year);
      } else rankNote.textContent = PL.t("Không tìm thấy hạng trong dữ liệu SCImago / CORE đã có — chọn hạng thủ công.");
    } });
    const save = async () => PL.safe(() => PL.put(`/api/review/${meta.id}/settings`, { venue: { type: type.value, scale: "icore", rank: rank.value, quartile: quart.value, name: name.value }, n_reviewers: +n.value }), PL.t("Đã lưu"));
    box.append(h("div.panelbox", { style: "margin-top:0" },
      h("div.row", { style: "margin-top:10px" }, h("b.grow", {}, meta.title || meta.file), h("span.muted", {}, PL.t("{0} trang · {1}k ký tự", meta.pages || "?", Math.round((meta.chars || 0) / 1000))),
        h("a.btn.sm.ghost", { href: `/api/review/${meta.id}/original`, target: "_blank" }, PL.t("Bản gốc"))),
      h("div.grid2", { style: "margin-top:10px" }, h("label.field", {}, h("span", {}, PL.t("Loại")), type), h("label.field", {}, h("span", {}, v.type === "journal" ? PL.t("Hạng tạp chí") : PL.t("Hạng hội nghị")), v.type === "journal" ? quart : rank),
        h("label.field", {}, h("span", {}, PL.t("Số reviewer")), n), h("label.field", {}, h("span", {}, "Venue"), name, rankNote)),
      h("div.row", {}, h("button.btn.sm", { type: "button", onclick: async () => { await save(); load(meta.id); } }, PL.t("Lưu cài đặt")), h("span.grow"),
        h("button.btn.accent", { type: "button", disabled: R.busy || null, onclick: runAll }, h("span", { html: PL.icon("play") }), Object.keys(state.reviewers).length ? PL.t("Phản biện lại") : PL.t("Bắt đầu phản biện")))));
    const prog = h("div#rv-prog");
    box.append(prog);
    const tabs = [];
    for (let i = 1; i <= (meta.n_reviewers || 3); i++) tabs.push(["R" + i, "Reviewer " + i]);
    tabs.push(["meta", PL.t("Chủ tịch")], ["issues", PL.t("Vấn đề ({0})", state.issues.length)], ["guide", PL.t("Hướng dẫn sửa bài")], ["response", PL.t("Thư phản hồi")]);
    const tb = h("div.rv-tabs", {}, tabs.map(([k, label]) => h("button" + (k === R.tab ? ".on" : ""), { type: "button", onclick: () => { R.tab = k; paint(); } }, label)));
    box.append(tb, h("div#rv-body"));
    tabBody();
    const dl = (kind, label, enabled) => h("button.btn.sm", { type: "button", disabled: enabled === false || null, onclick: (e) => PL.menu(e.currentTarget,
      [{ header: label }].concat([["md", "Markdown (.md)"], ["pdf", "PDF (.pdf)"], ["docx", "Word (.docx)"], ["tex", "LaTeX (.tex)"]].map(([f, l]) => ({ label: l,
        run: () => PL.tools.download(`/api/review/${meta.id}/download/${kind}?format=${f}`, "") })))) }, h("span", { html: PL.icon("download") }), label);
    box.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Xuất & áp dụng")),
      h("div.row", { style: "flex-wrap:wrap" },
        dl("guide", PL.t("Hướng dẫn sửa bài"), state.issues.length > 0),
        dl("report", PL.t("Báo cáo phản biện")),
        dl("fixes", PL.t("Đề xuất sửa")),
        state.response ? dl("response", PL.t("Thư phản hồi")) : null,
        meta.source ? h("button.btn.sm.accent", { type: "button", onclick: async () => { const r = await PL.safe(() => PL.post(`/api/review/${meta.id}/apply`, {})); if (r) PL.toast(PL.t("Đã áp dụng {0} sửa → source_revised.tex", (r.applied || []).length) + ((r.not_found || []).length ? PL.t(" · {0} không khớp", r.not_found.length) : "")); } }, PL.t("Áp dụng sửa đã chấp nhận vào LaTeX")) :
          h("button.btn.sm", { type: "button", onclick: () => srcFile.click() }, PL.t("Đính kèm mã nguồn LaTeX (.tex)")),
        meta.source ? h("a.btn.sm", { href: `/api/review/${meta.id}/download/source` }, PL.t("Tải .tex đã sửa")) : null,
        h("span.grow"), h("button.btn.sm.danger", { type: "button", onclick: async () => { if (await PL.confirm(PL.t("Xoá phiên phản biện này?"), PL.t("Xoá"))) { await PL.safe(() => PL.del("/api/review/" + meta.id)); PL.go("#/review"); } } }, PL.t("Xoá")))));
    const srcFile = h("input", { type: "file", accept: ".tex", hidden: true, onchange: async (e) => { if (e.target.files[0] && await PL.safe(() => PL.upload(`/api/review/${meta.id}/source`, e.target.files[0]), PL.t("Đã đính kèm LaTeX"))) load(meta.id); } });
    box.append(srcFile);
  }

  function tabBody() {
    const b = PL.$("#rv-body");
    const { state } = R.data;
    b.innerHTML = "";
    if (R.tab.startsWith("R")) {
      const rv = Object.values(state.reviewers)[+R.tab.slice(1) - 1];
      b.append(rv ? h("div.panelbox", {}, h("div.row", { style: "margin:10px 0" }, h("b", {}, rv.persona || ""), rv.recommendation ? h("span.chip", {}, rv.recommendation) : null,
        rv.score ? h("span.chip", {}, PL.t("Điểm ") + rv.score) : null), PL.rich(h("div.prose"), rv.text)) : h("p.muted", {}, PL.t("Chưa có báo cáo — bấm Bắt đầu phản biện.")));
    } else if (R.tab === "meta") {
      b.append(state.meta ? h("div.panelbox", {}, state.meta.decision ? h("div.row", { style: "margin:10px 0" }, h("span.chip.accent", {}, state.meta.decision)) : null, PL.rich(h("div.prose"), state.meta.text)) : h("p.muted", {}, PL.t("Chưa có ý kiến chủ tịch hội đồng.")));
    } else if (R.tab === "issues") {
      if (!state.issues.length) { b.append(h("p.muted", {}, PL.t("Chưa có danh sách vấn đề."))); return; }
      for (const it of state.issues) b.append(issueNode(it, state.fixes[it.id]));
    } else if (R.tab === "guide") {
      if (!state.issues.length) { b.append(h("p.muted", {}, PL.t("Chạy phản biện trước — hướng dẫn được soạn từ danh sách vấn đề và đề xuất sửa."))); return; }
      const intro = h("div.row.wrap", { style: "margin:10px 0" },
        h("span.grow.muted", {}, PL.t("Hướng dẫn chi tiết cho tác giả: kế hoạch sửa theo mức độ, từng bước sửa cho mỗi vấn đề, ví dụ đoạn đã sửa, tiêu chí hoàn thành và câu trả lời reviewer.")),
        h("button.btn.accent", { type: "button", disabled: R.busy || null, onclick: () => stage({ stage: "guide", language: PL.lang }, PL.t("Đang soạn hướng dẫn sửa bài…")) },
          h("span", { html: PL.icon("spark") }), state.guide ? PL.t("Soạn lại bằng AI") : PL.t("Soạn hướng dẫn bằng AI")));
      b.append(intro);
      if (state.guide) b.append(h("div.panelbox", {}, PL.rich(h("div.prose"), state.guide.text)));
      else b.append(h("p.muted", {}, PL.t("Chưa có bản do AI soạn. Bạn vẫn có thể tải bản hướng dẫn tự động (từ vấn đề + đề xuất sửa) ở mục Xuất bên dưới.")));
    } else {
      b.append(state.response ? h("div.panelbox", {}, PL.rich(h("div.prose"), state.response.text)) :
        h("div", {}, h("p.muted", {}, PL.t("Thư phản hồi reviewer được soạn từ các vấn đề và trạng thái xử lý của bạn.")),
          h("button.btn.accent", { type: "button", onclick: () => stage({ stage: "response" }, PL.t("Thư phản hồi")) }, PL.t("Soạn thư phản hồi"))));
    }
  }

  function issueNode(it, fx) {
    const node = h("div.issue", {},
      h("div.h", {}, h("span.chip." + (SEV[it.severity] || ""), {}, it.severity), h("span.t", {}, it.title), h("span.muted", { style: "font-size:12px" }, it.location),
        h("select.input", { style: "width:auto;height:26px;padding:0 6px;font-size:12px", onchange: (e) => setIssue(it, { status: e.target.value }) },
          [["open", PL.t("Chưa xử lý")], ["done", PL.t("Đã xử lý")], ["wontfix", PL.t("Không sửa")]].map(([k, l]) => h("option", { value: k, selected: it.status === k || null }, l)))),
      h("div", { style: "margin-top:6px;font-size:13.5px" }, it.problem),
      it.fix ? h("div.muted", { style: "font-size:13px;margin-top:4px" }, PL.t("Gợi ý: ") + it.fix) : null);
    if (fx) {
      node.append(h("div.diff-pair", {}, h("pre.old", {}, fx.original || PL.t("(không trích được đoạn gốc)")), h("pre.new", {}, fx.revised || fx.plan || "")),
        fx.note ? h("div.muted", { style: "font-size:12.5px;margin-top:4px" }, fx.note) : null,
        h("div.row", { style: "margin-top:8px" }, h("span.chip" + (fx.status === "accepted" ? ".ok" : fx.status === "dismissed" ? "" : ".warn"), {}, { proposed: PL.t("chờ duyệt"), accepted: PL.t("đã chấp nhận"), dismissed: PL.t("đã bỏ qua") }[fx.status] || fx.status),
          !fx.original_found && fx.original ? h("span.chip.err", {}, PL.t("không khớp nguyên văn")) : null, h("span.grow"),
          h("button.btn.sm", { type: "button", onclick: () => setIssue(it, { fix_status: "dismissed" }) }, PL.t("Bỏ qua")),
          h("button.btn.sm.accent", { type: "button", onclick: () => setIssue(it, { fix_status: "accepted", status: "done" }) }, PL.t("Chấp nhận sửa"))));
    } else {
      node.append(h("div.row", { style: "margin-top:8px" }, h("span.grow"), h("button.btn.sm", { type: "button", onclick: () => stage({ issue_id: it.id }, PL.t("Sửa ") + it.id, "fix") }, h("span", { html: PL.icon("spark") }), PL.t("Đề xuất sửa"))));
    }
    return node;
  }
  async function setIssue(it, body) {
    await PL.safe(() => PL.put(`/api/review/${R.data.meta.id}/issue/${it.id}`, body));
    load(R.data.meta.id);
  }

  /** POST a stage and stream its text into a progress card (start → delta… → done | error). */
  async function stage(body, label, path) {
    const prog = PL.$("#rv-prog");
    const out = h("div.stream-out");
    const box = h("div.card", {}, h("div.card-h", {}, h("span.spin"), h("span.ttl", {}, label)), h("div.card-b", {}, out));
    if (prog) prog.replaceChildren(box);
    const done = await PL.sse(`/api/review/${R.data.meta.id}/${path || "stage"}`, body, (t) => { out.textContent = t.slice(-1500); });
    if (prog) prog.replaceChildren();
    if (done) await load(R.data.meta.id);
    return done;
  }

  async function runAll() {
    if (R.busy) return;
    R.busy = true;
    const n = R.data.meta.n_reviewers || 3;
    try {
      for (let i = 1; i <= n; i++) {
        R.tab = "R" + i;
        if (!(await stage({ stage: "reviewer", idx: i, fresh: i === 1 }, PL.t("Reviewer {0}/{1} đang đọc bản thảo…", i, n)))) return;
      }
      R.tab = "meta";
      if (!(await stage({ stage: "meta" }, PL.t("Chủ tịch hội đồng tổng hợp…")))) return;
      R.tab = "issues";
      await stage({ stage: "issues" }, PL.t("Lập danh sách vấn đề…"));
      PL.toast(PL.t("Phản biện xong — duyệt từng vấn đề và đề xuất sửa"));
    } finally {
      R.busy = false;
      paint();
    }
  }
  R.runAll = runAll;
})(window);
