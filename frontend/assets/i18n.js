/* PhD Research Lab — interface language. Vietnamese is the source language of the UI strings: PL.t("Đã lưu {0}", x)
   returns the English entry of PL.EN when the interface is English (Settings → Appearance & language), the Vietnamese
   text otherwise; {0}, {1} … are filled from the arguments. Static markup uses data-t / data-t-title /
   data-t-placeholder / data-t-aria (applied by PL.applyStatic). Loaded before every other script. */
(function (W) {
  "use strict";
  const PL = (W.PL = W.PL || {});
  let lang = "vi";
  try { lang = W.localStorage.getItem("pl.lang") === "en" ? "en" : "vi"; } catch (e) { /* private mode */ }
  PL.lang = lang;
  PL.EN = PL.EN || {};
  PL.t = function (vi, ...args) {
    const s = (PL.lang === "en" && PL.EN[vi]) || vi;
    return args.length ? s.replace(/\{(\d+)\}/g, (m, i) => (args[+i] == null ? "" : String(args[+i]))) : s;
  };
  PL.applyStatic = function (root) {
    const D = W.document;
    D.documentElement.lang = PL.lang;
    (root || D).querySelectorAll("[data-t]").forEach((el) => { el.textContent = PL.t(el.dataset.t); });
    for (const [attr, key] of [["title", "tTitle"], ["placeholder", "tPlaceholder"], ["aria-label", "tAria"]]) {
      (root || D).querySelectorAll(`[data-${key.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase())}]`).forEach((el) => el.setAttribute(attr, PL.t(el.dataset[key])));
    }
  };
  /** Switch the language: remembered locally (first paint) and in the settings (the agents' answer language). */
  PL.setLang = function (v) {
    try { W.localStorage.setItem("pl.lang", v === "en" ? "en" : "vi"); } catch (e) { /* private mode */ }
    W.location.reload();
  };
  PL.setFont = function (v) {
    W.document.documentElement.dataset.font = v === "serif" ? "serif" : "sans";
    try { W.localStorage.setItem("pl.font", v === "serif" ? "serif" : "sans"); } catch (e) { /* private mode */ }
  };
})(window);
