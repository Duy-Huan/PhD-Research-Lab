/* PhD Research Lab — core: DOM helpers, API client, live streams, Markdown, icons, toast, dialogs, routing.
   Classic script (no build step): everything hangs off window.PL so the other files and the tests can reach it. */
(function (W) {
  "use strict";
  const PL = (W.PL = W.PL || {});
  const D = W.document;

  // ------------------------------------------------------------------ DOM
  PL.$ = (s, r) => (r || D).querySelector(s);
  PL.$$ = (s, r) => Array.from((r || D).querySelectorAll(s));
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  PL.esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC[c]);
  /** h("button.btn.sm", {onclick, title}, "text", child…) — a tiny element builder (text children are escaped). */
  PL.h = function (spec, attrs, ...kids) {
    const m = String(spec).match(/^([a-z0-9]+)?((?:\.[\w-]*)*)(?:#([\w-]+))?$/i) || [];  // "span.dot." + "" is fine
    const el = D.createElement(m[1] || "div");
    if (m[2]) el.className = m[2].split(".").filter(Boolean).join(" ");
    if (m[3]) el.id = m[3];
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "html") el.innerHTML = v;
      else if (k === "text") el.textContent = v;
      else if (k === "dataset") Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) {
      if (k == null || k === false) continue;
      el.append(k instanceof W.Node ? k : D.createTextNode(String(k)));
    }
    return el;
  };

  // ------------------------------------------------------------------ icons (stroke paths, 24×24)
  const P = {
    plus: "M12 5v14M5 12h14", x: "M6 6l12 12M18 6L6 18", chev: "M6 9l6 6 6-6", send: "M12 19V5M5 12l7-7 7 7",
    stop: "M7 7h10v10H7z", clip: "M21 11l-8.5 8.5a5 5 0 01-7-7L14 4a3.5 3.5 0 015 5l-8.6 8.6a2 2 0 01-2.8-2.8L15 7.5",
    sidebar: "M4 5h16v14H4zM9 5v14", panel: "M4 5h16v14H4zM15 5v14", gauge: "M12 14l4-4M4 18a9 9 0 1116 0",
    book: "M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 5v16", code: "M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14",
    review: "M4 4h12l4 4v12H4zM8 12h8M8 16h5M8 8h4", gear: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z",
    copy: "M9 9h11v11H9zM5 15H4V4h11v1", retry: "M4 4v6h6M20 20v-6h-6M5.6 15a8 8 0 0013.8 2.6M18.4 9A8 8 0 004.6 6.4",
    pin: "M12 17v5M8 3h8l-1 6 3 4H6l3-4z", brain: "M12 5a3 3 0 00-5.6-1.5A3 3 0 004 8a3 3 0 00.5 5.5A3 3 0 008 19a3 3 0 004 1V5zM12 5a3 3 0 015.6-1.5A3 3 0 0120 8a3 3 0 01-.5 5.5A3 3 0 0116 19a3 3 0 01-4 1",
    alert: "M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
    check: "M5 12l5 5L20 7", play: "M7 5l12 7-12 7z", file: "M14 3H6v18h12V7zM14 3v4h4", upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
    ext: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6", trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13", dots: "M5 12h.01M12 12h.01M19 12h.01",
    sync: "M20 11a8 8 0 00-14.9-3M4 5v4h4M4 13a8 8 0 0014.9 3M20 19v-4h-4", spark: "M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z",
    flask: "M9 3h6M10 3v6L4 19a1.5 1.5 0 001.3 2h13.4A1.5 1.5 0 0020 19l-6-10V3", folder: "M3 6a2 2 0 012-2h4l2 2h8a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2z",
  };
  PL.icon = (n) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${P[n] || ""}"/></svg>`;
  PL.paintIcons = (root) => PL.$$("[data-i]", root).forEach((el) => {
    if (!el.firstElementChild || el.firstElementChild.tagName !== "svg") el.insertAdjacentHTML("afterbegin", PL.icon(el.dataset.i));
  });

  // ------------------------------------------------------------------ API
  class ApiError extends Error {
    constructor(status, detail, data) { super(detail); this.status = status; this.data = data; }
  }
  PL.ApiError = ApiError;
  PL.api = async function (method, url, body, opts) {
    const init = { method, headers: { "X-PhDLab-Client": "ui" } };
    if (body instanceof W.FormData) init.body = body;
    else if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    if (opts && opts.signal) init.signal = opts.signal;
    let r;
    try { r = await W.fetch(url, init); } catch (e) {
      if (e && e.name === "AbortError") throw e;
      PL.online(false);
      throw new ApiError(0, "Không kết nối được máy chủ PhD Lab");
    }
    PL.online(true);
    const ct = r.headers.get("content-type") || "";
    const data = ct.includes("json") ? await r.json() : await r.text();
    if (!r.ok) {
      let d = data && data.detail !== undefined ? data.detail : data;
      if (d && typeof d === "object") d = d.message || JSON.stringify(d);
      throw new ApiError(r.status, String(d || r.statusText || "Lỗi"), data);
    }
    return data;
  };
  PL.get = (u) => PL.api("GET", u);
  PL.post = (u, b) => PL.api("POST", u, b === undefined ? {} : b);
  PL.put = (u, b) => PL.api("PUT", u, b);
  PL.del = (u) => PL.api("DELETE", u);
  PL.upload = (url, files, field) => {
    const fd = new W.FormData();
    for (const f of [].concat(files)) fd.append(field || "file", f);
    return PL.api("POST", url, fd);
  };
  /** Run fn; show its error as a toast instead of throwing (UI handlers). */
  PL.safe = async function (fn, okMsg) {
    try { const r = await fn(); if (okMsg) PL.toast(okMsg); return r; } catch (e) { PL.toast(e.message || String(e), "err"); return undefined; }
  };

  let offline = false;
  PL.online = function (ok) {
    if (ok === !offline) return;
    offline = !ok;
    const b = PL.$("#offline");
    if (b) b.hidden = ok;
  };

  /** EventSource with reconnect; onEvent(obj). Returns {close()}. url gets after=<last seq> on reconnect. */
  PL.stream = function (url, onEvent, opts) {
    let es = null, closed = false, after = (opts && opts.after) || 0, retry = 800;
    const open = () => {
      if (closed) return;
      const sep = url.includes("?") ? "&" : "?";
      es = new W.EventSource(url + sep + "after=" + after);
      es.onmessage = (m) => {
        retry = 800;
        let ev;
        try { ev = JSON.parse(m.data); } catch (e) { return; }
        if (typeof ev.seq === "number" && ev.type !== "hello") after = Math.max(after, ev.seq);
        if (ev.type === "hello" && typeof ev.seq === "number" && !after) after = ev.seq;
        if (ev.type === "stream.timeout") { es.close(); open(); return; }
        onEvent(ev);
      };
      es.onopen = () => { PL.online(true); if (opts && opts.onOpen) opts.onOpen(); };
      es.onerror = () => {
        es.close();
        if (opts && opts.onError) opts.onError();
        if (!closed) { W.setTimeout(open, retry); retry = Math.min(retry * 2, 15000); }
      };
    };
    open();
    return { close() { closed = true; if (es) es.close(); }, get after() { return after; } };
  };

  // app-wide bus (UI ⇄ CLI): PL.on("run.", fn) subscribes by type prefix
  const subs = [];
  PL.on = (prefix, fn) => { subs.push([prefix, fn]); return () => subs.splice(subs.findIndex((s) => s[1] === fn), 1); };
  PL.emit = (ev) => subs.slice().forEach(([p, fn]) => { if (!p || String(ev.type || "").startsWith(p)) { try { fn(ev); } catch (e) { /* listener errors never break the bus */ } } });
  PL.startBus = function () {
    const live = PL.$("#live");
    return PL.stream("/api/events/stream", (ev) => { if (ev.type !== "hello") PL.emit(ev); }, {
      onOpen: () => { if (live) { live.className = "dot live"; live.title = "Đang đồng bộ với CLI"; } },
      onError: () => { if (live) { live.className = "dot warn"; live.title = "Mất đồng bộ — đang kết nối lại"; } },
    });
  };

  // ------------------------------------------------------------------ Markdown (marked + DOMPurify; KaTeX / highlight.js on demand)
  const HIDE = /```phdlab-(action|memory)\s*\n[\s\S]*?```/g;
  const loaded = {};
  function load(src, css) {
    if (loaded[src]) return loaded[src];
    loaded[src] = new Promise((res) => {
      if (css) D.head.append(PL.h("link", { rel: "stylesheet", href: css }));
      const s = PL.h("script", { src });
      s.onload = () => res(true);
      s.onerror = () => res(false);
      D.head.append(s);
    });
    return loaded[src];
  }
  PL.load = load;
  function protectMath(src) {
    const math = [];
    const out = src
      .replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => { math.push([m, true]); return `@@M${math.length - 1}@@`; })
      .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => { math.push([m, true]); return `@@M${math.length - 1}@@`; })
      .replace(/(^|[^\\$\w])\$(?!\s)([^$\n]{0,300}?[^\s$])\$(?!\w)/g, (_, pre, m) => { math.push([m, false]); return `${pre}@@M${math.length - 1}@@`; });
    return { out, math };
  }
  PL.md = function (text) {
    const src = String(text || "").replace(HIDE, "").trim();
    const { out, math } = protectMath(src);
    let html = W.marked ? W.marked.parse(out, { gfm: true, breaks: false }) : PL.esc(out).replace(/\n/g, "<br>");
    html = html.replace(/@@M(\d+)@@/g, (_, i) => {
      const [m, display] = math[+i];
      return `<span class="math${display ? " display" : ""}" data-tex="${PL.esc(m)}">${PL.esc(display ? "$$" + m + "$$" : "$" + m + "$")}</span>`;
    });
    return W.DOMPurify ? W.DOMPurify.sanitize(html, { ADD_ATTR: ["data-tex", "target"] }) : PL.esc(src);
  };
  /** Render Markdown into el, then enhance it (math, code highlight, copy buttons, external links). */
  PL.rich = function (el, text) {
    el.innerHTML = PL.md(text);
    PL.$$("a[href^='http']", el).forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
    const maths = PL.$$(".math", el);
    if (maths.length) {
      load("/vendor/katex/katex.min.js", "/vendor/katex/katex.min.css").then((ok) => {
        if (!ok || !W.katex) return;
        maths.forEach((m) => { try { W.katex.render(m.dataset.tex, m, { displayMode: m.classList.contains("display"), throwOnError: false }); } catch (e) { /* keep the source */ } });
      });
    }
    const codes = PL.$$("pre > code", el);
    codes.forEach((c) => {
      const b = PL.h("button.copy-code", { type: "button", onclick: () => PL.copy(c.textContent) }, "Sao chép");
      c.parentElement.append(b);
    });
    if (codes.length) {
      const dark = D.documentElement.dataset.theme === "dark" || (!D.documentElement.dataset.theme && W.matchMedia && W.matchMedia("(prefers-color-scheme: dark)").matches);
      load("/vendor/hljs/highlight.min.js", dark ? "/vendor/hljs/github-dark.min.css" : "/vendor/hljs/github.min.css").then((ok) => {
        if (ok && W.hljs) codes.forEach((c) => { try { W.hljs.highlightElement(c); } catch (e) { /* plain text */ } });
      });
    }
    return el;
  };
  PL.copy = function (text) {
    const done = () => PL.toast("Đã sao chép");
    if (W.navigator.clipboard) W.navigator.clipboard.writeText(text).then(done, () => PL.toast("Không sao chép được", "err"));
    else done();
  };

  // ------------------------------------------------------------------ toast + dialogs
  let tt = 0;
  PL.toast = function (msg, kind) {
    const t = PL.$("#toast");
    if (!t) return;
    t.textContent = msg;
    t.className = "show" + (kind === "err" ? " err" : "");
    W.clearTimeout(tt);
    tt = W.setTimeout(() => { t.className = ""; }, kind === "err" ? 5200 : 2600);
  };
  /** modal({title, body: Node|string, actions:[{label, kind, onClick → false keeps it open}], wide}) → close() */
  PL.modal = function (o) {
    const m = PL.$("#modal");
    const close = () => { m.hidden = true; m.innerHTML = ""; D.removeEventListener("keydown", onKey); if (o.onClose) o.onClose(); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    const body = typeof o.body === "string" ? PL.h("div", { html: o.body }) : o.body;
    const foot = (o.actions || []).length ? PL.h("div.dialog-f", {}, o.actions.map((a) =>
      PL.h("button.btn" + (a.kind ? "." + a.kind : ""), { type: "button", onclick: async () => { if ((await a.onClick?.()) !== false) close(); } }, a.label))) : null;
    const dlg = PL.h("div.dialog" + (o.wide ? ".wide" : ""), { role: "dialog", "aria-modal": "true", "aria-label": o.title || "" },
      PL.h("div.dialog-h", {}, PL.h("h2", {}, o.title || ""), PL.h("button.icon", { type: "button", "aria-label": "Đóng", onclick: close, html: PL.icon("x") })),
      o.raw ? body : PL.h("div.dialog-b", {}, body), foot);
    m.innerHTML = "";
    m.append(dlg);
    m.hidden = false;
    m.onclick = (e) => { if (e.target === m) close(); };
    D.addEventListener("keydown", onKey);
    const f = dlg.querySelector("input, textarea, select");
    if (f) f.focus();
    return close;
  };
  PL.confirm = (text, okLabel) => new Promise((res) => {
    let v = false;
    PL.modal({ title: "Xác nhận", body: PL.h("p", {}, text), onClose: () => res(v),
      actions: [{ label: "Huỷ" }, { label: okLabel || "Đồng ý", kind: "accent", onClick: () => { v = true; } }] });
  });
  PL.prompt = (title, label, value) => new Promise((res) => {
    const inp = PL.h("input.input", { value: value || "" });
    let v = null;
    PL.modal({ title, body: PL.h("label.field", {}, PL.h("span", {}, label), inp), onClose: () => res(v),
      actions: [{ label: "Huỷ" }, { label: "Lưu", kind: "accent", onClick: () => { v = inp.value.trim(); } }] });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { v = inp.value.trim(); PL.$("#modal").hidden = true; PL.$("#modal").innerHTML = ""; res(v); } });
  });

  // ------------------------------------------------------------------ formatting
  PL.ago = function (ts) {
    if (!ts) return "";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "vừa xong";
    if (s < 3600) return Math.floor(s / 60) + " phút trước";
    if (s < 86400) return Math.floor(s / 3600) + " giờ trước";
    if (s < 86400 * 7) return Math.floor(s / 86400) + " ngày trước";
    return new Date(ts * 1000).toLocaleDateString("vi-VN");
  };
  PL.size = (n) => (n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? Math.round(n / 1e3) + " KB" : (n || 0) + " B");
  PL.STATUS = {
    CREATED: "Đã tạo", PLANNED: "Đã lập kế hoạch", APPROVAL_PENDING: "Chờ duyệt", RUNNING: "Đang chạy", VERIFYING: "Đang kiểm chứng",
    COMPLETED: "Hoàn tất", BLOCKED: "Đang chờ tài nguyên", FAILED: "Lỗi", RECOVERING: "Đang phục hồi", NEEDS_USER_ACTION: "Cần bạn quyết định",
    CANCELLED: "Đã huỷ",
  };
  PL.statusChip = (s) => PL.h("span.chip.status-chip", { dataset: { s } }, PL.STATUS[s] || s);

  // ------------------------------------------------------------------ routing (#/chat/<id> · #/dashboard · #/review/<id> …)
  const routes = {};
  PL.route = (name, fn) => { routes[name] = fn; };
  PL.go = (hash) => { if (W.location.hash === hash) PL.dispatch(); else W.location.hash = hash; };
  PL.dispatch = function () {
    const parts = (W.location.hash || "#/").replace(/^#\/?/, "").split("/");
    const fn = routes[parts[0]] || routes[""];
    if (fn) fn(...parts.slice(1).map(decodeURIComponent));
  };
  W.addEventListener("hashchange", () => PL.dispatch());

  PL.store = {
    get: (k, d) => { try { const v = W.localStorage.getItem("pl." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: (k, v) => { try { W.localStorage.setItem("pl." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };
})(window);
