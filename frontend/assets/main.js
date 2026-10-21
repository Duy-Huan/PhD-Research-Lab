/* PhD Research Lab — boot: project switcher, navigation, routes, the UI ⇄ CLI live bus. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document, h = PL.h;
  PL.state = { project: null, projects: [] };

  PL.setTitle = function (title, crumb) {
    const t = PL.$("#title"), c = PL.$("#crumb");
    if (t) t.textContent = title || "";
    if (c) c.textContent = crumb || "";
    D.title = (title ? title + " · " : "") + "PhD Research Lab";
  };
  PL.activeNav = (name) => PL.$$(".nav").forEach((b) => b.classList.toggle("active", b.dataset.go === name));
  PL.paintPending = function (n) {
    const c = PL.$("#pending-count");
    if (c) c.textContent = n ? String(n) : "";
  };

  // ------------------------------------------------------------------ projects
  async function loadProject() {
    const [cfg, ps] = await Promise.all([PL.get("/api/config"), PL.get("/api/projects")]);
    PL.state.project = cfg.project;
    PL.state.projects = ps.projects;
    PL.state.version = cfg.version;
    PL.$("#proj-name").textContent = cfg.project.name;
    const o = await PL.get("/api/outline").catch(() => null);
    PL.$("#proj-sub").textContent = o && o.level ? `Đề cương cấp ${o.level}/5 · ${o.level_label}` : "Chưa có đề cương";
  }
  function projectMenu(anchor) {
    const items = [{ header: "Dự án nghiên cứu" }];
    for (const p of PL.state.projects) {
      items.push({ label: p.name, hint: p.data_dir, tag: p.data_dir === PL.state.project.data_dir ? "đang mở" : null,
        run: () => switchProject(p.data_dir) });
    }
    items.push({ label: "＋ Dự án mới…", run: newProject }, { label: "Mở dự án có sẵn (thư mục)…", run: openExisting },
      { label: "Đề cương nghiên cứu", run: () => PL.panels.outline() }, { label: "Mở thư mục dự án", run: () => PL.safe(() => PL.post("/api/projects/reveal")) });
    PL.menu(anchor, items);
  }
  async function switchProject(dir) {
    if (dir === PL.state.project.data_dir) return;
    if (await PL.safe(() => PL.post("/api/projects/activate", { data_dir: dir }))) await afterSwitch();
  }
  async function afterSwitch() {
    PL.panels.close();
    await loadProject();
    await PL.chat.loadList();
    PL.go("#/");
  }
  function newProject() {
    const name = h("input.input", { placeholder: "vd: Lightweight ViT cho thiết bị biên" });
    const dir = h("input.input", { placeholder: "để trống = projects/<tên>" });
    PL.modal({ title: "Dự án nghiên cứu mới", body: h("div", {},
      h("label.field", {}, h("span", {}, "Tên dự án"), name),
      h("label.field", {}, h("span", {}, "Thư mục dữ liệu (tuỳ chọn)"), dir),
      h("p.muted", { style: "font-size:13px" }, "Sau khi tạo, bạn đưa vào đề cương ở cấp bạn đang có (từ khoá → đề cương đầy đủ) hoặc đính kèm file đề cương.")),
    actions: [{ label: "Huỷ" }, { label: "Tạo dự án", kind: "accent", onClick: async () => {
      if (!name.value.trim()) { name.focus(); return false; }
      const r = await PL.safe(() => PL.post("/api/projects", { name: name.value.trim(), data_dir: dir.value.trim() || undefined }), "Đã tạo dự án");
      if (!r) return false;
      await afterSwitch();
      return true;
    } }] });
  }
  async function openExisting() {
    const p = await PL.prompt("Mở dự án có sẵn", "Đường dẫn thư mục dự án", "");
    if (p && await PL.safe(() => PL.post("/api/projects/open", { data_dir: p }))) await afterSwitch();
  }

  // ------------------------------------------------------------------ routes
  PL.route("", () => { PL.activeNav(""); PL.chat.open(null); });
  PL.route("chat", (sid) => { PL.activeNav(""); PL.chat.open(sid || null); });

  // ------------------------------------------------------------------ pending count + live bus
  let pt = 0;
  async function refreshPending() {
    W.clearTimeout(pt);
    pt = W.setTimeout(async () => {
      const d = await PL.get("/api/dashboard").catch(() => null);
      if (d) PL.paintPending(d.pending.length);
    }, 600);
  }
  function wireBus() {
    let lt = 0;
    const list = () => { W.clearTimeout(lt); lt = W.setTimeout(() => PL.chat.loadList(), 400); };
    PL.on("aiws.", (e) => {
      list();
      if (e.session_id && e.session_id === PL.chat.sid && !PL.chat.sse) PL.chat.refresh();
      if (/approval|completed|run/.test(e.type)) refreshPending();
    });
    PL.on("run.", (e) => { if (e.run_id) PL.chat.refreshRun(e.run_id); refreshPending(); list(); });
    PL.on("project.", () => afterSwitch());
    PL.on("outline.", () => loadProject());
    PL.on("config.", () => PL.chat.loadModels());
    PL.startBus();
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    PL.paintIcons(D);
    const app = PL.$("#app");
    const narrow = () => W.matchMedia && W.matchMedia("(max-width: 820px)").matches;
    if (PL.store.get("side", true) === false && !narrow()) app.classList.add("side-collapsed");
    PL.$("#side-toggle").onclick = () => {
      if (narrow()) { app.classList.remove("side-open"); return; }
      app.classList.toggle("side-collapsed");
      PL.store.set("side", !app.classList.contains("side-collapsed"));
    };
    PL.$("#side-open").onclick = () => {
      if (narrow()) app.classList.toggle("side-open");
      else { app.classList.remove("side-collapsed"); PL.store.set("side", true); }
    };
    PL.$("#side-open").hidden = false;
    PL.$("#new-chat").onclick = () => { app.classList.remove("side-open"); PL.go("#/"); };
    PL.$("#proj-btn").onclick = (e) => projectMenu(e.currentTarget);
    PL.$("#search").addEventListener("input", () => { W.clearTimeout(PL._st); PL._st = W.setTimeout(PL.chat.loadList, 250); });
    PL.$("#panel-close").onclick = () => PL.panels.close();
    PL.$("#panel-btn").onclick = () => (PL.$("#panel").hidden ? PL.panels.outline() : PL.panels.close());
    PL.$$(".nav").forEach((b) => b.addEventListener("click", () => {
      app.classList.remove("side-open");
      const g = b.dataset.go;
      if (g === "library") PL.panels.library();
      else if (g === "code") PL.panels.code();
      else if (g === "settings") PL.settings.open();
      else PL.go("#/" + g);
    }));
    D.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); PL.go("#/"); }
      if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test((D.activeElement || {}).tagName || "") && PL.$("#input")) {
        e.preventDefault();
        PL.chat.setInput("/");
        PL.$("#input").dispatchEvent(new W.Event("input"));
      }
    });
    try { await loadProject(); } catch (e) { PL.toast(e.message, "err"); }
    await Promise.all([PL.chat.loadList(), PL.chat.loadSkills()]);
    PL.chat.loadModels();  // probes CLI providers — never blocks the first paint
    wireBus();
    refreshPending();
    PL.dispatch();
    const last = PL.store.get("panel", null);
    if (last && last.kind === "run" && last.arg) PL.panels.run(last.arg);
  }
  PL.boot = boot;
  if (!W.PL_NO_BOOT) {
    if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", boot);
    else boot();
  }
})(window);
