/* First paint, before CSS. Keep this small and independent of the application namespace. */
(function (W) {
  "use strict";
  try {
    const root = W.document.documentElement;
    const theme = W.localStorage.getItem("pl.theme");
    const font = W.localStorage.getItem("pl.font");
    const language = W.localStorage.getItem("pl.lang");
    if (theme === "light" || theme === "dark") root.dataset.theme = theme;
    root.dataset.font = font === "serif" ? "serif" : "sans";
    if (language === "en") root.lang = "en";
  } catch (e) { /* Browser storage can be unavailable in private/restricted contexts. */ }
})(window);
