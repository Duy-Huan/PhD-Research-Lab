/* Local data-only theme extensions. Color files never execute scripts or load remote assets. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document;
  const defaults = [
    { id: "lab-midnight", name: "Lab Midnight", base: "dark", colors: { bg: "#181b24", panel: "#202431", side: "#151821", raise: "#282e3d", ink: "#eceef5", "ink-2": "#c4cbdb", muted: "#a4afc5", faint: "#8d99ae", line: "#373f52", "line-2": "#505c73", accent: "#a6b9ff", "accent-2": "#c5d1ff", "accent-ink": "#151821", "accent-soft": "#303c61" } },
    { id: "lab-forest", name: "Lab Forest", base: "light", colors: { bg: "#f2f6f2", panel: "#ffffff", side: "#e8efe9", raise: "#ffffff", ink: "#1b3028", "ink-2": "#344e41", muted: "#586c60", faint: "#6d7e73", line: "#d2ded4", "line-2": "#afc3b3", accent: "#27764b", "accent-2": "#1e5b39", "accent-ink": "#ffffff", "accent-soft": "#e1f0e6" } }
  ];
  const tokens = new Set(["bg", "panel", "side", "raise", "ink", "ink-2", "muted", "faint", "line", "line-2", "accent", "accent-2", "accent-ink", "accent-soft", "ok", "ok-soft", "warn", "warn-soft", "err", "err-soft", "info-soft", "code-bg", "sel"]);
  const vscode = { "editor.background": "bg", "editor.foreground": "ink", "sideBar.background": "side", "sideBar.foreground": "ink-2", "panel.background": "panel", "input.background": "raise", "descriptionForeground": "muted", "panel.border": "line", "focusBorder": "accent", "button.background": "accent", "button.foreground": "accent-ink", "editor.selectionBackground": "sel" };
  const T = PL.themes = {};
  T.validate = function (raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error(PL.t("Gói theme không hợp lệ"));
    const name = String(raw.name || "").trim();
    const id = String(raw.id || name.toLowerCase().replace(/[^a-z0-9-]/g, "-")).slice(0, 64);
    const base = raw.base || (raw.type === "light" ? "light" : "dark");
    if (!name || name.length > 80 || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(id) || ["light", "dark", "system"].includes(id) || !["light", "dark"].includes(base) || !raw.colors || typeof raw.colors !== "object" || Array.isArray(raw.colors)) throw new Error(PL.t("Gói theme không hợp lệ"));
    const colors = {};
    for (const [key, value] of Object.entries(raw.colors)) {
      const token = vscode[key] || key;
      if (!tokens.has(token)) continue;
      if (typeof value !== "string" || !/^#(?:[\da-f]{3}|[\da-f]{4}|[\da-f]{6}|[\da-f]{8})$/i.test(value)) throw new Error(PL.t("Theme chỉ chấp nhận mã màu hex"));
      colors[token] = value;
    }
    if (!Object.keys(colors).length) throw new Error(PL.t("Theme chưa có màu được hỗ trợ"));
    return { id, name, base, colors };
  };
  T.list = function () {
    const saved = PL.store.get("themePackages", []);
    const list = new Map(defaults.map(t => [t.id, t]));
    if (Array.isArray(saved)) for (const raw of saved) {
      try { const t = T.validate(raw); list.set(t.id, t); } catch (e) { /* An invalid saved package cannot break first paint. */ }
    }
    return [...list.values()];
  };
  T.apply = function (id) {
    const pack = T.list().find(t => t.id === id);
    const root = D.documentElement;
    for (const token of tokens) root.style.removeProperty("--" + token);
    if (pack) {
      root.dataset.theme = pack.base;
      root.dataset.themePackage = pack.id;
      for (const [token, value] of Object.entries(pack.colors)) root.style.setProperty("--" + token, value);
    } else {
      delete root.dataset.themePackage;
      if (["light", "dark"].includes(id)) root.dataset.theme = id;
      else delete root.dataset.theme;
    }
    return pack ? pack.id : ["light", "dark"].includes(id) ? id : "system";
  };
  T.select = function (id) {
    const selected = T.apply(id);
    const picker = PL.$("#theme-select");
    if (picker) picker.value = selected;
    try { if (selected === "system") W.localStorage.removeItem("pl.theme"); else W.localStorage.setItem("pl.theme", selected); } catch (e) { /* private mode */ }
    PL.tools.repaintAll();
  };
  T.install = function (raw) {
    const t = T.validate(raw);
    const installed = T.list().filter(p => !defaults.some(d => d.id === p.id) && p.id !== t.id);
    if (defaults.some(d => d.id === t.id)) throw new Error(PL.t("Không thể thay thế theme tích hợp"));
    if (installed.length >= 30) throw new Error(PL.t("Tối đa 30 gói theme"));
    const next = [...installed, t];
    // Do not report success if persistence failed (e.g. a full or disabled local store).
    W.localStorage.setItem("pl.themePackages", JSON.stringify(next));
    T.select(t.id);
    return t;
  };
  T.remove = function (id) {
    W.localStorage.setItem("pl.themePackages", JSON.stringify(T.list().filter(t => !defaults.some(d => d.id === t.id) && t.id !== id)));
    if (D.documentElement.dataset.themePackage === id) T.select("system");
  };
  T.render = function (body) {
    const h = PL.h;
    body.append(h("h3", {}, PL.t("Gói theme")), h("p.help", {}, PL.t("Cài file JSON của PhD Lab hoặc VS Code. Chỉ nhập màu; gói theme không chạy mã.")));
    const grid = h("div.theme-grid");
    for (const t of T.list()) grid.append(h("article.theme-card", {}, h("div.theme-swatch", { style: `background:${t.colors.bg};color:${t.colors.ink};border-color:${t.colors.accent}` }, "Aa"), h("b", {}, t.name),
      h("button.btn.sm", { type: "button", onclick: () => T.select(t.id) }, PL.t("Áp dụng")),
      !defaults.some(d => d.id === t.id) ? h("button.btn.sm.ghost", { type: "button", onclick: () => PL.safe(() => { T.remove(t.id); PL.settings.open("look"); }) }, PL.t("Gỡ cài đặt")) : null));
    const file = h("input#theme-file", { type: "file", hidden: true, accept: ".json,application/json", "aria-label": PL.t("Cài gói theme"), onchange: () => PL.safe(async () => {
      if (!file.files.length) return;
      if (file.files[0].size > 65536) throw new Error(PL.t("Gói theme vượt quá 64 KB"));
      T.install(JSON.parse(await file.files[0].text()));
      await PL.settings.open("look");
    }) });
    body.append(grid, h("button.btn#install-theme", { type: "button", onclick: () => file.click() }, PL.t("Cài gói theme")), file);
  };
  let selected = "system";
  try { selected = W.localStorage.getItem("pl.theme") || "system"; } catch (e) { /* private mode */ }
  T.apply(selected);
})(window);
