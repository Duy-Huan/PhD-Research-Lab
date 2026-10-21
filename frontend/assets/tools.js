/* PhD Research Lab — chat tools: interactive charts (```chart), SVG figures (```svg), diagrams (```mermaid), export of an
   answer or a whole conversation (PDF · Word · LaTeX · Markdown · HTML) and notes pinned to a passage or a chart point.
   No dependency: charts are drawn as SVG here (validated categorical palette, light + dark steps); mermaid is loaded
   on demand from /vendor. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document, h = PL.h;
  const T = (PL.tools = {});
  const NS = "http://www.w3.org/2000/svg";

  // validated categorical palette (8 slots, fixed order) + chart surfaces, light and dark
  const PALETTE = {
    light: { series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
      surface: "#ffffff", ink: "#1c1b19", ink2: "#52514e", grid: "#ebe9e3", axis: "#d4d0c5" },
    dark: { series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
      surface: "#252422", ink: "#ecebe6", ink2: "#c3c2b7", grid: "#34322e", axis: "#45423c" },
  };
  T.dark = () => D.documentElement.dataset.theme === "dark" ||
    (!D.documentElement.dataset.theme && !!(W.matchMedia && W.matchMedia("(prefers-color-scheme: dark)").matches));

  // ------------------------------------------------------------------ chart spec
  /** Parse + validate a ```chart block. Returns {ok, spec} or {ok:false, error}. */
  T.parseChart = function (src) {
    let s;
    try { s = JSON.parse(src); } catch (e) { return { ok: false, error: PL.t("JSON biểu đồ không hợp lệ") }; }
    if (!s || typeof s !== "object") return { ok: false, error: PL.t("JSON biểu đồ không hợp lệ") };
    const type = ["line", "bar", "scatter", "area"].includes(s.type) ? s.type : "line";
    const series = (Array.isArray(s.series) ? s.series : []).filter((x) => x && Array.isArray(x.data)).slice(0, 8)
      .map((x, i) => ({ name: String(x.name || "S" + (i + 1)), data: x.data.map((v) => (v == null || v === "" ? null : Number(v))),
        error: Array.isArray(x.error) ? x.error.map(Number) : null, x: Array.isArray(x.x) ? x.x : null }));
    if (!series.length) return { ok: false, error: PL.t("Biểu đồ không có dữ liệu") };
    const n = Math.max(...series.map((x) => x.data.length));
    const x = Array.isArray(s.x) && s.x.length ? s.x.slice(0, n) : Array.from({ length: n }, (_, i) => i + 1);
    return { ok: true, spec: { type, title: String(s.title || ""), x, series, xlabel: String(s.xlabel || ""), ylabel: String(s.ylabel || ""),
      ylog: !!s.ylog, note: String(s.note || "") } };
  };

  function niceTicks(lo, hi, count) {
    if (!(hi > lo)) { hi = lo + 1; lo = lo - 1; }
    const step0 = (hi - lo) / Math.max(1, count);
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((k) => k >= step0) || 10 * mag;
    const out = [];
    for (let v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) out.push(+v.toFixed(10));
    return out;
  }
  const fmt = (v) => (Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(1) : +(+v).toPrecision(4) + "");
  function el(tag, attrs, parent) {
    const e = D.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }

  /** Draw the chart as a standalone <svg> (colors inlined, so it serialises for PNG / PDF export). */
  T.svgChart = function (spec, opts) {
    opts = opts || {};
    const P = PALETTE[opts.theme || (T.dark() ? "dark" : "light")];
    // drawn at the width it is shown at (text stays ~11 px on a phone); 640 for exports
    const Wd = Math.round(Math.max(300, Math.min(760, opts.width || 640))), Ht = Wd < 480 ? 280 : 340;
    const m = { l: 56, r: 18, t: spec.series.length > 1 ? 34 : 16, b: spec.xlabel ? 52 : 38 };
    const svg = el("svg", { viewBox: `0 0 ${Wd} ${Ht}`, xmlns: NS, role: "img", "aria-label": spec.title || PL.t("Biểu đồ"),
      "font-family": "Segoe UI, system-ui, sans-serif", "font-size": "11" });
    el("rect", { x: 0, y: 0, width: Wd, height: Ht, fill: P.surface }, svg);
    const numericX = spec.type === "scatter" || spec.x.every((v) => typeof v === "number");
    const vals = [];
    spec.series.forEach((s) => s.data.forEach((v, i) => { if (Number.isFinite(v)) { const e = (s.error || [])[i] || 0; vals.push(v - e, v + e); } }));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const log = spec.ylog && lo > 0;
    if (spec.type === "bar" || spec.type === "area") lo = Math.min(0, lo);
    const tf = (v) => (log ? Math.log10(v) : v);
    const ticks = log ? niceTicks(Math.floor(tf(lo)), Math.ceil(tf(hi)), 4) : niceTicks(lo, hi, 5);
    const y0 = ticks[0], y1 = ticks[ticks.length - 1];
    const iw = Wd - m.l - m.r, ih = Ht - m.t - m.b;
    const Y = (v) => m.t + ih - ((tf(v) - y0) / (y1 - y0 || 1)) * ih;
    let X, xs;
    if (numericX && spec.type !== "bar") {
      const all = spec.series.flatMap((s) => (s.x || spec.x)).map(Number).filter(Number.isFinite);
      xs = niceTicks(Math.min(...all), Math.max(...all), 6);
      X = (v) => m.l + ((Number(v) - xs[0]) / (xs[xs.length - 1] - xs[0] || 1)) * iw;
    } else {
      const band = iw / spec.x.length;
      X = (v, i) => m.l + band * (i + 0.5);
      X.band = band;
    }
    // grid + axes (hairline, recessive)
    const g = el("g", {}, svg);
    for (const t of ticks) {
      const yy = Y(log ? Math.pow(10, t) : t);
      el("line", { x1: m.l, x2: Wd - m.r, y1: yy, y2: yy, stroke: P.grid, "stroke-width": 1 }, g);
      el("text", { x: m.l - 8, y: yy + 3.5, "text-anchor": "end", fill: P.ink2 }, g).textContent = log ? "1e" + t : fmt(t);
    }
    el("line", { x1: m.l, x2: Wd - m.r, y1: m.t + ih, y2: m.t + ih, stroke: P.axis, "stroke-width": 1 }, g);
    if (xs) xs.forEach((t) => { el("text", { x: X(t), y: m.t + ih + 16, "text-anchor": "middle", fill: P.ink2 }, g).textContent = fmt(t); });
    else {
      const every = Math.ceil(spec.x.length / 12);
      spec.x.forEach((v, i) => { if (i % every === 0) el("text", { x: X(v, i), y: m.t + ih + 16, "text-anchor": "middle", fill: P.ink2 }, g).textContent = String(v).slice(0, 14); });
    }
    if (spec.xlabel) el("text", { x: m.l + iw / 2, y: Ht - 10, "text-anchor": "middle", fill: P.ink2 }, g).textContent = spec.xlabel;
    if (spec.ylabel) el("text", { x: 14, y: m.t + ih / 2, "text-anchor": "middle", fill: P.ink2, transform: `rotate(-90 14 ${m.t + ih / 2})` }, g).textContent = spec.ylabel;
    // legend (≥ 2 series), text in ink, swatch carries identity
    if (spec.series.length > 1) {
      let lx = m.l;
      spec.series.forEach((s, k) => {
        el("rect", { x: lx, y: 10, width: 10, height: 10, rx: 2, fill: P.series[k] }, svg);
        const t = el("text", { x: lx + 15, y: 19, fill: P.ink }, svg);
        t.textContent = s.name;
        lx += 26 + Math.min(150, s.name.length * 6.4);
      });
    }
    // marks
    const pts = [];
    const nS = spec.series.length;
    spec.series.forEach((s, k) => {
      const c = P.series[k];
      const sx = s.x || spec.x;
      const coords = s.data.map((v, i) => (Number.isFinite(v) ? { x: X(sx[i], i), y: Y(v), v, i, xv: sx[i] } : null));
      if (spec.type === "bar") {
        const bw = Math.min(24, (X.band * 0.72) / nS);
        coords.forEach((p) => {
          if (!p) return;
          const bx = p.x - (bw * nS) / 2 + k * bw + 1, base = Y(Math.max(0, y0)), top = Math.min(p.y, base), hgt = Math.abs(base - p.y);
          const r = Math.min(4, hgt, (bw - 2) / 2);
          el("path", { d: `M${bx},${base} V${top + r} q0,-${r} ${r},-${r} H${bx + bw - 2 - r} q${r},0 ${r},${r} V${base} Z`, fill: c }, svg);
          pts.push({ ...p, x: bx + (bw - 2) / 2, y: top, k, s });
        });
      } else {
        const d = coords.reduce((acc, p) => (p ? acc + (acc && !acc.endsWith("|") ? " L" : "M") + p.x.toFixed(1) + "," + p.y.toFixed(1) : acc + "|"), "").replace(/\|+M?/g, " M").replace(/^ M/, "M");
        if (spec.type === "area" && coords.filter(Boolean).length > 1) {
          const f = coords.filter(Boolean);
          el("path", { d: `M${f[0].x},${Y(Math.max(0, y0))} L` + f.map((p) => p.x + "," + p.y).join(" L") + ` L${f[f.length - 1].x},${Y(Math.max(0, y0))} Z`, fill: c, "fill-opacity": 0.14 }, svg);
        }
        if (spec.type !== "scatter") el("path", { d, fill: "none", stroke: c, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
        coords.forEach((p) => {
          if (!p) return;
          const e = (s.error || [])[p.i];
          if (Number.isFinite(e) && e > 0) {
            el("path", { d: `M${p.x},${Y(p.v - e)} V${Y(p.v + e)} M${p.x - 4},${Y(p.v - e)} H${p.x + 4} M${p.x - 4},${Y(p.v + e)} H${p.x + 4}`, stroke: c, "stroke-width": 1.4, fill: "none" }, svg);
          }
          el("circle", { cx: p.x, cy: p.y, r: spec.type === "scatter" ? 5 : 4, fill: c, stroke: P.surface, "stroke-width": 2 }, svg);
          pts.push({ ...p, k, s });
        });
      }
    });
    // notes on points: numbered badges
    svg._w = Wd;
    (opts.marks || []).forEach((mk, n) => {
      const p = pts.find((q) => q.s.name === mk.series && String(q.xv) === String(mk.x));
      if (!p) return;
      el("circle", { cx: p.x, cy: p.y - 14, r: 8, fill: "#b8501f" }, svg);
      el("text", { x: p.x, y: p.y - 10.5, "text-anchor": "middle", fill: "#fff", "font-size": "10", "font-weight": "600" }, svg).textContent = String(mk.n || n + 1);
    });
    svg._pts = pts;
    return svg;
  };

  /** The interactive figure: SVG + hover tooltip + click a point to note it + table view + PNG / SVG download. */
  T.chart = function (spec, opts) {
    opts = opts || {};
    const fig = h("figure.chart", { "data-chart": "1" });
    const tip = h("div.chart-tip", { role: "status", hidden: true });
    const holder = h("div.chart-svg");
    let table = null;
    const paint = () => {
      holder.innerHTML = "";
      const svg = T.svgChart(spec, { marks: opts.marks && opts.marks(), width: holder.clientWidth || 640 });
      holder.append(svg);
      const near = (ev) => {
        const r = svg.getBoundingClientRect();
        const sx = svg._w / (r.width || svg._w), px = (ev.clientX - r.left) * sx, py = (ev.clientY - r.top) * sx;
        let best = null, bd = 1e9;
        for (const p of svg._pts) { const dd = Math.hypot(p.x - px, p.y - py); if (dd < bd) { bd = dd; best = p; } }
        return bd < 28 ? best : null;  // hit target larger than the mark
      };
      svg.addEventListener("mousemove", (ev) => {
        const p = near(ev);
        if (!p) { tip.hidden = true; svg.style.cursor = ""; return; }
        svg.style.cursor = opts.onPoint ? "pointer" : "";
        tip.hidden = false;
        tip.textContent = `${p.s.name} · ${spec.xlabel || "x"} = ${p.xv} · ${spec.ylabel || "y"} = ${fmt(p.v)}` + ((p.s.error || [])[p.i] ? ` ± ${fmt(p.s.error[p.i])}` : "");
        const r = holder.getBoundingClientRect();
        tip.style.left = Math.min(r.width - 10, Math.max(10, ev.clientX - r.left)) + "px";
        tip.style.top = (ev.clientY - r.top - 12) + "px";
      });
      svg.addEventListener("mouseleave", () => { tip.hidden = true; });
      svg.addEventListener("click", (ev) => {
        const p = near(ev);
        if (p && opts.onPoint) opts.onPoint({ chart: spec.title || "chart", series: p.s.name, x: String(p.xv), y: fmt(p.v), label: `${p.s.name} @ ${p.xv}` }, ev);
      });
    };
    paint();
    T.charts.add(fig);
    // first drawn before the answer is on the page: redraw once at the real width
    (W.requestAnimationFrame || ((f) => W.setTimeout(f, 16)))(() => {
      const svg = holder.firstChild;
      if (fig.isConnected && svg && holder.clientWidth && Math.abs(holder.clientWidth - svg._w) > 40) paint();
    });
    const tools = h("div.chart-tools", {},
      h("button.btn.sm.ghost", { type: "button", onclick: () => {
        if (table) { table.remove(); table = null; return; }
        table = h("table.grid.chart-table", {}, h("tr", {}, h("th", {}, spec.xlabel || "x"), spec.series.map((s) => h("th", {}, s.name))),
          spec.x.map((xv, i) => h("tr", {}, h("td", {}, String(xv)), spec.series.map((s) => h("td", {}, s.data[i] == null ? "—" : fmt(s.data[i]) + ((s.error || [])[i] ? " ± " + fmt(s.error[i]) : ""))))));
        fig.append(table);
      } }, PL.t("Bảng dữ liệu")),
      h("button.btn.sm.ghost", { type: "button", onclick: async () => download(await T.png(spec), (spec.title || "chart") + ".png") }, "PNG"),
      h("button.btn.sm.ghost", { type: "button", onclick: () => download("data:image/svg+xml;charset=utf-8," + encodeURIComponent(new W.XMLSerializer().serializeToString(T.svgChart(spec, { theme: "light" }))), (spec.title || "chart") + ".svg") }, "SVG"),
      opts.onPoint ? h("span.muted.chart-hint", {}, PL.t("Bấm vào một điểm để ghi chú")) : null);
    fig.append(...[spec.title ? h("figcaption", {}, spec.title) : null, h("div.chart-wrap", {}, holder, tip), tools,
      spec.note ? h("div.muted.chart-note", {}, spec.note) : null].filter(Boolean));
    fig._spec = spec;
    fig._repaint = paint;
    return fig;
  };
  // live charts repaint when the theme or the width changes (dark steps are selected, not flipped); figures that left
  // the page are forgotten
  T.charts = new Set();
  T.repaintAll = () => T.charts.forEach((f) => { if (f.isConnected) f._repaint(); else T.charts.delete(f); });
  if (W.matchMedia) {
    const mq = W.matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", T.repaintAll);
  }
  let rz = 0;
  W.addEventListener("resize", () => { W.clearTimeout(rz); rz = W.setTimeout(T.repaintAll, 200); });

  function download(href, name) {
    const a = h("a", { href, download: name });
    D.body.append(a);
    a.click();
    a.remove();
  }
  T.download = download;

  /** SVG (string or element) → PNG data URL at 2× (for Word / LaTeX export and the PNG button). */
  T.svgToPng = function (svgEl) {
    return new Promise((res) => {
      const xml = typeof svgEl === "string" ? svgEl : new W.XMLSerializer().serializeToString(svgEl);
      const vb = /viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"/.exec(xml);
      const w = vb ? +vb[1] : 640, ht = vb ? +vb[2] : 340;
      const img = new W.Image();
      img.onload = () => {
        const c = D.createElement("canvas");
        c.width = w * 2; c.height = ht * 2;
        const ctx = c.getContext && c.getContext("2d");
        if (!ctx) { res(""); return; }
        ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
        ctx.drawImage(img, 0, 0, c.width, c.height);
        try { res(c.toDataURL("image/png")); } catch (e) { res(""); }
      };
      img.onerror = () => res("");
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
    });
  };
  T.png = (spec) => T.svgToPng(T.svgChart(spec, { theme: "light" }));

  // ------------------------------------------------------------------ fenced blocks inside rendered answers
  /** Replace ```chart / ```svg / ```mermaid code blocks of a rendered answer by their figures. */
  T.enhance = function (root, ctx) {
    ctx = ctx || {};
    const blocks = PL.$$("pre > code", root);
    let nChart = 0, nSvg = 0;
    for (const code of blocks) {
      const lang = ((/language-(\w+)/.exec(code.className) || [])[1] || "").toLowerCase();
      const pre = code.parentElement;
      if (lang === "chart") {
        const idx = nChart++;
        const r = T.parseChart(code.textContent);
        if (!r.ok) { pre.before(h("div.err-line", {}, r.error)); continue; }
        const fig = T.chart(r.spec, { onPoint: ctx.onPoint ? (pt, ev) => ctx.onPoint(pt, ev) : null, marks: ctx.marks ? () => ctx.marks(r.spec.title || "chart") : null });
        fig.dataset.idx = String(idx);
        pre.replaceWith(fig);
      } else if (lang === "svg") {
        const idx = nSvg++;
        const clean = W.DOMPurify ? W.DOMPurify.sanitize(code.textContent, { USE_PROFILES: { svg: true, svgFilters: true } }) : "";
        if (!/<svg[\s>]/i.test(clean)) continue;
        const fig = h("figure.svg-figure", { html: clean, dataset: { idx: String(idx) } });
        const s = fig.querySelector("svg");
        if (s && !s.getAttribute("viewBox") && s.getAttribute("width") && s.getAttribute("height")) s.setAttribute("viewBox", `0 0 ${parseFloat(s.getAttribute("width"))} ${parseFloat(s.getAttribute("height"))}`);
        pre.replaceWith(fig);
      } else if (lang === "mermaid") {
        const fig = h("figure.mermaid-figure", {}, h("span.spin"));
        const src = code.textContent;
        pre.replaceWith(fig);
        T.mermaid(src).then((svg) => {
          fig.innerHTML = "";
          if (svg) fig.innerHTML = W.DOMPurify ? W.DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true, html: true } }) : "";
          else fig.append(h("pre.preview-box.mono", {}, src));
        });
      }
    }
  };
  let mid = 0;
  T.mermaid = async function (src) {
    const ok = await PL.load("/vendor/mermaid/mermaid.min.js");
    if (!ok || !W.mermaid) return "";
    if (!T._mm) { W.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: T.dark() ? "dark" : "neutral", fontFamily: "Segoe UI, system-ui, sans-serif",
      htmlLabels: false, flowchart: { htmlLabels: false } });  // SVG <text> labels: they survive sanitising and export
      T._mm = true;
    }
    try { return (await W.mermaid.render("mmd" + (++mid), src)).svg; } catch (e) { return ""; }
  };

  // ------------------------------------------------------------------ export
  const FORMATS = [["pdf", "PDF (.pdf)"], ["docx", "Word (.docx)"], ["tex", "LaTeX (.tex)"], ["md", "Markdown (.md)"], ["html", "HTML (.html)"]];
  /** Images of the rendered figures of el, keyed like the backend expects ("chart-<n>", "svg-<n>"). */
  async function figureImages(el) {
    const out = {};
    for (const f of PL.$$("figure.chart", el)) if (f._spec) { const p = await T.png(f._spec); if (p) out["chart-" + f.dataset.idx] = p; }
    for (const f of PL.$$("figure.svg-figure", el)) { const s = f.querySelector("svg"); if (s) { const p = await T.svgToPng(s); if (p) out["svg-" + f.dataset.idx] = p; } }
    return out;
  }
  /** Printable HTML of rendered answers: charts redrawn with the light palette, UI controls removed. */
  function printableHtml(els) {
    return els.map((el) => {
      const c = el.cloneNode(true);
      PL.$$(".chart-tools, .chart-tip, .chart-table, .msg-actions, .copy-code, .note-pop", c).forEach((x) => x.remove());
      PL.$$("figure.chart", c).forEach((f, i) => {
        const live = PL.$$("figure.chart", el)[i];
        const holder = f.querySelector(".chart-svg");
        if (live && live._spec && holder) { holder.innerHTML = ""; holder.append(T.svgChart(live._spec, { theme: "light" })); }
      });
      return c.outerHTML;
    }).join("\n");
  }
  T.printableHtml = printableHtml;

  /** Export {title, markdown, els:[rendered answer nodes]} to fmt; PDF falls back to the browser's print dialog. */
  T.exportAs = async function (fmt, doc) {
    const body = { format: fmt, title: doc.title || "", markdown: doc.markdown || "" };
    if(PL.research && PL.research.tid)body.topic_id=PL.research.tid;
    if (fmt === "pdf" || fmt === "html") body.html = printableHtml(doc.els || []);
    if (fmt === "docx" || fmt === "tex") body.images = Object.assign({}, ...(await Promise.all((doc.els || []).map(figureImages))));
    PL.toast(PL.t("Đang xuất {0}…", fmt.toUpperCase()));
    let r;
    try {
      r = await W.fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json", "X-PhDLab-Client": "ui" }, body: JSON.stringify(body) });
    } catch (e) { PL.toast(PL.t("Không kết nối được máy chủ PhD Lab"), "err"); return; }
    if (r.status === 501 && fmt === "pdf") { printFallback(body.html, doc.title); return; }
    if (!r.ok) { const d = await r.json().catch(() => ({})); PL.toast(d.detail || r.statusText, "err"); return; }
    const blob = await r.blob();
    const cd = r.headers.get("content-disposition") || "";
    const name = decodeURIComponent((/filename\*=UTF-8''([^;]+)/.exec(cd) || [])[1] || "export." + fmt);
    const url = W.URL.createObjectURL(blob);
    download(url, name);
    W.setTimeout(() => W.URL.revokeObjectURL(url), 4000);
    PL.toast(PL.t("Đã xuất {0} · bản sao lưu trong exports/ của dự án", name));
  };
  function printFallback(html, title) {
    const w = W.open("", "_blank");
    if (!w) { PL.toast(PL.t("Trình duyệt chặn cửa sổ in"), "err"); return; }
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${PL.esc(title || "PhD Research Lab")}</title><link rel="stylesheet" href="/vendor/katex/katex.min.css"><link rel="stylesheet" href="/assets/app.css"></head><body class="print-doc"><div class="prose">${html}</div></body></html>`);
    w.document.close();
    w.setTimeout(() => w.print(), 400);
  }
  T.exportMenu = function (anchor, doc) {
    PL.menu(anchor, [{ header: PL.t("Xuất ra") }].concat(FORMATS.map(([k, l]) => ({ label: l, run: () => T.exportAs(k, typeof doc === "function" ? doc() : doc) }))));
  };

  // ------------------------------------------------------------------ notes on passages
  /** Wrap the passage `quote` (disambiguated by prefix) of root in <mark class="note-hl">. True when found. */
  T.highlight = function (root, note, n) {
    const walker = D.createTreeWalker(root, 4 /* SHOW_TEXT */, { acceptNode: (t) => (t.parentElement && t.parentElement.closest(".katex, .chart, pre, mark.note-hl") ? 2 : 1) });
    const nodes = [];
    let text = "";
    for (let t = walker.nextNode(); t; t = walker.nextNode()) { nodes.push([t, text.length]); text += t.nodeValue; }
    const q = note.quote || "";
    if (!q) return false;
    let at = -1;
    if (note.prefix) { const k = text.indexOf(note.prefix + q); if (k >= 0) at = k + note.prefix.length; }
    if (at < 0) at = text.indexOf(q);
    if (at < 0) return false;
    const end = at + q.length;
    for (const [t, off] of nodes) {
      const len = t.nodeValue.length;
      const a = Math.max(at, off), b = Math.min(end, off + len);
      if (a >= b) continue;
      let node = t;
      if (a > off) node = node.splitText(a - off);
      if (b < off + len) node.splitText(b - a);
      const mk = h("mark.note-hl" + (note.status === "resolved" ? ".resolved" : ""), { dataset: { note: note.id }, title: note.text || "" });
      node.parentNode.insertBefore(mk, node);
      mk.append(node);
    }
    const last = PL.$$(`mark[data-note="${note.id}"]`, root).pop();
    if (last && n) last.after(h("sup.note-ref", { dataset: { note: note.id } }, String(n)));
    return true;
  };

  /** The text selected inside one AI answer → {messageId, quote, prefix, suffix, rect} or null. */
  T.selectionInAnswer = function () {
    const sel = W.getSelection && W.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const range = sel.getRangeAt(0);
    const start = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    const prose = start && start.closest(".msg.ai .prose");
    const msg = prose && prose.closest(".msg.ai");
    if (!prose || !msg || !msg.dataset.id || !prose.contains(range.endContainer)) return null;
    const quote = sel.toString().replace(/\s+/g, " ").trim();
    if (quote.length < 2) return null;
    const pre = D.createRange();
    pre.selectNodeContents(prose);
    pre.setEnd(range.startContainer, range.startOffset);
    const before = pre.toString();
    return { messageId: msg.dataset.id, quote: sel.toString().slice(0, 2000), prefix: before.slice(-60), rect: range.getBoundingClientRect() };
  };
})(window);
