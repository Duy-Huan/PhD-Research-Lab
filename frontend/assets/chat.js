/* PhD Research Lab — the research chat: conversations, streaming answers, "/" skills, attachments, model picker,
   proposals the researcher accepts or rejects, live cards of background research runs, notes pinned to points of an
   answer and export of answers / conversations.
   Rendering is keyed: a refresh reuses the DOM node of every message / card whose content did not change, so text
   selections, scroll position, charts and run cards survive live updates; streamed text is painted once per frame. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document, h = PL.h;
  const C = (PL.chat = { sid: null, s: null, sse: null, atts: [], skills: [], models: null, list: [], live: {}, runCards: {}, nodes: new Map() });

  const ACTION = (PL.ACTION = {
    update_outline: PL.t("Cập nhật đề cương"), start_run: PL.t("Chạy trong nền"), write_section: PL.t("Lưu phần bài báo"), commit_code: PL.t("Commit code"),
    add_decision: PL.t("Khoá quyết định"), propose_gap: PL.t("Ghi research gap"), create_hypothesis: PL.t("Thêm giả thuyết"),
    create_experiment: PL.t("Tạo thí nghiệm"), record_result: PL.t("Ghi kết quả vào bộ nhớ"), pin_result: PL.t("Ghim kết quả"),
    propose_memory: PL.t("Ghi nhớ"), add_note: PL.t("Ghi chú dự án"),
  });
  const MEM_TYPE = { decision: PL.t("Quyết định"), finding: PL.t("Phát hiện"), hypothesis: PL.t("Giả thuyết"), experiment: PL.t("Thí nghiệm"),
    knowledge: PL.t("Kiến thức"), open_question: PL.t("Câu hỏi mở"), rejected_approach: PL.t("Hướng bị loại"), claim: PL.t("Nhận định"), note: PL.t("Ghi chú"),
    experiment_result: PL.t("Kết quả thí nghiệm") };
  const STARTERS = [
    ["/outline", PL.t("Xây đề cương từ từ khoá")], ["/lit", PL.t("Tổng quan tài liệu")], ["/gap", PL.t("Tìm research gap")],
    ["/idea", PL.t("Chạy thử ý tưởng ngay")], ["/write", PL.t("Viết một phần bài báo")], ["/status", PL.t("Tiến độ dự án")],
  ];
  const ACTIVE = ["running", "queued", "waiting_approval", "awaiting_launch"];

  // ------------------------------------------------------------------ conversation list (sidebar)
  C.loadList = async function () {
    const q = (PL.$("#search") || {}).value || "";
    const r = await PL.get("/api/chat/sessions?q=" + encodeURIComponent(q)).catch(() => ({ sessions: [] }));
    C.list = r.sessions;
    const groups = await PL.get("/api/chat/projects").catch(() => ({ projects: [] }));
    C.chatProjects = groups.projects;
    renderList();
  };
  let lt = 0;
  C.loadListSoon = () => { W.clearTimeout(lt); lt = W.setTimeout(C.loadList, 500); };
  function renderList() {
    const box = PL.$("#threads");
    if (!box) return;
    const frag = D.createDocumentFragment();
    if (!C.list.length) frag.append(h("div.tgroup", {}, PL.t("Chưa có cuộc trò chuyện")));
    // Calendar boundaries in the user's timezone, never a rolling 24-hour window.
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const week = new Date(today); week.setDate(today.getDate() - 7);
    const groups = [[PL.t("Hôm nay"), s => s.updated * 1000 >= today], [PL.t("Hôm qua"), s => s.updated * 1000 >= yesterday], [PL.t("7 ngày qua"), s => s.updated * 1000 >= week]];
    const months = new Set(C.list.filter(s => s.updated * 1000 < week).map(s => new Date(s.updated * 1000).getFullYear() + "-" + new Date(s.updated * 1000).getMonth()));
    for (const month of months) groups.push([new Intl.DateTimeFormat(PL.lang === "en" ? "en-GB" : "vi-VN", { month: "long", year: "numeric" }).format(new Date(...month.split("-").map(Number), 1)), s => new Date(s.updated * 1000).getFullYear() + "-" + new Date(s.updated * 1000).getMonth() === month]);
    const used = new Set();
    const pinned = C.list.filter(s => s.pinned && !s.chat_project);
    if (pinned.length) frag.append(h("div.tgroup", {}, PL.ui("Pinned conversations")));
    for (const s of pinned) { used.add(s.id); frag.append(threadNode(s)); }
    for (const project of C.chatProjects || []) {
      const items = C.list.filter(s => s.chat_project === project.id).sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));
      const body = h("div.chat-project-items");
      for (const s of items) { used.add(s.id); body.append(threadNode(s)); }
      const details = h("details.chat-project", { open: true }, h("summary", {}, project.name, h("span.muted", {}, " · " + items.length)),
        h("button.btn.sm.ghost", { type: "button", onclick: () => PL.safe(async () => {
          const session = await PL.post("/api/chat/sessions", { chat_project: project.id }); PL.go("#/chat/" + session.id); await C.loadList();
        }) }, PL.t("Cuộc trò chuyện mới")), body);
      frag.append(details);
    }
    for (const [label, fn] of groups) {
      const items = C.list.filter((s) => !used.has(s.id) && fn(s));
      if (!items.length) continue;
      frag.append(h("div.tgroup", {}, label));
      for (const s of items) {
        used.add(s.id);
        frag.append(threadNode(s));
      }
    }
    box.replaceChildren(frag);
  }
  function threadNode(s) {
    return h("div.thread" + (s.id === C.sid ? ".active" : ""), { role: "link", tabindex: "0", dataset: { session: s.id }, title: s.title + " · " + PL.date(s.updated),
          onclick: () => PL.go("#/chat/" + s.id), onkeydown: (e) => { if (e.key === "Enter") PL.go("#/chat/" + s.id); } },
        s.pinned ? h("span.thread-pin", { title: PL.ui("Pinned conversation"), html: PL.icon("pin") }) : null, h("span.t", {}, s.title || PL.t("Cuộc trò chuyện")),
        s.pending_approvals ? h("span.badge", { title: PL.t("Đề xuất chờ bạn duyệt") }, s.pending_approvals) : null,
        s.status === "running" ? h("span.spin") : null,
        h("button.icon.more", { type: "button", "aria-label": PL.t("Tuỳ chọn"), html: PL.icon("dots"), onclick: (e) => { e.stopPropagation(); threadMenu(e.currentTarget, s); } }));
  }
  function threadMenu(anchor, s) {
    PL.menu(anchor, [
      { label: PL.ui(s.pinned ? "Unpin conversation" : "Pin conversation"), run: async () => { await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { pinned: !s.pinned })); await C.loadList(); } },
      { label: PL.ui("Move to chat project…"), run: () => {
        const select = h("select.input", { "aria-label": PL.ui("Chat project") }, [["", PL.ui("Ungrouped")], ...(C.chatProjects || []).map(p => [p.id, p.name])].map(([id, name]) => h("option", { value: id, selected: id === (s.chat_project || "") || null }, name)));
        PL.modal({ title: PL.ui("Move to chat project…"), body: select, actions: [{ label: PL.ui("New chat project"), onClick: () => { C.createChatProject(s.id); } }, { label: PL.ui("Save"), onClick: async () => {
          const result = await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { chat_project: select.value })); if (!result) return false; await C.loadList();
        } }] });
      } },
      { label: PL.t("Đổi tên"), run: async () => { const t = await PL.prompt(PL.t("Đổi tên"), PL.t("Tên cuộc trò chuyện"), s.title); if (t) { await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { title: t })); C.loadList(); } } },
      { label: PL.t("Xuất cuộc trò chuyện…"), run: async () => { if (C.sid !== s.id) { PL.go("#/chat/" + s.id); return; } exportConversation(anchor); } },
      { label: PL.t("Lưu trữ"), run: async () => { await PL.safe(() => PL.put("/api/chat/sessions/" + s.id, { archived: true })); if (C.sid === s.id) PL.go("#/"); C.loadList(); } },
      { label: PL.t("Xoá"), danger: true, run: async () => {
        if (!(await PL.confirm(PL.t("Xoá \"{0}\"? (file được chuyển vào thùng rác của dự án)", s.title), PL.t("Xoá")))) return;
        await PL.safe(() => PL.del(`/api/chat/sessions/${s.id}?confirm=${s.id}`));
        if (C.sid === s.id) PL.go("#/");
        C.loadList();
      } },
    ]);
  }

  C.createChatProject = async function (sid) {
    const name = await PL.prompt(PL.ui("New chat project"), PL.ui("Project name"), "");
    if (!name || !name.trim()) return;
    const group = await PL.safe(() => PL.post("/api/chat/projects", { name: name.trim() }));
    if (!group) return;
    if (sid) await PL.safe(() => PL.put("/api/chat/sessions/" + sid, { chat_project: group.id }));
    await C.loadList();
  };

  /** A small popup menu next to an element: items [{label, run, danger, disabled, hint}]. Arrow keys + Escape. */
  PL.menu = function (anchor, items, opts) {
    PL.$$(".menu.pop").forEach((m) => m.remove());
    const m = h("div.menu.pop", { role: "menu" });
    for (const it of items) {
      if (it.header) { m.append(h("div.mh", {}, it.header)); continue; }
      m.append(h("button.mi", { type: "button", role: "menuitem", disabled: it.disabled || null,
        style: it.danger ? "color: var(--err)" : null, onclick: () => { close(); it.run && it.run(); } },
      h("span.grow", {}, it.label, it.hint ? h("div.d", {}, it.hint) : null), it.tag ? h("span.tag.chip", {}, it.tag) : null));
    }
    D.body.append(m);
    const r = anchor.getBoundingClientRect();
    const below = !(opts && opts.above);
    m.style.left = Math.max(8, Math.min(r.left, W.innerWidth - m.offsetWidth - 8)) + "px";
    if (below) m.style.top = Math.max(8, Math.min(r.bottom + 4, W.innerHeight - m.offsetHeight - 8)) + "px";
    else m.style.top = Math.max(8, r.top - m.offsetHeight - 4) + "px";
    const off = (e) => { if (!m.contains(e.target)) close(); };
    const key = (e) => {
      if (e.key !== "Escape" && /^(SELECT|INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
      const bs = PL.$$(".mi:not(:disabled)", m);
      const i = bs.indexOf(D.activeElement);
      if (e.key === "Escape") { close(); if (anchor.focus) anchor.focus(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); (bs[i + 1] || bs[0]).focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); (bs[i - 1] || bs[bs.length - 1]).focus(); }
    };
    function close() { m.remove(); D.removeEventListener("mousedown", off, true); D.removeEventListener("keydown", key, true); }
    m.close = close;
    W.setTimeout(() => { D.addEventListener("mousedown", off, true); D.addEventListener("keydown", key, true); }, 0);
    return m;
  };

  // ------------------------------------------------------------------ open / new
  C.open = async function (sid) {
    if (C.sse) { C.sse.close(); C.sse = null; }
    const same = sid && sid === C.sid && PL.$("#msgs");
    C.sid = sid || null;
    if (!same) {
      C.pinQuery = "";
      C.s = null;
      C.live = {};
      C.runCards = {};
      C.nodes = new Map();
      renderShell();
    }
    renderList();
    renderAtts();
    if (!sid) { renderEmpty(); return; }
    try {
      C.s = await PL.get("/api/chat/sessions/" + sid);
    } catch (e) {
      PL.toast(e.message, "err");
      PL.go("#/");
      return;
    }
    if (C.sid !== sid) return;  // the researcher opened another conversation meanwhile
    reconcilePins();
    if (PL.research) PL.research.onSession(C.s);
    renderAtts();
    PL.setTitle(C.s.title, "");
    paintTopTools();
    renderMessages(true);
    C.sse = PL.stream(`/api/chat/sessions/${sid}/stream`, onEvent, { after: C.s.last_seq || 0 });
  };

  function renderShell() {
    const v = PL.$("#view");
    v.replaceChildren(h("section#thread", { "aria-live": "polite" }, h("div#msgs")), composer());
    if (PL.research) PL.research.chips();
    PL.setTitle(C.sid ? "…" : "", "");
    paintTopTools();
    attachDrop(PL.$("#thread"));
    wireSelection(PL.$("#thread"));
  }
  /** Header buttons of an open conversation: notes and export. */
  function paintTopTools() {
    const box = PL.$("#top-tools");
    if (!box) return;
    box.replaceChildren();
    if (!C.sid) return;
    const n = ((C.s || {}).notes || []).filter((x) => x.status !== "resolved").length;
    box.append(h("button.btn.sm.ghost#pinned-btn", { type: "button", title: PL.t("Tin nhắn đã ghim"), "aria-label": PL.t("Tin nhắn đã ghim"), onclick: () => C.pinsPanel() },
      h("span", { html: PL.icon("pin") }), h("span.lbl", {}, PL.t("Tin nhắn đã ghim"))),
      h("button.btn.sm.ghost#notes-btn", { type: "button", title: PL.t("Ghi chú trên câu trả lời"), onclick: () => notesPanel() },
        h("span", { html: PL.icon("note") }), h("span.lbl", {}, PL.t("Ghi chú")), n ? h("span.count-pill", {}, String(n)) : null),
      h("button.btn.sm.ghost", { type: "button", title: PL.t("Xuất cuộc trò chuyện"), onclick: (e) => exportConversation(e.currentTarget) },
        h("span", { html: PL.icon("download") }), h("span.lbl", {}, PL.t("Xuất"))));
  }

  async function renderEmpty() {
    const msgs = PL.$("#msgs");
    msgs.replaceChildren(h("div.hello", {}, h("img.mark", { src: "/img/logo-128.png", alt: "" }), h("h1", {}, " ")));
    const [o, d] = await Promise.all([PL.get("/api/outline").catch(() => null), PL.get("/api/dashboard").catch(() => null)]);
    if (C.sid || !PL.$("#msgs")) return;
    const wrap = h("div");
    const name = (PL.state.project || {}).name || "";
    wrap.append(h("div.hello", {}, h("img.mark", { src: "/img/logo-128.png", alt: "" }),
      h("h1", {}, o && o.level ? PL.t("Hôm nay nghiên cứu gì?") : PL.t("Bắt đầu một nghiên cứu")),
      h("p", {}, name ? PL.t("Dự án {0}", name) + (o && o.level ? PL.t(" · đề cương cấp {0}/5 — {1}", o.level, PL.t(o.level_label)) : "") : "")));
    if (d) {
      const line = h("div.state-line");
      if (d.current) line.append(h("span.chip.info", {}, h("span.spin"), h("span.ellipsis", {}, d.current.title)));
      if (d.pending && d.pending.length) line.append(h("button.chip.warn", { type: "button", onclick: () => PL.go("#/dashboard") }, PL.t("{0} việc chờ bạn duyệt", d.pending.length)));
      if (line.childNodes.length) wrap.append(line);
    }
    if (o && o.level < 1 && !(o.attachments || []).length) wrap.append(PL.panels.outlineStarter(o));
    const st = h("div.starters");
    for (const [cmd, label] of STARTERS) st.append(h("button.starter", { type: "button", onclick: () => setInput(cmd + " ") }, h("b", {}, cmd), label));
    msgs.replaceChildren(wrap, st);
    const inp = PL.$("#input");
    if (inp) inp.focus();
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
  const notesOf = (mid) => (C.s.notes || []).filter((n) => n.message_id === mid);
  const noteNo = (n) => C.s.notes.indexOf(n) + 1;  // only called with an existing session note
  function keyOf(it) {
    if (it.k === "msg") {
      const m = it.m;
      return ["m:" + m.id, m.content.length + ":" + m.status + ":" + providerLabel(m.provider) + ":" + (m.model || "") + ":" + (m.run_id || "") + ":" + m.content.slice(-40)
        + ":" + !!m.pinned + ":" + JSON.stringify(notesOf(m.id).map((n) => [n.id, n.status, n.text, noteNo(n)]))];
    }
    if (it.k === "ap") return ["a:" + it.a.id, it.a.status + ":" + JSON.stringify(it.a.result || "").length];
    if (it.k === "mem") return ["e:" + it.it.id, it.it.status + ":" + it.it.conflicts];
    return ["f:" + it.a.id, it.a.status];
  }

  function renderMessages(scroll) {
    const box = PL.$("#msgs");
    if (!box || !C.s) return;
    const keep = nearBottom();
    if (!C.s.messages.length) { C.nodes = new Map(); renderEmpty(); return; }
    if (box.querySelector(".hello")) box.replaceChildren();
    const next = new Map(), want = [];
    let day = "";
    for (const it of timeline()) {
      if (it.k === "msg") {
        const date = PL.date(it.ts);
        if (date !== day) { want.push(h("div.chat-day", {}, h("time", { datetime: new Date(it.ts * 1000).toISOString().slice(0, 10) }, date))); day = date; }
      }
      const [key, sig] = keyOf(it);
      const old = C.nodes.get(key);
      let node = old && old.sig === sig ? old.node : null;
      if (!node) {
        node = it.k === "msg" ? messageNode(it.m) : it.k === "ap" ? approvalCard(it.a) : it.k === "mem" ? memoryCard(it.it) : artifactCard(it.a);
      }
      next.set(key, { sig, node });
      want.push(node);
    }
    const running = (C.s.turns || []).find((t) => ACTIVE.includes(t.status));
    if (running) want.push(liveNode(running));
    // move / insert only what changed (the DOM of unchanged messages is never touched)
    let cur = box.firstChild;
    for (const n of want) {
      if (n === cur) { cur = cur.nextSibling; continue; }
      box.insertBefore(n, cur);
    }
    while (cur) { const nx = cur.nextSibling; cur.remove(); cur = nx; }
    C.nodes = next;
    setBusy(!!running);
    if (scroll || keep) toBottom(true);
  }

  function messageNode(m) {
    if (m.role === "user") {
      return h("div.msg.user", { dataset: { id: m.id } }, h("div.bubble", {}, m.content), messageMeta(m), h("div.msg-actions", {}, pinAction(m)));
    }
    const prose = h("div.prose");
    paintProse(prose, m);
    const who = h("div.who", {}, h("img", { src: "/img/logo-64.png", alt: "" }),
      m.provider === "phdlab" ? "PhD Lab" : providerLabel(m.provider) + (m.model ? " · " + m.model : ""),
      m.status === "partial" ? h("span.chip.warn", {}, PL.t("chưa đầy đủ")) : null);
    const node = h("div.msg.ai", { dataset: { id: m.id } }, who, prose, messageMeta(m));
    if (m.run_id) node.append(runCard(m.run_id));
    node.append(h("div.msg-actions", {},
      act("copy", PL.t("Sao chép"), () => PL.copy(m.content)),
      m.provider !== "phdlab" ? act("retry", PL.t("Tạo lại câu trả lời"), () => retry()) : null,
      act("note", PL.t("Ghi chú (chọn một đoạn để ghi chú đúng chỗ)"), () => noteDialog({ message_id: m.id, quote: m.content.replace(/\s+/g, " ").slice(0, 160) })),
      act("download", PL.t("Xuất câu trả lời (PDF, Word, LaTeX…)"), (e) => PL.tools.exportMenu(e.currentTarget, () => ({ title: (C.s.title || "answer"), markdown: m.content, els: [prose] }))),
      act("brain", PL.t("Ghi nhớ vào dự án"), () => rememberDialog(m)),
      act("pin", PL.t("Ghim vào kết quả"), () => pinMessage(m)), pinAction(m)));
    return node;
  }
  function messageMeta(m) {
    return h("time.message-time", { datetime: new Date(m.ts * 1000).toISOString(), title: PL.date(m.ts, true) }, PL.date(m.ts, true));
  }
  const pinChanges = new Map(), pinBusy = new Set();
  function reconcilePins() {
    for (const m of C.s.messages) {
      const key = C.sid + ":" + m.id, change = pinChanges.get(key);
      if (!change) continue;
      if (change.settled && !!m.pinned === change.value) pinChanges.delete(key);
      else m.pinned = change.value;
    }
  }
  function pinAction(m) {
    return act("pin", m.pinned ? PL.t("Bỏ ghim tin nhắn") : PL.t("Ghim tin nhắn"), (e) => PL.safe(async () => {
      const sid = C.sid, pinned = !m.pinned, button = e.currentTarget;
      const key = sid + ":" + m.id;
      if (pinBusy.has(key)) return;
      pinBusy.add(key);
      pinChanges.set(key, { value: pinned, settled: false });
      button.disabled = true;
      try {
        await PL.put(`/api/chat/sessions/${sid}/messages/${m.id}/pin`, { pinned });
        if (C.sid !== sid) { pinChanges.delete(key); return; }
        pinChanges.get(key).settled = true;
        const current = C.s.messages.find((message) => message.id === m.id);
        if (current) current.pinned = pinned;
        renderMessages(false);
        if (!PL.$("#panel").hidden && PL.store.get("panel", {}).kind === "pins") C.pinsPanel();
      } catch (error) { pinChanges.delete(key); throw error; }
      finally { pinBusy.delete(key); button.disabled = false; }
    }));
  }
  C.pinsPanel = function () {
    const body = h("div.pinned-messages");
    const allPins = C.s.messages.filter(m => m.pinned), list = h("div"), count = h("p.muted", { role: "status" });
    const normalize = text => text.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/g, "d");
    const search = h("input.input.pin-search", { type: "search", placeholder: PL.ui("Search pinned messages…"), "aria-label": PL.ui("Search pinned messages"), value: C.pinQuery || "", oninput: () => { C.pinQuery = search.value; paint(); } });
    const paint = () => {
    const q = normalize(search.value.trim()), pins = allPins.filter(m => normalize(m.content).includes(q));
    list.replaceChildren(); count.textContent = pins.length + " / " + allPins.length;
    for (const m of pins) {
      const start = Math.max(0, normalize(m.content).indexOf(q) - 60);
      list.append(h("article.research-card", {}, h("p", {}, m.content.slice(start, start + 300)), messageMeta(m),
      h("button.btn.sm", { type: "button", onclick: () => {
        PL.panels.close();
        W.requestAnimationFrame(() => {
            const node = PL.$$("#msgs .msg").find(n => n.dataset.id === m.id);
            if (!node) { PL.toast(PL.ui("Message is no longer visible; reopen the conversation")); return; }
            node.scrollIntoView({ block: "center", behavior: W.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
            node.setAttribute("tabindex", "-1"); node.focus({ preventScroll: true });
            node.classList.add("pin-target"); W.setTimeout(() => node.classList.remove("pin-target"), 1800);
        });
      } }, PL.t("Đến tin nhắn")), pinAction(m)));
    }
    if (!pins.length) list.append(h("p.muted", {}, allPins.length ? PL.ui("No matching pinned messages") : PL.t("Chưa có tin nhắn được ghim")));
    };
    body.append(search, count, list); paint();
    PL.panels.open(PL.t("Tin nhắn đã ghim"), body, { kind: "pins" });
  };
  /** Markdown + figures + the researcher's notes (highlights) of one answer. */
  function paintProse(prose, m) {
    PL.rich(prose, m.content || (m.status === "cancelled" ? PL.t("_(đã dừng)_") : ""), {
      onPoint: (pt) => noteDialog({ message_id: m.id, point: pt, quote: pt.label }),
      marks: (chart) => notesOf(m.id).filter((n) => n.point && n.point.chart === chart).map((n) => ({ ...n.point, n: noteNo(n) })),
    });
    notesOf(m.id).forEach((n) => { if (!n.point) PL.tools.highlight(prose, n, noteNo(n)); });
  }
  const act = (icon, title, fn) => h("button.icon", { type: "button", title, "aria-label": title, html: PL.icon(icon), onclick: fn });

  function providerLabel(pid) {
    const p = ((C.models || {}).providers || []).find((x) => x.id === pid);
    if (p) return p.label;
    return { "app:auto": PL.ui("Research agent") }[pid] || pid || PL.ui("Research agent");
  }

  function liveNode(t) {
    const live = C.live[t.id] || (C.live[t.id] = { text: "", activity: "" });
    if (live.node && live.status === t.status) {  // same live answer: keep painting into it
      if (live.actEl) live.actEl.lastChild.textContent = activityText(t, live);
      return live.node;
    }
    const prose = h("div.prose");
    if (live.text) PL.rich(prose, live.text, { stream: true });
    else prose.append(h("span.typing", {}, h("i"), h("i"), h("i")));
    live.el = prose;
    const node = h("div.msg.ai.live", { dataset: { turn: t.id } }, h("div.who", {}, h("img", { src: "/img/logo-64.png", alt: "" }), providerLabel((C.s.settings || {}).provider || "app:auto")));
    live.actEl = h("div.activity", { hidden: !(live.activity || t.status !== "running") || null }, h("span.spin"), h("span", {}, activityText(t, live)));
    node.append(live.actEl, prose);
    if (t.status === "awaiting_launch") {
      node.append(h("div.row", {}, h("button.btn.accent.sm", { type: "button", onclick: () => PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/turns/${t.id}/launch`)) }, PL.t("Gửi cho mô hình"))));
    }
    live.node = node;
    live.status = t.status;
    return node;
  }
  function activityText(t, live) {
    if (t.status === "waiting_approval") return PL.t("Đang chờ bạn duyệt công cụ…");
    if (t.status === "awaiting_launch") return PL.t("Chế độ thủ công: xem ngữ cảnh rồi bấm Gửi");
    return live.activity || PL.t("Đang suy nghĩ…");
  }
  function setActivity(live, text) {
    live.activity = text;
    if (live.actEl) { live.actEl.hidden = false; live.actEl.lastChild.textContent = text; }
  }

  // ------------------------------------------------------------------ cards: proposals (Accept / Reject)
  function approvalCard(a) {
    const pending = a.status === "pending";
    if (a.kind === "tool" && !pending) {  // read-only tools the policy ran on its own: one quiet activity line
      return h("div.activity", {}, h("span", { html: PL.icon(a.status === "executed" ? "check" : "alert") }),
        (a.status === "executed" ? PL.t("Đã dùng công cụ {0}", a.name) : PL.t("Không dùng được công cụ {0}", a.name)) + (a.decided_by && a.decided_by.startsWith("auto") ? PL.t(" (tự động, chỉ đọc)") : ""));
    }
    const label = a.kind === "tool" ? PL.t("Dùng công cụ: {0}", a.name) : (ACTION[a.name] || a.name);
    return h("div.card" + (pending ? ".pending" : ".done"), { dataset: { ap: a.id } },
      h("div.card-h", {}, h("span.kind", {}, a.kind === "tool" ? PL.t("Công cụ") : PL.t("Đề xuất")), h("span.ttl", {}, label), verdictChip(a)),
      h("div.card-b", {}, proposalBody(a)),
      h("div.card-f", {},
        a.reason ? h("span.muted.small", {}, a.reason) : null, h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: () => decide(a, "reject") }, PL.t("Bỏ qua")),
        h("button.btn.accent.sm", { type: "button", onclick: () => decide(a, "approve") }, h("span", { html: PL.icon("check") }), PL.t("Chấp nhận"))));
  }
  function verdictChip(a) {
    const map = { pending: ["warn", PL.t("chờ duyệt")], executed: ["ok", PL.t("đã chấp nhận")], approved: ["ok", PL.t("đã chấp nhận")],
      rejected: ["", PL.t("đã bỏ qua")], failed: ["err", PL.t("lỗi")], denied: ["err", PL.t("bị chặn")], cancelled: ["", PL.t("đã huỷ")] };
    const [k, t] = map[a.status] || ["", a.status];
    return h("span.chip" + (k ? "." + k : ""), {}, t);
  }
  function proposalBody(a) {
    const g = a.args || {};
    const box = h("div");
    if (a.name === "start_run") box.append(h("div", {}, h("b", {}, "/" + g.skill), " ", h("span", {}, String(g.input || "").slice(0, 400))));
    else if (a.name === "write_section") {
      box.append(h("div.muted", {}, PL.t("Phần: {0}", g.section)));
      const p = h("div.preview-box.prose");
      p.textContent = String(g.text || "").slice(0, 4000);
      box.append(p);
    } else if (a.name === "update_outline") {
      const dl = h("dl.kv");
      for (const [k, v] of Object.entries(g)) if (v) dl.append(h("dt", {}, ({ keywords: PL.t("Từ khoá"), topic: PL.t("Chủ đề"), direction: PL.t("Định hướng"), method: PL.t("Phương pháp"), proposal: PL.t("Đề cương") })[k] || k), h("dd", {}, String(v).slice(0, k === "proposal" ? 600 : 1200)));
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
      else if (r.pin) box.append(h("div.muted", {}, PL.t("Đã ghim {0}", r.pin)));
    }
    return box;
  }
  async function decide(a, decision) {
    const card = PL.$(`.card[data-ap="${a.id}"]`);
    if (card) card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    const r = await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/approvals/${a.id}`, { decision }));
    if (r && r.status === "failed") PL.toast(PL.t("Không thực hiện được: {0}", (r.result || {}).error || ""), "err");
    else if (r) PL.toast(decision === "approve" ? PL.t("Đã chấp nhận") : PL.t("Đã bỏ qua"));
    await refresh();
    // a card whose status did not change is reused as is: let the researcher try again
    if (card && card.isConnected) card.querySelectorAll("button").forEach((b) => { b.disabled = false; });
  }

  function memoryCard(it) {
    const pending = it.status === "pending" || it.status === "duplicate";
    return h("div.card" + (pending ? ".pending" : ".done"), {},
      h("div.card-h", {}, h("span.kind", {}, PL.t("Đề xuất ghi nhớ")), h("span.ttl", {}, MEM_TYPE[it.type] || it.type),
        h("span.chip" + (pending ? ".warn" : it.status === "approved" ? ".ok" : ""), {}, { pending: PL.t("chờ duyệt"), duplicate: PL.t("có thể trùng"), approved: PL.t("đã lưu"), rejected: PL.t("đã bỏ qua") }[it.status] || it.status)),
      h("div.card-b", {}, it.text, it.conflicts ? h("div.err-line", {}, PL.t("Mâu thuẫn với {0} mục đã có — kiểm tra trước khi lưu", it.conflicts)) : null),
      h("div.card-f", {}, h("span.muted.small", {}, PL.t("Bộ nhớ ngữ cảnh chạy nền — chỉ lưu khi bạn chấp nhận")), h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${it.id}/reject`, {})); refresh(); } }, PL.t("Bỏ qua")),
        h("button.btn.accent.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${it.id}/approve`, {}), PL.t("Đã lưu vào bộ nhớ dự án")); refresh(); } }, PL.t("Chấp nhận"))));
  }

  function artifactCard(a) {
    const open = a.status === "collected";
    return h("div.card" + (open ? ".pending" : ".done"), {},
      h("div.card-h", {}, h("span.kind", {}, PL.t("File đề xuất")), h("span.ttl.mono", {}, a.path), h("span.chip", {}, { collected: PL.t("chờ duyệt"), applied: PL.t("đã áp dụng"), rejected: PL.t("đã bỏ qua") }[a.status] || a.status)),
      h("div.card-f", {}, h("button.btn.sm", { type: "button", onclick: () => PL.panels.artifact(C.sid, a) }, PL.t("Xem & so sánh")), h("span.spacer"),
        h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/artifacts/${a.id}/reject`, {})); refresh(); } }, PL.t("Bỏ qua")),
        h("button.btn.accent.sm", { type: "button", onclick: () => PL.panels.artifact(C.sid, a, true) }, PL.t("Áp dụng vào code"))));
  }

  // ------------------------------------------------------------------ run cards (live)
  function runCard(rid) {
    const card = h("div.card.run", { dataset: { run: rid } }, h("div.card-b", {}, h("span.spin")));
    (C.runCards[rid] = C.runCards[rid] || []).push(card);
    PL.get("/api/runs/" + rid).then((r) => fillRun(card, r)).catch(() => { card.replaceChildren(h("div.card-b.muted", {}, PL.t("Run {0} không còn", rid))); });
    return card;
  }
  C.refreshRun = async function (rid) {
    const cards = (C.runCards[rid] || []).filter((c) => c.isConnected);
    C.runCards[rid] = cards;
    if (!cards.length) return;
    let r = null, gone = false;
    try { r = await PL.get("/api/runs/" + rid); } catch (e) { gone = e.status === 404; }
    if (r) cards.forEach((c) => fillRun(c, r));
    else if (gone) cards.forEach((c) => c.replaceChildren(h("div.card-b.muted", {}, PL.t("Run {0} không còn", rid))));
  };
  function fillRun(card, r) {
    card.className = "card run" + (["APPROVAL_PENDING", "NEEDS_USER_ACTION"].includes(r.status) ? " pending" : "");
    const cur = r.steps.find((s) => s.id === r.current) || {};
    const steps = h("div.steps", {}, r.steps.map((s) => h("i." + (s.status || "pending"), { title: `${s.label} · ${s.provider} · ${s.status}` })));
    const body = h("div.card-b", {}, steps,
      h("div.row", {}, h("span.grow.ellipsis.muted", {}, ["RUNNING", "VERIFYING", "BLOCKED", "RECOVERING"].includes(r.status) ? `${cur.label || ""} · ${cur.provider || ""}` :
        ["COMPLETED", "CANCELLED"].includes(r.status) ? PL.t("{0} bước", r.steps.length) : r.reason || ""),
      r.synthetic ? h("span.chip.warn", {}, "SYNTHETIC") : null));
    if (r.status === "NEEDS_USER_ACTION" && (r.proposal || r.next_decision)) body.append(h("div.preview-box", {}, (r.proposal && r.proposal.text) || r.next_decision));
      if (cur.result && cur.result.engine_partial && !["COMPLETED", "CANCELLED"].includes(r.status)) body.append(h("pre.preview-box", {}, cur.result.engine_partial));
      if (r.proposal && r.proposal.job_id) body.append(h("button.btn.sm", { type: "button", onclick: () => PL.engineJob(r, r.proposal.job_id) }, PL.t("OpenScience · quyết định / khôi phục")));
    if (r.status === "COMPLETED" && r.outputs.length) {
      body.append(h("div.row.wrap", { style: "margin-top:6px" }, r.outputs.slice(0, 8).map((o) =>
        h("button.chip", { type: "button", onclick: () => PL.panels.file(o.path) }, h("span", { html: PL.icon("file") }), o.path.split("/").pop()))));
    }
    const sources = PL.panels.runSources(r);
    if (sources.length) {
      const list = h("details", { style: "margin-top:10px" }, h("summary", { style: "cursor:pointer" }, PL.t("{0} nguồn tìm được · xem & lưu vào thư viện", sources.length)));
      list.addEventListener("toggle", () => { if (list.open && !list._done) { list._done = true; list.append(h("div", {}, sources.map((s) => PL.panels.paperCard(s)))); } }, { once: false });
      body.append(list);
    }
    const f = h("div.card-f", {});
    f.append(h("button.btn.sm.ghost", { type: "button", onclick: () => PL.panels.run(r.id) }, PL.t("Chi tiết")), h("span.spacer"));
    if (r.status === "APPROVAL_PENDING") {
      f.append(h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, PL.t("Huỷ")),
        h("button.btn.accent.sm", { type: "button", onclick: () => runAct(r, "approve") }, h("span", { html: PL.icon("play") }), PL.t("Chấp nhận & chạy")));
    } else if (r.status === "NEEDS_USER_ACTION") {
      f.append(...[h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, PL.t("Huỷ run")),
        h("button.btn.sm", { type: "button", onclick: () => runAct(r, "resume", { accept: false }) }, PL.t("Thử lại")),
        r.proposal && r.proposal.patch && Object.keys(r.proposal.patch).length ?
          h("button.btn.accent.sm", { type: "button", onclick: () => runAct(r, "resume", { accept: true }) }, PL.t("Áp dụng đề xuất & tiếp tục")) : null].filter(Boolean));
    } else if (!["COMPLETED", "CANCELLED"].includes(r.status)) {
      f.append(h("button.btn.sm", { type: "button", onclick: () => runAct(r, "cancel") }, PL.t("Dừng")));
    }
    card.replaceChildren(h("div.card-h", {}, h("span.kind", {}, "Run"), h("span.ttl.ellipsis", { title: r.title }, r.title), PL.statusChip(r.status)), body, f);
  }
  async function runAct(r, what, body) {
    if (what === "cancel" && !(await PL.confirm(PL.t("Huỷ run \"{0}\"?", r.title), PL.t("Huỷ run")))) return;
    await PL.safe(() => PL.post(`/api/runs/${r.id}/${what}`, body || {}), { approve: PL.t("Đã duyệt — run bắt đầu"), cancel: PL.t("Đã huỷ"), resume: PL.t("Đang tiếp tục") }[what]);
    C.refreshRun(r.id);
  }
  PL.runAct = runAct;
    PL.engineJob = async function (run, jobId) {
      const detail = await PL.safe(() => PL.get(`/api/research-engines/jobs/${jobId}`));
      if (!detail) return;
      const box = h("div", {}, h("p.help", {}, `${detail.receipt?.state || detail.job.state} · ${detail.job.native_run_id || PL.ui("admission unresolved")}`));
      if (detail.observation_error) box.append(h("p.help", {}, PL.ui("Live runtime unavailable · ") + detail.observation_error));
      if (detail.job.native_run_id) box.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(async () => {
        const receipt = await PL.post(`/api/research-engines/jobs/${jobId}/cancel`, {});
        PL.toast(PL.t("Hủy tác vụ gốc: {0}", PL.ui(receipt.state)));
      }) }, PL.ui("Request native cancellation / reconcile status")));
      const resume = async () => { await PL.post(`/api/runs/${run.id}/resume`, { accept: false }); C.refreshRun(run.id); };
      if (!detail.job.native_run_id) box.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(async () => {
        await PL.post(`/api/research-engines/jobs/${jobId}/recover-admission`, {}); await resume();
      }) }, PL.ui("Recover admission with the same request ID")));
      for (const p of detail.pending || []) {
        const row = h("div.panelbox", {}, h("b", {}, p.permission || PL.ui("Question")), h("pre.preview-box", {}, JSON.stringify(p.kind === "permission" ? { patterns: p.patterns, metadata: p.metadata } : p.questions, null, 2)));
        const send = async (reply, answers) => {
          const receipt = await PL.post(`/api/research-engines/jobs/${jobId}/decisions`, { request_id: p.id, reply, ...(answers ? { answers } : {}) });
          if (receipt.state === "indeterminate" || receipt.status === "indeterminate") { PL.toast(PL.ui("Decision indeterminate; reconcile the runtime"), "err"); return; }
          await resume();
        };
        row.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => send("reject")) }, PL.ui("Reject")));
        if (p.kind === "permission") row.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => send("once")) }, PL.ui("Allow once")));
        else row.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(async () => {
          const answers = [];
          for (const question of p.questions || []) {
            const answer = await PL.prompt(PL.ui("OpenScience question"), question.question || question.header || PL.ui("Answer"), "");
            if (answer === null) return;
            answers.push([answer]);
          }
          await send("reject", answers);
        }) }, PL.ui("Answer")));
        box.append(row);
      }
      PL.modal({ title: PL.ui("OpenScience · live runtime decisions"), body: box, wide: true });
    };

  // ------------------------------------------------------------------ live events of the open conversation
  let rt = 0;
  const frame = W.requestAnimationFrame ? (f) => W.requestAnimationFrame(f) : (f) => W.setTimeout(f, 16);
  function paintLive(live) {
    if (!live.shown) {  // the first words appear at once; later deltas are batched
      live.shown = true;
      PL.rich(live.el, live.text, { stream: true });
      toBottom();
      return;
    }
    if (live.pending) return;  // one Markdown render per frame, however many deltas arrived
    live.pending = true;
    frame(() => {
      live.pending = false;
      if (!live.el || !live.el.isConnected) return;
      const keep = nearBottom();
      PL.rich(live.el, live.text, { stream: true });
      if (keep) toBottom(true);
    });
  }
  function onEvent(ev) {
    const d = ev.data || {};
    const live = ev.turn_id ? (C.live[ev.turn_id] = C.live[ev.turn_id] || { text: "", activity: "" }) : null;
    switch (ev.type) {
      case "turn.started":
        refresh();
        break;
      case "message.delta":
        live.text += d.text || "";
        if (live.el && live.el.isConnected) paintLive(live);
        else { W.clearTimeout(rt); rt = W.setTimeout(refresh, 60); }
        break;
      case "context.compiled":
        setActivity(live, PL.t("Đã dùng {0} nguồn ngữ cảnh ({1} token)", d.sources, d.tokens));
        break;
      case "status.updated":
        if (d.intent && live) setActivity(live, PL.t("Kỹ năng /{0}", d.intent));
        break;
      case "tool.started":
        if (live) setActivity(live, PL.t("Đang dùng công cụ {0}", d.tool || ""));
        break;
      case "run.updated":
        C.refreshRun(d.run_id);
        break;
      case "message.completed": case "turn.completed": case "turn.failed": case "turn.cancelled":
      case "action.approval_required": case "tool.approval_required": case "memory.candidate": case "memory.saved":
      case "action.completed": case "action.failed": case "artifact.discovered": case "artifact.updated": case "session.updated":
        if (ev.type === "turn.failed") PL.toast(PL.t("Lỗi: {0}", d.message || ""), "err");
        W.clearTimeout(rt);
        rt = W.setTimeout(refresh, 60);
        break;
      default:
    }
  }
  let inflight = null;
  async function refresh() {
    if (!C.sid) return;
    if (inflight) { inflight.again = true; return; }  // coalesce bursts of events into one request
    const sid = C.sid;
    inflight = { again: false };
    try {
      const s = await PL.get("/api/chat/sessions/" + sid);
      if (C.sid === sid) {
        C.s = s;
        reconcilePins();
        PL.setTitle(C.s.title, "");
        paintTopTools();
        renderMessages(false);
        C.loadListSoon();
      }
    } catch (e) { /* offline banner already shown */ }
    const again = inflight.again;
    inflight = null;
    if (again) refresh();
  }
  C.refresh = refresh;

  // ------------------------------------------------------------------ notes on answers (select a passage or click a chart point)
  let pop = null;
  function wireSelection(thread) {
    thread.addEventListener("mouseup", () => W.setTimeout(showNoteButton, 0));
    thread.addEventListener("keyup", (e) => { if (e.shiftKey) showNoteButton(); });
    thread.addEventListener("scroll", () => { if (pop) { pop.remove(); pop = null; } }, { passive: true });
    thread.addEventListener("click", (e) => {
      const mk = e.target.closest && e.target.closest("mark.note-hl, sup.note-ref");
      if (mk) notePopover(mk.dataset.note, mk);
    });
  }
  function showNoteButton() {
    if (pop) { pop.remove(); pop = null; }
    const s = PL.tools.selectionInAnswer();
    if (!s || !C.sid) return;
    pop = h("div.note-pop.sel-pop", {},
      h("button.btn.sm.accent", { type: "button", onmousedown: (e) => e.preventDefault(), onclick: () => { pop.remove(); pop = null; noteDialog({ message_id: s.messageId, quote: s.quote, prefix: s.prefix }); } },
        h("span", { html: PL.icon("note") }), PL.t("Ghi chú")),
      h("button.btn.sm", { type: "button", onmousedown: (e) => e.preventDefault(), onclick: () => { pop.remove(); pop = null; setInput(`> ${s.quote.replace(/\s+/g, " ").slice(0, 400)}\n\n`); } }, PL.t("Hỏi về đoạn này")));
    D.body.append(pop);
    pop.style.left = Math.max(8, Math.min(s.rect.left + s.rect.width / 2 - pop.offsetWidth / 2, W.innerWidth - pop.offsetWidth - 8)) + "px";
    pop.style.top = Math.max(8, s.rect.top - pop.offsetHeight - 8) + "px";
  }
  function noteDialog(base, existing) {
    const txt = h("textarea.input", { rows: "4", placeholder: PL.t("Ghi chú của bạn: cần kiểm chứng, sai số liệu, ý tưởng mở rộng…") }, existing ? existing.text : "");
    const quote = base.point ? PL.t("Điểm {0}: {1} = {2}", base.point.series, base.point.x, base.point.y) : base.quote;
    PL.modal({ title: existing ? PL.t("Sửa ghi chú") : PL.t("Ghi chú vào điểm này"), body: h("div", {},
      h("blockquote.note-quote", {}, String(quote || "").slice(0, 600)), h("label.field", {}, h("span", {}, PL.t("Ghi chú")), txt)),
    actions: [{ label: PL.t("Huỷ") }, { label: PL.t("Lưu ghi chú"), kind: "accent", onClick: async () => {
      const r = existing ? await PL.safe(() => PL.put(`/api/chat/sessions/${C.sid}/notes/${existing.id}`, { text: txt.value }), PL.t("Đã lưu ghi chú"))
        : await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/notes`, { ...base, text: txt.value }), PL.t("Đã lưu ghi chú"));
      if (!r) return false;
      const sel = W.getSelection && W.getSelection();
      if (sel && sel.removeAllRanges) sel.removeAllRanges();
      await refresh();
      if (PL.$("#panel") && !PL.$("#panel").hidden && PL.store.get("panel", {}) && (PL.store.get("panel", {}) || {}).kind === "notes") notesPanel();
      return true;
    } }] });
  }
  function notePopover(nid, anchor) {
    const n = ((C.s || {}).notes || []).find((x) => x.id === nid);
    if (!n) return;
    PL.menu(anchor, [{ header: n.text ? n.text.slice(0, 200) : PL.t("(chưa có nội dung)") },
      { label: PL.t("Sửa ghi chú"), run: () => noteDialog({ message_id: n.message_id, quote: n.quote, point: n.point }, n) },
      { label: n.status === "resolved" ? PL.t("Mở lại") : PL.t("Đánh dấu đã xử lý"), run: () => setNote(n, { status: n.status === "resolved" ? "open" : "resolved" }) },
      { label: PL.t("Hỏi AI về ghi chú này"), run: () => askNotes([n]) },
      { label: PL.t("Xoá ghi chú"), danger: true, run: () => delNote(n) }]);
  }
  async function setNote(n, patch) { await PL.safe(() => PL.put(`/api/chat/sessions/${C.sid}/notes/${n.id}`, patch)); await refresh(); }
  async function delNote(n) { await PL.safe(() => PL.del(`/api/chat/sessions/${C.sid}/notes/${n.id}`), PL.t("Đã xoá ghi chú")); await refresh(); }
  function askNotes(notes) {
    const lines = notes.map((n, i) => `${i + 1}. > ${(n.point ? PL.t("Điểm {0}: {1} = {2}", n.point.series, n.point.x, n.point.y) : n.quote).replace(/\s+/g, " ").slice(0, 300)}\n   ${PL.t("Ghi chú")}: ${n.text || "—"}`);
    setInput(PL.t("Xem lại các điểm mình đã ghi chú trên câu trả lời và sửa / giải thích từng điểm:") + "\n\n" + lines.join("\n") + "\n");
  }
  function notesPanel() {
    const notes = (C.s || {}).notes || [];
    const body = PL.panels.open(PL.t("Ghi chú ({0})", notes.length), null, { kind: "notes" });
    if (!notes.length) { body.append(h("p.muted", {}, PL.t("Chưa có ghi chú. Bôi đen một đoạn trong câu trả lời rồi bấm Ghi chú, hoặc bấm vào một điểm trên biểu đồ."))); return; }
    const open = notes.filter((n) => n.status !== "resolved");
    body.append(h("div.row", { style: "margin-bottom:10px" }, h("span.grow.muted", {}, PL.t("{0} chưa xử lý", open.length)),
      open.length ? h("button.btn.sm.accent", { type: "button", onclick: () => askNotes(open) }, h("span", { html: PL.icon("spark") }), PL.t("Gửi ghi chú cho AI")) : null));
    notes.forEach((n, i) => body.append(h("div.note-item" + (n.status === "resolved" ? ".resolved" : ""), {},
      h("div.row", {}, h("span.note-num", {}, String(i + 1)), h("span.grow.muted.small", {}, PL.ago(n.created)),
        h("button.icon", { type: "button", title: PL.t("Đến đoạn này"), "aria-label": PL.t("Đến đoạn này"), html: PL.icon("ext"), onclick: () => jumpTo(n) }),
        h("button.icon", { type: "button", title: PL.t("Tuỳ chọn"), "aria-label": PL.t("Tuỳ chọn"), html: PL.icon("dots"), onclick: (e) => notePopover(n.id, e.currentTarget) })),
      h("blockquote.note-quote", {}, n.point ? PL.t("Điểm {0}: {1} = {2}", n.point.series, n.point.x, n.point.y) : String(n.quote).slice(0, 300)),
      n.text ? h("div.note-text", {}, n.text) : h("div.muted.small", {}, PL.t("(chưa có nội dung)")))));
  }
  function jumpTo(n) {
    const mk = PL.$(`mark[data-note="${n.id}"]`) || PL.$(`.msg[data-id="${n.message_id}"]`);
    if (!mk) return;
    mk.scrollIntoView({ block: "center" });
    mk.classList.add("flash");
    W.setTimeout(() => mk.classList.remove("flash"), 1400);
  }
  C.notesPanel = notesPanel;

  // ------------------------------------------------------------------ export of the whole conversation
  function exportConversation(anchor) {
    if (!C.s) return;
    PL.tools.exportMenu(anchor, () => {
      const md = C.s.messages.map((m) => "### " + (m.role === "user" ? PL.t("Bạn") : "PhD Lab") + "\n\n" + m.content).join("\n\n---\n\n");
      const els = [];  // the rendered nodes themselves: tools.js reads the chart data of live figures
      for (const m of C.s.messages) {
        const n = PL.$(`.msg[data-id="${m.id}"] ${m.role === "user" ? ".bubble" : ".prose"}`);
        if (!n) continue;
        els.push(h("h3", {}, m.role === "user" ? PL.t("Bạn") : "PhD Lab"), m.role === "user" ? h("div.msg-user", {}, m.content) : n);
      }
      return { title: C.s.title, markdown: md, els };
    });
  }

  // ------------------------------------------------------------------ composer
  function composer() {
    const ta = h("textarea#input", { rows: "1", placeholder: PL.t("Hỏi, giao việc, hoặc gõ / để chọn kỹ năng…"), "aria-label": PL.t("Tin nhắn") });
    const file = h("input", { type: "file", multiple: true, hidden: true, onchange: (e) => { addFiles(e.target.files); e.target.value = ""; } });
    const send = h("button.send#send", { type: "button", "aria-label": PL.t("Gửi"), html: PL.icon("send"), onclick: () => (C.busy ? stop() : submit()) });
    const model = h("button.model-btn#model", { type: "button", title: PL.t("Mô hình cho cuộc trò chuyện này"), onclick: (e) => modelMenu(e.currentTarget) }, "…");
    const box = h("div.composer", {},
      h("div.atts#atts"), h("div.research-chips#research-chips"), ta,
      h("div.bar", {},
        h("button.icon", { type: "button", title: PL.t("Đính kèm file (PDF, Word, Markdown, dữ liệu, ảnh…)"), "aria-label": PL.t("Đính kèm file"), html: PL.icon("clip"), onclick: () => file.click() }), file,
        h("button.icon", { type: "button", title: PL.t("Kỹ năng (/)"), "aria-label": PL.t("Kỹ năng"), html: PL.icon("spark"), onclick: () => { setInput("/"); slash(); } }),
        h("button.icon", { type: "button", title: PL.t("Công cụ: biểu đồ, sơ đồ, xuất file"), "aria-label": PL.t("Công cụ"), html: PL.icon("chart"), onclick: (e) => toolsMenu(e.currentTarget) }),
        h("span.grow"), model, send));
    let sized = false;
    ta.addEventListener("input", () => {
      slash();
      updateSend();
      if (!sized) { sized = true; frame(() => { sized = false; autosize(ta); }); }  // one layout read per frame while typing
    });
    ta.addEventListener("keydown", onKey);
    ta.addEventListener("paste", (e) => { const fs = e.clipboardData && e.clipboardData.files; if (fs && fs.length) { e.preventDefault(); addFiles(fs); } });
    W.setTimeout(() => { renderAtts(); paintModel(); updateSend(); }, 0);
    return h("footer#composer-wrap", {}, box, h("div.composer-hint", {}, PL.t("Enter để gửi · Shift+Enter xuống dòng · mọi việc có thay đổi dự án đều chờ bạn Chấp nhận")));
  }
  function toolsMenu(anchor) {
    const ask = (t) => () => setInput(t);
    PL.menu(anchor, [{ header: PL.t("Yêu cầu AI dùng công cụ hiển thị") },
      { label: PL.t("Vẽ đồ thị từ dữ liệu / kết quả"), hint: PL.t("biểu đồ tương tác, bấm điểm để ghi chú"), run: ask(PL.t("Vẽ đồ thị (```chart) so sánh các kết quả đã đo trong dự án: ")) },
      { label: PL.t("Vẽ sơ đồ kiến trúc / pipeline"), hint: "mermaid", run: ask(PL.t("Vẽ sơ đồ mermaid cho pipeline / kiến trúc: ")) },
      { label: PL.t("Vẽ hình minh hoạ (SVG)"), hint: "svg", run: ask(PL.t("Vẽ hình minh hoạ dạng SVG cho: ")) },
      { label: PL.t("Viết bảng LaTeX"), run: ask(PL.t("Viết bảng LaTeX (booktabs) cho các kết quả: ")) },
      { header: PL.t("Xuất cuộc trò chuyện") },
      { label: "PDF · Word · LaTeX · Markdown…", disabled: !C.sid, run: () => exportConversation(anchor) }]);
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
    const b = PL.$("#send");
    if (C.busy === v && b && b.classList.contains("stop") === v) return;
    C.busy = v;
    if (!b) return;
    b.classList.toggle("stop", v);
    b.innerHTML = PL.icon(v ? "stop" : "send");
    b.setAttribute("aria-label", v ? PL.t("Dừng") : PL.t("Gửi"));
    updateSend();
  }

  // "/" menu
  let sel = 0;
  const skillTitle = (s) => s.mode === "ui" ? PL.ui(s.title) : (PL.lang === "en" && s.title_en) || s.title;
  const skillDesc = (s) => s.mode === "ui" ? PL.ui(s.description) : (PL.lang === "en" && s.description_en) || s.description;
  function slash() {
    const ta = PL.$("#input");
    const old = PL.$(".menu.slash");
    const m = /^\/([\w-]*)$/.exec(ta.value);
    if (!m) { if (old) old.remove(); return; }
    const q = m[1].toLowerCase();
    const list = C.skills.filter((s) => s.name.startsWith(q) || s.aliases.some((a) => a.startsWith(q)) || (q.length > 1 && skillTitle(s).toLowerCase().includes(q)));
    if (old) old.remove();
    if (!list.length) return;
    sel = Math.min(sel, list.length - 1);
    const menu = h("div.menu.slash", { role: "listbox" });
    const cats = { research: PL.t("Nghiên cứu"), experiment: PL.t("Thí nghiệm"), writing: PL.t("Viết bài"), system: PL.t("Hệ thống") };
    let cur = "";
    list.forEach((s, i) => {
      if (s.category !== cur) { cur = s.category; menu.append(h("div.mh", {}, cats[cur] || PL.ui(cur))); }
      menu.append(h("button.mi" + (i === sel ? ".sel" : ""), { type: "button", role: "option", onmousedown: (e) => { e.preventDefault(); pick(s); } },
        h("span.c", {}, "/" + s.name), h("span.grow", {}, skillTitle(s), h("div.d", {}, skillDesc(s))),
        s.origin === "plugin" ? h("span.tag.chip.info", { title: s.plugin }, "plugin") : null,
        s.mode === "run" ? h("span.tag.chip" + (s.risk >= 2 ? ".warn" : ".info"), {}, s.risk >= 2 ? PL.t("cần duyệt") : PL.t("chạy nền")) : null));
    });
    menu._list = list;
    PL.$(".composer").append(menu);
    const on = menu.querySelector(".mi.sel");
    if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" });
  }
  function pick(s) {
    const m = PL.$(".menu.slash"); if (m) m.remove();
    if (s.mode === "ui" && PL.research) { setInput(""); PL.safe(() => PL.research.dispatch(s)); }
    else setInput("/" + s.name + " ");
  }
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
    box.replaceChildren(...C.atts.map((a) => h("span.att", { title: a.name }, a.pending ? h("span.spin") : h("span", { html: PL.icon("file") }), h("span.n", {}, a.name),
      /\.pdf$/i.test(a.name) && !a.pending ? h("button", { type: "button", title: PL.t("Lưu bản PDF này vào Thư viện dự án"), onclick: () => PL.safe(() => PL.upload("/api/library/upload", a.file, "files"), PL.t("Đã thêm vào Thư viện")) }, PL.t("＋TV")) : null,
      h("button", { type: "button", "aria-label": PL.t("Bỏ {0}", a.name), onclick: () => { C.atts.splice(C.atts.indexOf(a), 1); renderAtts(); } }, "✕"))));
    updateSend();
  }
  function attachDrop(el) {
    el.addEventListener("dragover", (e) => { e.preventDefault(); });
    el.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });
  }

  // model + reasoning picker (one popover: filter, models, "Cấp độ tư duy")
  const LEVEL = { auto: PL.t("Tự động"), off: PL.t("Tắt"), low: PL.t("Thấp"), medium: PL.t("Vừa"), high: PL.t("Cao") };
  C.loadModels = async function () {
    C.models = await PL.get("/api/models").catch(() => null);
    paintModel();
    if (C.s) renderMessages(false);  // provider labels of the answers
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
    const assistant = C.models && C.models.agent_catalog && C.models.agent_catalog.assistant;
    b.replaceChildren(h("span.ellipsis", {}, pid === "app:auto" ? (assistant ? PL.ui("Chat assistant") + " · " + (assistant.selected || assistant.label) : PL.t("Tự động")) : providerLabel(pid)));
    if (lvl !== "auto") b.append(h("span.lvl", { title: PL.t("Cấp độ tư duy") }, LEVEL[lvl]));
    b.append(h("span", { html: PL.icon("chev") }));
  }
  function modelMenu(anchor) {
    const agent = "assistant", catalog = (C.models && C.models.agent_catalog || {}).assistant;
    if (!catalog) { genericModelMenu(anchor); return; }
    const menu = PL.menu(anchor, [{ header: PL.ui("Chat assistant") + " · " + catalog.label }], { above: true });
    const activate = async () => {
      if (C.sid) {
        const saved = await PL.safe(() => PL.put("/api/chat/sessions/" + C.sid, { settings: { provider: "app:auto" }, settings_reset: ["model"] }));
        if (!saved) return;
        await refresh();
      } else C.pending = Object.assign({}, C.pending, { provider: "app:auto", model: "" });
      paintModel(); menu.close();
    };
    const select = h("select.input", { "aria-label": PL.ui("Assistant model"), onchange: (e) => PL.safe(async () => {
      const result = await PL.post("/api/config", { agent_models: { [agent]: e.target.value } });
      if (result) { await C.loadModels(); await activate(); }
    }) }, [["", PL.ui("Provider default")], ...catalog.models.map((m) => [m, m])].map(([v, label]) => h("option", { value: v, selected: v === catalog.selected || null }, label)));
    select.disabled = catalog.mode === "auto";
    menu.append(select, h("p.help", {}, catalog.mode === "auto" ? PL.ui("Assign the chat assistant’s provider in Settings to choose its models.") : PL.ui("This list belongs to the assigned agent provider. Changing it updates this agent across chats.")),
      h("button.mi", { type: "button", onclick: () => PL.safe(activate) }, PL.ui("Use assigned agent")),
      h("button.mi", { type: "button", onclick: () => { menu.close(); PL.settings.open("models"); } }, PL.t("Cài đặt mô hình & API key…")));
    select.focus();
  }
  function genericModelMenu(anchor) {
    PL.$$(".menu.pop").forEach((m) => m.remove());
    const pop = h("div.menu.pop.picker", { role: "dialog", "aria-label": PL.t("Mô hình") });
    const filter = h("input.filter", { type: "search", placeholder: PL.t("Lọc mô hình…"), "aria-label": PL.t("Lọc mô hình") });
    const list = h("div.plist");
    const groups = { router: "", local: PL.t("Trên máy này"), api: PL.ui("Cloud API"), cli: PL.t("CLI (gói đăng ký của bạn)") };
    const paintList = () => {
      const q = filter.value.trim().toLowerCase();
      list.replaceChildren();
      const cur = currentProvider();
      for (const [t, label] of Object.entries(groups)) {
        const g = ((C.models || {}).providers || []).filter((p) => p.transport === t && (!q || (p.label + " " + p.id).toLowerCase().includes(q)))
          .sort((x, y) => Number(y.available) - Number(x.available));
        if (!g.length) continue;
        if (label) list.append(h("div.mh", {}, label));
        for (const p of g) {
          list.append(h("button.mi" + (p.id === cur ? ".sel" : ""), { type: "button", disabled: !p.available || null, title: p.available ? p.id : p.detail,
            onclick: async () => { pop.remove(); await setSetting("model", ""); await setSetting("provider", p.id === "app:auto" ? "" : p.id); } },
          h("span", { html: PL.icon(t === "cli" ? "code" : t === "api" ? "spark" : "gauge") }),
          h("span.grow", {}, p.id === "app:auto" ? PL.t("Tự động (Research / Reviewer agent)") : p.label,
            !p.available ? h("div.d", {}, p.state === "NO_KEY" ? PL.t("chưa có API key") : p.detail) : null),
          p.id === cur ? h("span", { html: PL.icon("check") }) : null));
          if (p.available && p.id === cur && p.id !== "app:auto") {
            const options = Array.from(new Set([...(p.models || []), setting("model")].filter(Boolean)));
            list.append(h("select.input", { "aria-label": "Model", onchange: (e) => { pop.remove(); setSetting("model", e.target.value); } },
              [["", PL.ui("Provider default")], ...options.map((m) => [m, m])].map(([value, label]) => h("option", { value, selected: value === setting("model") || null }, label))));
          }
        }
      }
      if (!C.models) list.append(h("div.mh", {}, h("span.spin"), PL.t(" Đang tải danh sách mô hình…")));
      else if (!list.childNodes.length) list.append(h("div.mh", {}, PL.t("Không có mô hình phù hợp")));
    };
    filter.addEventListener("input", paintList);
    const info = providerInfo(currentProvider());
    const levels = (info && info.reasoning) || [];
    const lvl = setting("reasoning") || "auto";
    const rrow = h("button.mi.reason", { type: "button", "aria-haspopup": "menu", onclick: (e) => {
      e.stopPropagation();
      PL.$$(".menu.sub").forEach((m) => m.remove());
      const sub = h("div.menu.pop.sub", { role: "menu" }, h("div.mh", {}, PL.t("Cấp độ tư duy")),
        ["auto", "off", "low", "medium", "high"].map((k) => h("button.mi" + (k === lvl ? ".sel" : ""), { type: "button",
          disabled: k !== "auto" && !levels.includes(k) || null,
          onclick: () => { pop.remove(); sub.remove(); setSetting("reasoning", k === "auto" ? "" : k); } },
        h("span.grow", {}, LEVEL[k], k === "auto" ? h("div.d", {}, PL.t("mặc định của mô hình")) : null), k === lvl ? h("span", { html: PL.icon("check") }) : null)));
      D.body.append(sub);
      const pr = pop.getBoundingClientRect(), rr = rrow.getBoundingClientRect();
      const left = pr.left - sub.offsetWidth - 6;
      sub.style.left = (left >= 8 ? left : Math.min(pr.right + 6, W.innerWidth - sub.offsetWidth - 8)) + "px";
      sub.style.top = Math.max(8, Math.min(rr.bottom - sub.offsetHeight, W.innerHeight - sub.offsetHeight - 8)) + "px";
    } }, h("span.grow", {}, PL.t("Cấp độ tư duy"), !levels.length ? h("div.d", {}, PL.t("mô hình này không có điều khiển tư duy")) : null),
    h("span.muted", {}, LEVEL[lvl]), h("span", { html: PL.icon("chev"), style: "transform:rotate(-90deg)" }));
    pop.append(h("div.mh", {}, PL.t("Mô hình")), filter, list, h("div.sep"), rrow,
      h("button.mi", { type: "button", onclick: () => { pop.remove(); PL.settings.open("models"); } }, h("span.grow.muted", {}, PL.t("Cài đặt mô hình & API key…"))));
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
    if (PL.research && PL.research.command(text)) { ta.value = ""; return; }
    if (C.atts.some((a) => a.pending)) { PL.toast(PL.t("Đợi file tải lên xong")); return; }
    if (!text && !C.atts.length) return;
    const atts = C.atts.slice();
    const body = { text: text || PL.t("Hãy đọc các file đính kèm và tóm tắt những điểm quan trọng cho dự án."), overrides: {} };
    if (atts.length) body.overrides.sources = atts.map((a) => "att:" + a.id);
    if (PL.research && PL.research.tid) body.overrides.sources = (body.overrides.sources || []).concat(PL.research.sources());
    if (atts.length) body.text = body.text + "\n\n" + atts.map((a) => `📎 ${a.name}`).join("\n");
    try {
      if (!C.sid) {
        const pend = Object.fromEntries(Object.entries(C.pending || {}).filter(([, v]) => v));
        const s = await PL.post("/api/chat/sessions", { ...(Object.keys(pend).length ? { settings: pend } : {}), ...(PL.research && PL.research.tid ? { topic_id: PL.research.tid } : {}) });
        C.pending = null;
        ta.value = "";
        C.atts = [];
        W.history.replaceState(null, "", "#/chat/" + s.id);
        await C.open(s.id);
      }
      const inp = PL.$("#input");
      inp.value = "";
      C.atts = [];
      renderAtts();
      autosize(inp);
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
    const t = ((C.s || {}).turns || []).find((x) => ACTIVE.includes(x.status));
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
    const type = h("select.input", {}, Object.entries({ decision: PL.t("Quyết định"), finding: PL.t("Phát hiện"), hypothesis: PL.t("Giả thuyết"), open_question: PL.t("Câu hỏi mở"), rejected_approach: PL.t("Hướng bị loại"), knowledge: PL.t("Kiến thức") }).map(([k, v]) => h("option", { value: k }, v)));
    const txt = h("textarea.input", { rows: "5" }, m.content.replace(/```[\s\S]*?```/g, "").slice(0, 1200));
    PL.modal({ title: PL.t("Ghi nhớ vào dự án"), body: h("div", {}, h("label.field", {}, h("span", {}, PL.t("Loại")), type), h("label.field", {}, h("span", {}, PL.t("Nội dung (bạn có thể sửa)")), txt)),
      actions: [{ label: PL.t("Huỷ") }, { label: PL.t("Lưu"), kind: "accent", onClick: async () => { await PL.safe(() => PL.post(`/api/chat/sessions/${C.sid}/memory`, { message_id: m.id, type: type.value, content: txt.value, save: true }), PL.t("Đã lưu vào bộ nhớ dự án")); refresh(); } }] });
  }
  async function pinMessage(m) {
    const title = await PL.prompt(PL.t("Ghim vào kết quả"), PL.t("Tiêu đề"), (C.s.title || "").slice(0, 80));
    if (!title) return;
    await PL.safe(() => PL.post("/api/pins", { kind: "note", title, body: m.content.slice(0, 20000), provenance: { session_id: C.sid, message_id: m.id } }), PL.t("Đã ghim"));
  }

  C.loadSkills = async function () {
    const r = await PL.get("/api/skills").catch(() => ({ skills: [] }));
    if (PL.research) PL.research.actions = r.actions || [];
    C.skills = (r.actions || []).concat(r.skills);
  };
})(window);
