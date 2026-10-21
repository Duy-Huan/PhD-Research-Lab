/* PhD Research Lab — the research chat: conversations, streaming answers, "/" skills, attachments, model picker,
   proposals the researcher accepts or rejects, live cards of background research runs. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document, h = PL.h;
  const C = (PL.chat = { sid: null, s: null, sse: null, atts: [], skills: [], models: null, list: [], live: {}, runCards: {} });

  const ACTION = (PL.ACTION = {
    update_outline: "Cập nhật đề cương", start_run: "Chạy trong nền", write_section: "Lưu phần bài báo", commit_code: "Commit code",
    add_decision: "Khoá quyết định", propose_gap: "Ghi research gap", create_hypothesis: "Thêm giả thuyết",
    create_experiment: "Tạo thí nghiệm", record_result: "Ghi kết quả vào bộ nhớ", pin_result: "Ghim kết quả",
    propose_memory: "Ghi nhớ", add_note: "Ghi chú dự án",
  });
  const MEM_TYPE = { decision: "Quyết định", finding: "Phát hiện", hypothesis: "Giả thuyết", experiment: "Thí nghiệm",
    knowledge: "Kiến thức", open_question: "Câu hỏi mở", rejected_approach: "Hướng bị loại", claim: "Nhận định", note: "Ghi chú",
    experiment_result: "Kết quả thí nghiệm" };
  const STARTERS = [
    ["/outline", "Xây đề cương từ từ khoá"], ["/lit", "Tổng quan tài liệu"], ["/gap", "Tìm research gap"],
    ["/idea", "Chạy thử ý tưởng ngay"], ["/write", "Viết một phần bài báo"], ["/status", "Tiến độ dự án"],
  ];

  // ------------------------------------------------------------------ conversation list (sidebar)
  C.loadList = async function () {
    const q = (PL.$("#search") || {}).value || "";
    const r = await PL.get("/api/chat/sessions?q=" + encodeURIComponent(q)).catch(() => ({ sessions: [] }));
    C.list = r.sessions;
    renderList();
  };
  function renderList() {
    const box = PL.$("#threads");
    if (!box) return;
    box.innerHTML = "";
    if (!C.list.length) { box.append(h("div.tgroup", {}, "Chưa có cuộc trò chuyện")); return; }
    const now = Date.now() / 1000;
    const groups = [["Hôm nay", (s) => now - s.updated < 86400], ["7 ngày qua", (s) => now - s.updated < 7 * 86400], ["Cũ hơn", () => true]];
    const used = new Set();
    for (const [label, fn] of groups) {
      const items = C.list.filter((s) => !used.has(s.id) && fn(s));
      if (!items.length) continue;
      box.append(h("div.tgroup", {}, label));
      for (const s of items) {
        used.add(s.id);
        const row = h("div.thread" + (s.id === C.sid ? ".active" : ""), { role: "link", tabindex: "0", title: s.title,
          onclick: () => PL.go("#/chat/" + s.id), onkeydown: (e) => { if (e.key === "Enter") PL.go("#/chat/" + s.id); } },
          h("span.t", {}, s.title || "Cuộc trò chuyện"),
          s.pending_approvals ? h("span.badge", { title: "Đề xuất chờ bạn duyệt" }, s.pending_approvals) : null,
          s.status === "running" ? h("span.spin") : null,
          h("button.icon.more", { type: "button", "aria-label": "Tuỳ chọn", html: PL.icon("dots"), onclick: (e) => { e.stopPropagation(); threadMenu(e.currentTarget, s); } }));
        box.append(row);
      }
    }
  }
  function threadMenu(anchor, s) {
    PL.menu(anchor, [
      { label: "Đổi tên", run: async () => { const t = await PL.prompt("Đổi tên", "Tên cuộc trò chuyện", s.title); if (t) { await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { title: t })); C.loadList(); } } },
      { label: "Lưu trữ", run: async () => { await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { archived: true })); if (C.sid === s.id) PL.go("#/"); C.loadList(); } },
      { label: "Xoá", danger: true, run: async () => {
        if (!(await PL.confirm(`Xoá "${s.title}"? (file được chuyển vào thùng rác của dự án)`, "Xoá"))) return;
        await PL.safe(() => PL.del(`/api/chat/sessions/${s.id}?confirm=${s.id}`));
        if (C.sid === s.id) PL.go("#/");
        C.loadList();
      } },
    ]);
  }

  /** A small popup menu next to an element: items [{label, run, danger, disabled, hint}]. */
  PL.menu = function (anchor, items, opts) {
    PL.$$(".menu.pop").forEach((m) => m.remove());
    const m = h("div.menu.pop", { role: "menu" });
    for (const it of items) {
      if (it.header) { m.append(h("div.mh", {}, it.header)); continue; }
      m.append(h("button.mi", { type: "button", role: "menuitem", disabled: it.disabled || null,
        style: it.danger ? "color: var(--err)" : null, onclick: () => { m.remove(); it.run && it.run(); } },
      h("span.grow", {}, it.label, it.hint ? h("div.d", {}, it.hint) : null), it.tag ? h("span.tag.chip", {}, it.tag) : null));
    }
    D.body.append(m);
    const r = anchor.getBoundingClientRect();
    const below = !(opts && opts.above);
    m.style.left = Math.max(8, Math.min(r.left, W.innerWidth - m.offsetWidth - 8)) + "px";
    if (below) m.style.top = Math.min(r.bottom + 4, W.innerHeight - m.offsetHeight - 8) + "px";
    else m.style.top = Math.max(8, r.top - m.offsetHeight - 4) + "px";
    const off = (e) => { if (!m.contains(e.target)) { m.remove(); D.removeEventListener("mousedown", off, true); } };
    W.setTimeout(() => D.addEventListener("mousedown", off, true), 0);
    return m;
  };

  // ------------------------------------------------------------------ open / new
  C.open = async function (sid) {
    if (C.sse) { C.sse.close(); C.sse = null; }
    C.sid = sid || null;
    C.s = null;
    C.live = {};
    C.runCards = {};
    renderList();
    renderShell();
    if (!sid) { renderEmpty(); return; }
    try {
      C.s = await PL.get("/api/chat/sessions/" + sid);
    } catch (e) {
      PL.toast(e.message, "err");
      PL.go("#/");
      return;
    }
    PL.setTitle(C.s.title, "");
    renderMessages(true);
    C.sse = PL.stream(`/api/chat/sessions/${sid}/stream`, onEvent, { after: C.s.last_seq || 0 });
  };

  function renderShell() {
    const v = PL.$("#view");
    v.innerHTML = "";
    v.append(h("section#thread", { "aria-live": "polite" }, h("div#msgs")), composer());
    PL.setTitle(C.sid ? "…" : "", "");
    attachDrop(PL.$("#thread"));
  }

  async function renderEmpty() {
    const msgs = PL.$("#msgs");
    msgs.innerHTML = "";
    const wrap = h("div");
    const [o, d] = await Promise.all([PL.get("/api/outline").catch(() => null), PL.get("/api/dashboard").catch(() => null)]);
    const name = (PL.state.project || {}).name || "";
    wrap.append(h("div.hello", {}, h("img.mark", { src: "/img/logo-128.png", alt: "" }),
      h("h1", {}, o && o.level ? "Hôm nay nghiên cứu gì?" : "Bắt đầu một nghiên cứu"),
      h("p", {}, name ? `Dự án ${name}` + (o && o.level ? ` · đề cương cấp ${o.level}/5 — ${o.level_label}` : "") : "")));
    if (d) {
      const line = h("div.state-line");
      if (d.current) line.append(h("span.chip.info", {}, h("span.spin"), d.current.title));
      if (d.pending && d.pending.length) line.append(h("button.chip.warn", { type: "button", onclick: () => PL.go("#/dashboard") }, `${d.pending.length} việc chờ bạn duyệt`));
      if (line.childNodes.length) wrap.append(line);
    }
    if (o && o.level < 1 && !(o.attachments || []).length) wrap.append(PL.panels.outlineStarter(o));
    msgs.append(wrap);
    const st = h("div.starters");
    for (const [cmd, label] of STARTERS) st.append(h("button.starter", { type: "button", onclick: () => setInput(cmd + " ") }, h("b", {}, cmd), label));
    msgs.append(st);
    PL.$("#input").focus();
  }

  // ------------------------------------------------------------------ rendering
  function nearBottom() {
    const t = PL.$("#thread");
    return !t || t.scrollHeight - t.scrollTop - t.clientHeight < 160;
  }
  function toBottom(force) {
    const t = PL.$("#thread");
    if (t && (force || nearBottom())) t.scrollTop = t.scrollHeight;
  }

  function timeline() {
    const s = C.s;
    const items = [];
    const answerTs = {};
    for (const m of s.messages) {
      items.push({ k: "msg", ts: m.ts, m });
      if (m.role === "assistant" && m.turn_id) answerTs[m.turn_id] = m.ts;
    }
    for (const a of s.approvals) {
      if (a.kind === "apply_artifact") continue;
      const after = a.turn_id && answerTs[a.turn_id] ? answerTs[a.turn_id] + 0.0005 : 0;
      items.push({ k: "ap", ts: Math.max(a.created || 0, after), a });
    }
    for (const it of s.memory_items || []) {
      const msg = s.messages.find((m) => (it.message_ids || []).includes(m.id));
      items.push({ k: "mem", ts: (msg ? msg.ts : 0) + 0.0007, it });
    }
    for (const a of s.artifacts || []) items.push({ k: "art", ts: (answerTs[a.turn_id] || a.created || 0) + 0.0009, a });
    return items.sort((x, y) => x.ts - y.ts);
  }

  function renderMessages(scroll) {
    const box = PL.$("#msgs");
    if (!box || !C.s) return;
    const keep = nearBottom();
    box.innerHTML = "";
    if (!C.s.messages.length) { renderEmpty(); return; }
    for (const it of timeline()) {
      if (it.k === "msg") box.append(messageNode(it.m));
      else if (it.k === "ap") box.append(approvalCard(it.a));
      else if (it.k === "mem") box.append(memoryCard(it.it));
      else box.append(artifactCard(it.a));
    }
    const running = (C.s.turns || []).find((t) => ["running", "queued", "waiting_approval", "awaiting_launch"].includes(t.status));
    if (running) box.append(liveNode(running));
    setBusy(!!running);
    if (scroll || keep) toBottom(true);
  }

  function messageNode(m) {
    if (m.role === "user") {
      return h("div.msg.user", { dataset: { id: m.id } }, h("div.bubble", {}, m.content));
    }
    const prose = h("div.prose");
    PL.rich(prose, m.content || (m.status === "cancelled" ? "_(đã dừng)_" : ""));
    const who = h("div.who", {}, h("img", { src: "/img/logo-64.png", alt: "" }),
      m.provider === "phdlab" ? "PhD Lab" : providerLabel(m.provider) + (m.model ? " · " + m.model : ""),
      m.status === "partial" ? h("span.chip.warn", {}, "chưa đầy đủ") : null);
    const node = h("div.msg.ai", { dataset: { id: m.id } }, who, prose);
    if (m.run_id) node.append(runCard(m.run_id));
    node.append(h("div.msg-actions", {},
      act("copy", "Sao chép", () => PL.copy(m.content)),
      m.provider !== "phdlab" ? act("retry", "Tạo lại câu trả lời", () => retry()) : null,
      act("brain", "Ghi nhớ vào dự án", () => rememberDialog(m)),
      act("pin", "Ghim vào kết quả", () => pinMessage(m))));
    return node;
  }
  const act = (icon, title, fn) => h("button.icon", { type: "button", title, "aria-label": title, html: PL.icon(icon), onclick: fn });

  function providerLabel(pid) {
    const p = ((C.models || {}).providers || []).find((x) => x.id === pid);
    if (p) return p.label;
    return { "app:auto": "Research agent" }[pid] || pid || "Research agent";
  }

  function liveNode(t) {
    const live = C.live[t.id] || (C.live[t.id] = { text: "", activity: "" });
    const prose = h("div.prose");
    if (live.text) PL.rich(prose, live.text);
    else prose.append(h("span.typing", {}, h("i"), h("i"), h("i")));
    live.el = prose;
    const node = h("div.msg.ai.live", { dataset: { turn: t.id } }, h("div.who", {}, h("img", { src: "/img/logo-64.png", alt: "" }), providerLabel((C.s.settings || {}).provider || "app:auto")));
    if (live.activity || t.status !== "running") node.append(h("div.activity", {}, h("span.spin"), activityText(t, live)));
    node.append(prose);
    if (t.status === "awaiting_launch") {
      node.append(h("div.row", {}, h("button.btn.accent.sm", { type: "button", onclick: () => PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/turns/${t.id}/launch`)) }, "Gửi cho mô hình")));
    }
    return node;
  }
  function activityText(t, live) {
    if (t.status === "waiting_approval") return "Đang chờ bạn duyệt công cụ…";
    if (t.status === "awaiting_launch") return "Chế độ thủ công: xem ngữ cảnh rồi bấm Gửi";
    return live.activity || "Đang suy nghĩ…";
  }

  // ------------------------------------------------------------------ cards: proposals (Accept / Reject)
  function approvalCard(a) {
    const pending = a.status === "pending";
    if (a.kind === "tool" && !pending) {  // read-only tools the policy ran on its own: one quiet activity line
      return h("div.activity", {}, h("span", { html: PL.icon(a.status === "executed" ? "check" : "alert") }),
        `${a.status === "executed" ? "Đã dùng" : "Không dùng được"} công cụ ${a.name}` + (a.decided_by && a.decided_by.startsWith("auto") ? " (tự động, chỉ đọc)" : ""));
    }
    const label = a.kind === "tool" ? "Dùng công cụ: " + a.name : (ACTION[a.name] || a.name);
    const card = h("div.card" + (pending ? ".pending" : ".done"), { dataset: { ap: a.id } },
      h("div.card-h", {}, h("span.kind", {}, a.kind === "tool" ? "Công cụ" : "Đề xuất"), h("span.ttl", {}, label), verdictChip(a)),
      h("div.card-b", {}, proposalBody(a)),
      h("div.card-f", {},
        a.reason ? h("span.muted", { style: "font-size:12px" }, a.reason) : null, h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: () => decide(a, "reject") }, "Bỏ qua"),
        h("button.btn.accent.sm", { type: "button", onclick: () => decide(a, "approve") }, h("span", { html: PL.icon("check") }), "Chấp nhận")));
    return card;
  }
  function verdictChip(a) {
    const map = { pending: ["warn", "chờ duyệt"], executed: ["ok", "đã chấp nhận"], approved: ["ok", "đã chấp nhận"],
      rejected: ["", "đã bỏ qua"], failed: ["err", "lỗi"], denied: ["err", "bị chặn"], cancelled: ["", "đã huỷ"] };
    const [k, t] = map[a.status] || ["", a.status];
    return h("span.chip" + (k ? "." + k : ""), {}, t);
  }
  function proposalBody(a) {
    const g = a.args || {};
    const box = h("div");
    if (a.name === "start_run") box.append(h("div", {}, h("b", {}, "/" + g.skill), " ", h("span", {}, String(g.input || "").slice(0, 400))));
    else if (a.name === "write_section") {
      box.append(h("div.muted", {}, "Phần: " + g.section));
      const p = h("div.preview-box.prose");
      p.textContent = String(g.text || "").slice(0, 4000);
      box.append(p);
    } else if (a.name === "update_outline") {
      const dl = h("dl.kv");
      for (const [k, v] of Object.entries(g)) if (v) dl.append(h("dt", {}, ({ keywords: "Từ khoá", topic: "Chủ đề", direction: "Định hướng", method: "Phương pháp", proposal: "Đề cương" })[k] || k), h("dd", {}, String(v).slice(0, k === "proposal" ? 600 : 1200)));
      box.append(dl);
    } else if (a.name === "commit_code") {
      box.append(h("div", {}, g.message), h("div.preview-box.mono", {}, (g.files || []).join("\n")));
    } else if (g.text || g.body || g.title) {
      if (g.title) box.append(h("div", {}, h("b", {}, g.title)));
      const t = g.text || g.body;
      if (t) { const p = h("div.prose"); PL.rich(p, String(t).slice(0, 3000)); box.append(p); }
    } else box.append(h("pre.preview-box.mono", {}, JSON.stringify(g, null, 1)));
    if (a.result && (a.result.error || a.result.text)) box.append(h("div.err-line", {}, a.result.error || a.result.text));
    if (a.status === "executed" && a.result) {
      const r = a.result;
      if (r.run) box.append(runCard(r.run));
      else if (r.pin) box.append(h("div.muted", {}, "Đã ghim " + r.pin));
    }
    return box;
  }
  async function decide(a, decision) {
    const card = PL.$(`.card[data-ap="${a.id}"]`);
    if (card) card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    const r = await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/approvals/${a.id}`, { decision }));
    if (r && r.status === "failed") PL.toast("Không thực hiện được: " + ((r.result || {}).error || ""), "err");
    else if (r) PL.toast(decision === "approve" ? "Đã chấp nhận" : "Đã bỏ qua");
    await refresh();
  }

  function memoryCard(it) {
    const pending = it.status === "pending" || it.status === "duplicate";
    return h("div.card" + (pending ? ".pending" : ".done"), {},
      h("div.card-h", {}, h("span.kind", {}, "Đề xuất ghi nhớ"), h("span.ttl", {}, MEM_TYPE[it.type] || it.type),
        h("span.chip" + (pending ? ".warn" : it.status === "approved" ? ".ok" : ""), {}, { pending: "chờ duyệt", duplicate: "có thể trùng", approved: "đã lưu", rejected: "đã bỏ qua" }[it.status] || it.status)),
      h("div.card-b", {}, it.text, it.conflicts ? h("div.err-line", {}, `Mâu thuẫn với ${it.conflicts} mục đã có — kiểm tra trước khi lưu`) : null),
      h("div.card-f", {}, h("span.muted", { style: "font-size:12px" }, "Bộ nhớ ngữ cảnh chạy nền — chỉ lưu khi bạn chấp nhận"), h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${it.id}/reject`, {})); refresh(); } }, "Bỏ qua"),
        h("button.btn.accent.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${it.id}/approve`, {}), "Đã lưu vào bộ nhớ dự án"); refresh(); } }, "Chấp nhận")));
  }

  function artifactCard(a) {
    const open = a.status === "collected";
    return h("div.card" + (open ? ".pending" : ".done"), {},
      h("div.card-h", {}, h("span.kind", {}, "File đề xuất"), h("span.ttl.mono", {}, a.path), h("span.chip", {}, { collected: "chờ duyệt", applied: "đã áp dụng", rejected: "đã bỏ qua" }[a.status] || a.status)),
      h("div.card-f", {}, h("button.btn.sm", { type: "button", onclick: () => PL.panels.artifact(C.sid, a) }, "Xem & so sánh"), h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/artifacts/${a.id}/reject`, {})); refresh(); } }, "Bỏ qua"),
        h("button.btn.accent.sm", { type: "button", onclick: () => PL.panels.artifact(C.sid, a, true) }, "Áp dụng vào code")));
  }

  // ------------------------------------------------------------------ run cards (live)
  function runCard(rid) {
    const card = h("div.card.run", { dataset: { run: rid } }, h("div.card-b", {}, h("span.spin")));
    (C.runCards[rid] = C.runCards[rid] || []).push(card);
    PL.get("/api/runs/" + rid).then((r) => fillRun(card, r)).catch(() => { card.innerHTML = ""; card.append(h("div.card-b.muted", {}, "Run " + rid + " không còn")); });
    return card;
  }
  C.refreshRun = async function (rid) {
    const cards = (C.runCards[rid] || []).filter((c) => c.isConnected);
    if (!cards.length) return;
    const r = await PL.get("/api/runs/" + rid).catch(() => null);
    if (r) cards.forEach((c) => fillRun(c, r));
  };
  function fillRun(card, r) {
    card.innerHTML = "";
    card.className = "card run" + (["APPROVAL_PENDING", "NEEDS_USER_ACTION"].includes(r.status) ? " pending" : "");
    const cur = r.steps.find((s) => s.id === r.current) || {};
    const steps = h("div.steps", {}, r.steps.map((s) => h("i." + (s.status || "pending"), { title: `${s.label} · ${s.provider} · ${s.status}` })));
    const body = h("div.card-b", {}, steps,
      h("div.row", {}, h("span.grow.ellipsis.muted", {}, ["RUNNING", "VERIFYING", "BLOCKED", "RECOVERING"].includes(r.status) ? `${cur.label || ""} · ${cur.provider || ""}` :
        ["COMPLETED", "CANCELLED"].includes(r.status) ? `${r.steps.length} bước` : r.reason || ""),
        r.synthetic ? h("span.chip.warn", {}, "SYNTHETIC") : null));
    if (r.status === "NEEDS_USER_ACTION" && (r.proposal || r.next_decision)) body.append(h("div.preview-box", {}, (r.proposal && r.proposal.text) || r.next_decision));
    if (r.status === "COMPLETED" && r.outputs.length) {
      body.append(h("div.row", { style: "flex-wrap:wrap;margin-top:6px" }, r.outputs.slice(0, 8).map((o) =>
        h("button.chip", { type: "button", onclick: () => PL.panels.file(o.path) }, h("span", { html: PL.icon("file") }), o.path.split("/").pop()))));
    }
    const sources = PL.panels.runSources(r);
    if (sources.length) {
      const list = h("details", { style: "margin-top:10px" }, h("summary", { style: "cursor:pointer" }, `${sources.length} nguồn tìm được · xem & lưu vào thư viện`));
      list.append(h("div", {}, sources.map((s) => PL.panels.paperCard(s))));
      body.append(list);
    }
    const f = h("div.card-f", {});
    f.append(h("button.btn.sm.ghost", { type: "button", onclick: () => PL.panels.run(r.id) }, "Chi tiết"), h("span.spacer"));
    if (r.status === "APPROVAL_PENDING") {
      f.append(h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, "Huỷ"),
        h("button.btn.accent.sm", { type: "button", onclick: () => runAct(r, "approve") }, h("span", { html: PL.icon("play") }), "Chấp nhận & chạy"));
    } else if (r.status === "NEEDS_USER_ACTION") {
      f.append(h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, "Huỷ run"),
        h("button.btn.sm", { type: "button", onclick: () => runAct(r, "resume", { accept: false }) }, "Thử lại"),
        r.proposal && r.proposal.patch && Object.keys(r.proposal.patch).length ?
          h("button.btn.accent.sm", { type: "button", onclick: () => runAct(r, "resume", { accept: true }) }, "Áp dụng đề xuất & tiếp tục") : null);
    } else if (!["COMPLETED", "CANCELLED"].includes(r.status)) {
      f.append(h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, "Dừng"));
    }
    card.append(h("div.card-h", {}, h("span.kind", {}, "Run"), h("span.ttl.ellipsis", { title: r.title }, r.title), PL.statusChip(r.status)), body, f);
  }
  async function runAct(r, what, body) {
    if (what === "cancel" && !(await PL.confirm(`Huỷ run "${r.title}"?`, "Huỷ run"))) return;
    await PL.safe(() => PL.post(`/api/runs/${r.id}/${what}`, body || {}), { approve: "Đã duyệt — run bắt đầu", cancel: "Đã huỷ", resume: "Đang tiếp tục" }[what]);
    C.refreshRun(r.id);
  }
  PL.runAct = runAct;

  // ------------------------------------------------------------------ live events of the open conversation
  let rt = 0;
  function onEvent(ev) {
    const d = ev.data || {};
    const live = ev.turn_id ? (C.live[ev.turn_id] = C.live[ev.turn_id] || { text: "", activity: "" }) : null;
    switch (ev.type) {
      case "turn.started":
        refresh();
        break;
      case "message.delta":
        live.text += d.text || "";
        if (live.el) { PL.rich(live.el, live.text); toBottom(); }
        else refresh();
        break;
      case "context.compiled":
        live.activity = `Đã dùng ${d.sources} nguồn ngữ cảnh (${d.tokens} token)`;
        break;
      case "status.updated":
        if (d.intent && live) live.activity = `Kỹ năng /${d.intent}`;
        break;
      case "tool.started":
        if (live) live.activity = "Đang dùng công cụ " + (d.tool || "");
        break;
      case "run.updated":
        C.refreshRun(d.run_id);
        break;
      case "message.completed": case "turn.completed": case "turn.failed": case "turn.cancelled":
      case "action.approval_required": case "tool.approval_required": case "memory.candidate": case "memory.saved":
      case "action.completed": case "action.failed": case "artifact.discovered": case "artifact.updated": case "session.updated":
        if (ev.type === "turn.failed") PL.toast("Lỗi: " + (d.message || ""), "err");
        W.clearTimeout(rt);
        rt = W.setTimeout(refresh, 60);
        break;
      default:
    }
  }
  async function refresh() {
    if (!C.sid) return;
    try { C.s = await PL.get("/api/chat/sessions/" + C.sid); } catch (e) { return; }
    PL.setTitle(C.s.title, "");
    renderMessages(false);
    C.loadList();
  }
  C.refresh = refresh;

  // ------------------------------------------------------------------ composer
  function composer() {
    const ta = h("textarea#input", { rows: "1", placeholder: "Hỏi, giao việc, hoặc gõ / để chọn kỹ năng…", "aria-label": "Tin nhắn" });
    const file = h("input", { type: "file", multiple: true, hidden: true, onchange: (e) => { addFiles(e.target.files); e.target.value = ""; } });
    const send = h("button.send#send", { type: "button", "aria-label": "Gửi", html: PL.icon("send"), onclick: () => (C.busy ? stop() : submit()) });
    const model = h("button.model-btn#model", { type: "button", title: "Mô hình cho cuộc trò chuyện này", onclick: (e) => modelMenu(e.currentTarget) }, "…");
    const box = h("div.composer", {},
      h("div.atts#atts"), ta,
      h("div.bar", {},
        h("button.icon", { type: "button", title: "Đính kèm file (PDF, Word, Markdown, dữ liệu, ảnh…)", "aria-label": "Đính kèm file", html: PL.icon("clip"), onclick: () => file.click() }), file,
        h("button.icon", { type: "button", title: "Kỹ năng (/)", "aria-label": "Kỹ năng", html: PL.icon("spark"), onclick: () => { setInput("/"); slash(); } }),
        h("span.grow"), model, send));
    ta.addEventListener("input", () => { autosize(ta); slash(); updateSend(); });
    ta.addEventListener("keydown", onKey);
    ta.addEventListener("paste", (e) => { const fs = e.clipboardData && e.clipboardData.files; if (fs && fs.length) { e.preventDefault(); addFiles(fs); } });
    W.setTimeout(() => { renderAtts(); paintModel(); updateSend(); }, 0);
    return h("footer#composer-wrap", {}, box, h("div.composer-hint", {}, "Enter để gửi · Shift+Enter xuống dòng · mọi việc có thay đổi dự án đều chờ bạn Chấp nhận"));
  }
  function autosize(ta) { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, W.innerHeight * 0.4) + "px"; }
  function setInput(t) { const ta = PL.$("#input"); if (!ta) return; ta.value = t; autosize(ta); ta.focus(); ta.setSelectionRange(t.length, t.length); updateSend(); }
  C.setInput = setInput;
  function updateSend() {
    const b = PL.$("#send"), ta = PL.$("#input");
    if (!b || !ta) return;
    b.disabled = !C.busy && !ta.value.trim() && !C.atts.length;
  }
  function setBusy(v) {
    C.busy = v;
    const b = PL.$("#send");
    if (!b) return;
    b.classList.toggle("stop", v);
    b.innerHTML = PL.icon(v ? "stop" : "send");
    b.setAttribute("aria-label", v ? "Dừng" : "Gửi");
    updateSend();
  }

  // "/" menu
  let sel = 0;
  function slash() {
    const ta = PL.$("#input");
    const old = PL.$(".menu.slash");
    const m = /^\/([\w-]*)$/.exec(ta.value);
    if (!m) { if (old) old.remove(); return; }
    const q = m[1].toLowerCase();
    const list = C.skills.filter((s) => s.name.startsWith(q) || s.aliases.some((a) => a.startsWith(q)) || (q.length > 1 && s.title.toLowerCase().includes(q)));
    if (old) old.remove();
    if (!list.length) return;
    sel = Math.min(sel, list.length - 1);
    const menu = h("div.menu.slash", { role: "listbox" });
    const cats = { research: "Nghiên cứu", experiment: "Thí nghiệm", writing: "Viết bài", system: "Hệ thống" };
    let cur = "";
    list.forEach((s, i) => {
      if (s.category !== cur) { cur = s.category; menu.append(h("div.mh", {}, cats[cur] || cur)); }
      menu.append(h("button.mi" + (i === sel ? ".sel" : ""), { type: "button", role: "option", onmousedown: (e) => { e.preventDefault(); pick(s); } },
        h("span.c", {}, "/" + s.name), h("span.grow", {}, s.title, h("div.d", {}, s.description)),
        s.mode === "run" ? h("span.tag.chip" + (s.risk >= 2 ? ".warn" : ".info"), {}, s.risk >= 2 ? "cần duyệt" : "chạy nền") : null));
    });
    menu._list = list;
    PL.$(".composer").append(menu);
  }
  function pick(s) { setInput("/" + s.name + " "); const m = PL.$(".menu.slash"); if (m) m.remove(); }
  function onKey(e) {
    const m = PL.$(".menu.slash");
    if (m && ["ArrowDown", "ArrowUp", "Tab", "Enter", "Escape"].includes(e.key)) {
      const list = m._list;
      if (e.key === "Escape") { m.remove(); return; }
      e.preventDefault();
      if (e.key === "ArrowDown") sel = (sel + 1) % list.length;
      else if (e.key === "ArrowUp") sel = (sel - 1 + list.length) % list.length;
      else return pick(list[sel]);
      slash();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!C.busy) submit(); }
  }

  // attachments
  async function addFiles(files) {
    for (const f of Array.from(files || [])) {
      const tmp = { id: "", name: f.name, pending: true, file: f };
      C.atts.push(tmp);
      renderAtts();
      try {
        const a = await PL.upload("/api/chat/attachments", f);
        Object.assign(tmp, { id: a.id, pending: false, kind: a.kind, chars: a.chars });
      } catch (e) {
        C.atts.splice(C.atts.indexOf(tmp), 1);
        PL.toast(`${f.name}: ${e.message}`, "err");
      }
      renderAtts();
    }
  }
  C.addFiles = addFiles;
  function renderAtts() {
    const box = PL.$("#atts");
    if (!box) return;
    box.innerHTML = "";
    for (const a of C.atts) {
      box.append(h("span.att", { title: a.name }, a.pending ? h("span.spin") : h("span", { html: PL.icon("file") }), h("span.n", {}, a.name),
        /\.pdf$/i.test(a.name) && !a.pending ? h("button", { type: "button", title: "Lưu bản PDF này vào Thư viện dự án", onclick: () => PL.safe(() => PL.upload("/api/library/upload", a.file, "files"), "Đã thêm vào Thư viện") }, "＋TV") : null,
        h("button", { type: "button", "aria-label": "Bỏ " + a.name, onclick: () => { C.atts.splice(C.atts.indexOf(a), 1); renderAtts(); } }, "✕")));
    }
    updateSend();
  }
  function attachDrop(el) {
    el.addEventListener("dragover", (e) => { e.preventDefault(); });
    el.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });
  }

  // model + reasoning picker (one popover: filter, models, "Cấp độ tư duy")
  const LEVEL = { auto: "Tự động", off: "Tắt", low: "Thấp", medium: "Vừa", high: "Cao" };
  C.loadModels = async function () {
    C.models = await PL.get("/api/models").catch(() => null);
    paintModel();
  };
  function setting(k) {
    if (!C.sid) return (C.pending || {})[k] || "";
    return ((C.s || {}).settings || {})[k] || "";
  }
  function currentProvider() { return setting("provider") || (C.models || {}).default || "app:auto"; }
  function providerInfo(pid) { return ((C.models || {}).providers || []).find((p) => p.id === pid) || null; }
  function paintModel() {
    const b = PL.$("#model");
    if (!b) return;
    const pid = currentProvider();
    const lvl = setting("reasoning") || "auto";
    b.innerHTML = "";
    b.append(h("span.ellipsis", {}, pid === "app:auto" ? "Tự động" : providerLabel(pid)));
    if (lvl !== "auto") b.append(h("span.lvl", { title: "Cấp độ tư duy" }, LEVEL[lvl]));
    b.append(h("span", { html: PL.icon("chev") }));
  }
  function modelMenu(anchor) {
    PL.$$(".menu.pop").forEach((m) => m.remove());
    const pop = h("div.menu.pop.picker", { role: "dialog", "aria-label": "Mô hình" });
    const filter = h("input.filter", { type: "search", placeholder: "Lọc mô hình…", "aria-label": "Lọc mô hình" });
    const list = h("div.plist");
    const groups = { router: "", local: "Trên máy này", api: "Cloud API", cli: "CLI (gói đăng ký của bạn)" };
    const paintList = () => {
      const q = filter.value.trim().toLowerCase();
      list.innerHTML = "";
      const cur = currentProvider();
      for (const [t, label] of Object.entries(groups)) {
        const g = ((C.models || {}).providers || []).filter((p) => p.transport === t && (!q || (p.label + " " + p.id).toLowerCase().includes(q)))
          .sort((x, y) => Number(y.available) - Number(x.available));
        if (!g.length) continue;
        if (label) list.append(h("div.mh", {}, label));
        for (const p of g) {
          list.append(h("button.mi" + (p.id === cur ? ".sel" : ""), { type: "button", disabled: !p.available || null, title: p.available ? p.id : p.detail,
            onclick: () => { pop.remove(); setSetting("provider", p.id === "app:auto" ? "" : p.id); } },
          h("span", { html: PL.icon(t === "cli" ? "code" : t === "api" ? "spark" : "gauge") }),
          h("span.grow", {}, p.id === "app:auto" ? "Tự động (Research / Reviewer agent)" : p.label,
            !p.available ? h("div.d", {}, p.state === "NO_KEY" ? "chưa có API key" : p.detail) : null),
          p.id === cur ? h("span", { html: PL.icon("check") }) : null));
        }
      }
      if (!C.models) list.append(h("div.mh", {}, h("span.spin"), " Đang tải danh sách mô hình…"));
      else if (!list.childNodes.length) list.append(h("div.mh", {}, "Không có mô hình phù hợp"));
    };
    filter.addEventListener("input", paintList);
    const info = providerInfo(currentProvider());
    const levels = (info && info.reasoning) || [];
    const lvl = setting("reasoning") || "auto";
    const rrow = h("button.mi.reason", { type: "button", "aria-haspopup": "menu", onclick: (e) => {
      e.stopPropagation();
      PL.$$(".menu.sub").forEach((m) => m.remove());
      const sub = h("div.menu.pop.sub", { role: "menu" }, h("div.mh", {}, "Cấp độ tư duy"),
        ["auto", "off", "low", "medium", "high"].map((k) => h("button.mi" + (k === lvl ? ".sel" : ""), { type: "button",
          disabled: k !== "auto" && !levels.includes(k) || null,
          onclick: () => { pop.remove(); sub.remove(); setSetting("reasoning", k === "auto" ? "" : k); } },
        h("span.grow", {}, LEVEL[k], k === "auto" ? h("div.d", {}, "mặc định của mô hình") : null), k === lvl ? h("span", { html: PL.icon("check") }) : null)));
      D.body.append(sub);
      const pr = pop.getBoundingClientRect(), rr = rrow.getBoundingClientRect();
      const left = pr.left - sub.offsetWidth - 6;
      sub.style.left = (left >= 8 ? left : Math.min(pr.right + 6, W.innerWidth - sub.offsetWidth - 8)) + "px";
      sub.style.top = Math.max(8, Math.min(rr.bottom - sub.offsetHeight, W.innerHeight - sub.offsetHeight - 8)) + "px";
    } }, h("span.grow", {}, "Cấp độ tư duy", !levels.length ? h("div.d", {}, "mô hình này không có điều khiển tư duy") : null),
    h("span.muted", {}, LEVEL[lvl]), h("span", { html: PL.icon("chev"), style: "transform:rotate(-90deg)" }));
    pop.append(h("div.mh", {}, "Mô hình"), filter, list, h("div.sep"), rrow,
      h("button.mi", { type: "button", onclick: () => { pop.remove(); PL.settings.open("models"); } }, h("span.grow.muted", {}, "Cài đặt mô hình & API key…")));
    paintList();
    D.body.append(pop);
    const r = anchor.getBoundingClientRect();
    pop.style.left = Math.max(8, Math.min(r.right - pop.offsetWidth, W.innerWidth - pop.offsetWidth - 8)) + "px";
    pop.style.top = Math.max(8, r.top - pop.offsetHeight - 6) + "px";
    filter.focus();
    const close = () => { pop.remove(); PL.$$(".menu.sub").forEach((m) => m.remove()); D.removeEventListener("mousedown", off, true); };
    const off = (e) => { if (!pop.contains(e.target) && !e.target.closest(".menu.sub")) close(); };
    W.setTimeout(() => D.addEventListener("mousedown", off, true), 0);
    pop.addEventListener("keydown", (e) => { if (e.key === "Escape") { close(); anchor.focus(); } });
    if (!C.models) C.loadModels().then(() => { if (pop.isConnected) paintList(); });
  }
  async function setSetting(k, v) {
    if (!C.sid) {
      C.pending = Object.assign({}, C.pending, { [k]: v });
      paintModel();
      return;
    }
    await PL.safe(() => PL.put("/api/chat/sessions/" + C.sid, v ? { settings: { [k]: v } } : { settings_reset: [k] }));
    await refresh();
    paintModel();
    if (k === "reasoning" && v) {
      const e = await PL.get(`/api/chat/sessions/${C.sid}/effective`).catch(() => null);
      const n = e && (e.notes || []).find((x) => x.setting === "reasoning");
      if (n) PL.toast(n.note);
    }
  }
  C.setSetting = setSetting;

  // ------------------------------------------------------------------ send / stop / retry
  async function submit(textArg) {
    const ta = PL.$("#input");
    const text = (textArg != null ? textArg : ta.value).trim();
    if (C.atts.some((a) => a.pending)) { PL.toast("Đợi file tải lên xong"); return; }
    if (!text && !C.atts.length) return;
    const atts = C.atts.slice();
    const body = { text: text || "Hãy đọc các file đính kèm và tóm tắt những điểm quan trọng cho dự án.", overrides: {} };
    if (atts.length) body.overrides.sources = atts.map((a) => "att:" + a.id);
    if (atts.length) body.text = body.text + "\n\n" + atts.map((a) => `📎 ${a.name}`).join("\n");
    try {
      if (!C.sid) {
        const pend = Object.fromEntries(Object.entries(C.pending || {}).filter(([, v]) => v));
        const s = await PL.post("/api/chat/sessions", Object.keys(pend).length ? { settings: pend } : {});
        C.pending = null;
        ta.value = "";
        C.atts = [];
        W.history.replaceState(null, "", "#/chat/" + s.id);
        await C.open(s.id);
      }
      ta.value = "";
      C.atts = [];
      renderAtts();
      autosize(PL.$("#input"));
      setBusy(true);
      await PL.post(`/api/chat/sessions/${C.sid}/turns`, body);
    } catch (e) {
      setBusy(false);
      PL.toast(e.message, "err");
      if (!PL.$("#input").value) PL.$("#input").value = text;
    }
    refresh();
  }
  C.submit = submit;
  async function stop() {
    const t = ((C.s || {}).turns || []).find((x) => ["running", "queued", "waiting_approval", "awaiting_launch"].includes(x.status));
    if (t) await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/turns/${t.id}/cancel`));
    refresh();
  }
  async function retry() {
    if (C.busy) return;
    setBusy(true);
    await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/retry`, {}));
    refresh();
  }

  function rememberDialog(m) {
    const type = h("select.input", {}, Object.entries({ decision: "Quyết định", finding: "Phát hiện", hypothesis: "Giả thuyết", open_question: "Câu hỏi mở", rejected_approach: "Hướng bị loại", knowledge: "Kiến thức" }).map(([k, v]) => h("option", { value: k }, v)));
    const txt = h("textarea.input", { rows: "5" }, m.content.replace(/```[\s\S]*?```/g, "").slice(0, 1200));
    PL.modal({ title: "Ghi nhớ vào dự án", body: h("div", {}, h("label.field", {}, h("span", {}, "Loại"), type), h("label.field", {}, h("span", {}, "Nội dung (bạn có thể sửa)"), txt)),
      actions: [{ label: "Huỷ" }, { label: "Lưu", kind: "accent", onClick: async () => { await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/memory`, { message_id: m.id, type: type.value, content: txt.value, save: true }), "Đã lưu vào bộ nhớ dự án"); refresh(); } }] });
  }
  async function pinMessage(m) {
    const title = await PL.prompt("Ghim vào kết quả", "Tiêu đề", (C.s.title || "").slice(0, 80));
    if (!title) return;
    await PL.safe(() => PL.post("/api/pins", { kind: "note", title, body: m.content.slice(0, 20000), provenance: { session_id: C.sid, message_id: m.id } }), "Đã ghim");
  }

  C.loadSkills = async function () {
    const r = await PL.get("/api/skills").catch(() => ({ skills: [] }));
    C.skills = r.skills;
  };
})(window);
