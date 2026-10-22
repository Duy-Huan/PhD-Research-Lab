/* Adjustable workspace proportions and the compact function menu. */
(function (W) {
  "use strict";
  const PL = W.PL, D = W.document, L = PL.layout = {};
  const defaults = { side: 0.20, panel: 0.36 };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  L.init = function () {
    const app = PL.$("#app"), menu = PL.$("#nav-popup"), toggle = PL.$("#nav-toggle");
    const saved = PL.store.get("layout", {}), ratios = { ...defaults };
    for (const key of ["side", "panel"]) if (Number.isFinite(saved[key]) && saved[key] > 0) ratios[key] = saved[key];
    let drag = null;
    const narrow = () => W.innerWidth <= 820;
    const bounds = (key) => key === "side" ? [220, Math.max(220, Math.min(420, W.innerWidth * 0.4))] :
      [260, Math.max(260, Math.min(720, W.innerWidth - (W.innerWidth > 1100 ? (app.classList.contains("side-collapsed") ? 0 : clamp(W.innerWidth * ratios.side, 220, 420)) + 340 : 40)))];
    const paint = () => {
      for (const key of ["side", "panel"]) {
        const [lo, hi] = bounds(key), width = Math.round(clamp(W.innerWidth * ratios[key], lo, hi));
        app.style.setProperty("--" + key + "-w", width + "px");
        const grip = PL.$("#" + key + "-resize");
        grip.setAttribute("aria-valuemin", lo); grip.setAttribute("aria-valuemax", Math.round(hi)); grip.setAttribute("aria-valuenow", width);
      }
    };
    const finish = (cancel) => {
      if (!drag) return;
      if (cancel) ratios[drag.key] = drag.original;
      else PL.store.set("layout", ratios);
      drag = null; app.classList.remove("layout-dragging"); paint();
    };
    for (const key of ["side", "panel"]) {
      const grip = PL.$("#" + key + "-resize");
      grip.addEventListener("pointerdown", (e) => {
        if (e.button !== 0 || narrow()) return;
        e.preventDefault();
        drag = { key, id: e.pointerId, x: e.clientX, width: Number(grip.getAttribute("aria-valuenow")), original: ratios[key] };
        if (grip.setPointerCapture) grip.setPointerCapture(e.pointerId);
        app.classList.add("layout-dragging");
      });
      const reset = () => { finish(true); ratios[key] = defaults[key]; PL.store.set("layout", ratios); paint(); };
      grip.addEventListener("dblclick", reset);
      grip.addEventListener("keydown", (e) => {
        if (narrow()) return;
        if (e.key === "Enter") { reset(); return; }
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
        e.preventDefault();
        const [lo, hi] = bounds(key), width = Number(grip.getAttribute("aria-valuenow"));
        const next = e.key === "Home" ? lo : e.key === "End" ? hi : width + (e.key === "ArrowRight" ? 1 : -1) * (key === "side" ? 1 : -1) * 24;
        ratios[key] = clamp(next, lo, hi) / W.innerWidth; PL.store.set("layout", ratios); paint();
      });
    }
    D.addEventListener("pointermove", (e) => {
      if (!drag || e.pointerId !== drag.id) return;
      const [lo, hi] = bounds(drag.key);
      ratios[drag.key] = clamp(drag.width + (e.clientX - drag.x) * (drag.key === "side" ? 1 : -1), lo, hi) / W.innerWidth;
      paint();
    });
    D.addEventListener("pointerup", (e) => { if (drag && e.pointerId === drag.id) finish(false); });
    D.addEventListener("pointercancel", () => finish(true));
    W.addEventListener("blur", () => finish(true));
    W.addEventListener("resize", () => { finish(true); paint(); L.closeMenu(); });
    L.closeMenu = () => { menu.hidden = true; toggle.setAttribute("aria-expanded", "false"); };
    toggle.onclick = () => {
      menu.hidden = !menu.hidden; toggle.setAttribute("aria-expanded", String(!menu.hidden));
      if (!menu.hidden) menu.querySelector("button").focus();
    };
    D.addEventListener("pointerdown", (e) => { D.body.dataset.keyboardNavigation = "false"; if (!menu.contains(e.target) && !toggle.contains(e.target)) L.closeMenu(); });
    D.addEventListener("keydown", (e) => {
      if (e.key === "Tab") D.body.dataset.keyboardNavigation = "true";
      if (e.key === "Escape") {
        finish(true);
        if (!menu.hidden) { L.closeMenu(); toggle.focus(); }
      }
    });
    menu.addEventListener("keydown", (e) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const items = Array.from(menu.querySelectorAll("button")), i = items.indexOf(D.activeElement);
      items[e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    });
    paint();
  };
})(window);
