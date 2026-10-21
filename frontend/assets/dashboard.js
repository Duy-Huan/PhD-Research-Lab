/* PhD Research Lab — "Theo dõi": the minimal tracking dashboard. By default only what the researcher needs (current
   goal, current step + provider, status, pinned results, next decision); everything technical sits under
   "Chi tiết nâng cao" (resources, GPU, models in VRAM, providers, acceptance evidence, research state). */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  let off = null;

  PL.route("dashboard", async function () {
    if (PL.chat.sse) { PL.chat.sse.close(); PL.chat.sse = null; }
    PL.chat.sid = null;
    PL.setTitle("Theo dõi", "");
    PL.activeNav("dashboard");
    const v = PL.$("#view");
    v.innerHTML = "";
    const inner = h("div.page-in", {}, h("span.spin"));
    v.append(h("div.page", {}, inner));
    const paint = async () => {
      const d = await PL.get("/api/dashboard").catch((e) => ({ error: e.message }));
      if (d.error) { inner.innerHTML = ""; inner.append(h("p.err-line", {}, d.error)); return; }
      inner.innerHTML = "";
      inner.append(h("h1", {}, d.project), h("p.lead", {}, "Tiến độ nghiên cứu — chi tiết kỹ thuật nằm trong mục nâng cao."));
      const cur = d.current;
      inner.append(h("div.tiles", {},
        tile("Mục tiêu", h("div.v.big", {}, d.goal || "Chưa có — bắt đầu bằng /outline"), () => PL.panels.outline(),
          h("div.muted", { style: "font-size:12px;margin-top:6px" }, `Đề cương cấp ${d.outline_level}/5${d.outline_label ? " · " + d.outline_label : ""}`)),
        tile("Bước hiện tại", cur ? h("div.v", {}, h("div", {}, cur.step || cur.title), h("div.muted", { style: "font-size:12.5px" }, `${cur.provider || ""} · ${cur.progress}`)) : h("div.v.muted", {}, "Không có run nào đang chạy"),
          cur ? () => PL.panels.run(cur.run) : null),
        tile("Trạng thái", h("div.v", {}, h("span.chip" + ({ running: ".info", "waiting approval": ".warn", idle: "" }[d.status] || ""), {},
          { running: "đang chạy", "waiting approval": "chờ bạn duyệt", idle: "rảnh" }[d.status] || d.status))),
        tile("Quyết định tiếp theo", h("div.v", {}, d.next_decision || h("span.muted", {}, "Không có gì cần bạn quyết định")))));

      if (d.pending.length) {
        inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, `Cần bạn duyệt (${d.pending.length})`),
          h("div.list", {}, d.pending.map((p) => h("div.li", { style: "cursor:pointer", onclick: () => openPending(p) },
            h("span.dot.warn"), h("div.m", {}, h("div.t", {}, PL.ACTION[p.title] || p.title), h("div.s", {}, p.text || "")),
            p.kind === "run" ? PL.statusChip(p.status) : h("span.chip", {}, { approval: "đề xuất", memory: "bộ nhớ" }[p.kind] || p.kind))))));
      }
      inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Kết quả đã ghim"),
        d.pins.length ? h("div.list", {}, d.pins.map(pinRow)) : h("p.muted", {}, "Chưa có. Kết quả của run và câu trả lời quan trọng có thể ghim từ chat.")));
      if (d.recent_runs.length) {
        const t = h("table.grid", {}, h("tr", {}, h("th", {}, "Run"), h("th", {}, "Trạng thái"), h("th", {}, "Tiến độ"), h("th", {}, "Cập nhật")));
        d.recent_runs.forEach((r) => t.append(h("tr", { style: "cursor:pointer", onclick: () => PL.panels.run(r.id) },
          h("td", {}, r.title, r.synthetic ? h("span.chip.warn", { style: "margin-left:6px" }, "SYNTHETIC") : null), h("td", {}, PL.statusChip(r.status)),
          h("td", {}, `${r.done}/${r.steps}`), h("td.muted", {}, PL.ago(r.updated)))));
        inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Run gần đây"), t));
      }
      const adv = h("details.adv", { ontoggle: (e) => { if (e.target.open && !adv._done) { adv._done = true; advanced(adv); } } }, h("summary", {}, "Chi tiết nâng cao — tài nguyên, GPU, mô hình trong VRAM, providers, nghiệm thu"));
      inner.append(adv);
      PL.paintPending(d.pending.length);
    };
    await paint();
    if (off) off();
    const offs = [PL.on("run.", () => schedule()), PL.on("aiws.", () => schedule()), PL.on("outline.", () => schedule())];
    let t = 0;
    function schedule() { if (!PL.$(".page")) { offs.forEach((f) => f()); return; } W.clearTimeout(t); t = W.setTimeout(paint, 500); }
    off = () => offs.forEach((f) => f());
  });

  function tile(k, v, onclick, extra) {
    return h("div.tile", onclick ? { style: "cursor:pointer", onclick, role: "button", tabindex: "0" } : {}, h("div.k", {}, k), v, extra || null);
  }
  function openPending(p) {
    if (p.kind === "run") PL.panels.run(p.id);
    else if (p.session_id) PL.go("#/chat/" + p.session_id);
    else memoryList();
  }
  function pinRow(p) {
    return h("div.li", {}, h("span", { html: PL.icon("pin") }),
      h("div.m", {}, h("div.t", {}, p.title), h("div.s", {}, `${p.kind} · ${p.body.slice(0, 140)}`)),
      h("span.chip" + (p.status === "verified" ? ".ok" : p.status === "approved" ? ".info" : ""), {}, { pinned: "đã ghim", approved: "đã duyệt", verified: "đã kiểm chứng" }[p.status] || p.status),
      h("button.icon", { type: "button", title: "Tuỳ chọn", html: PL.icon("dots"), onclick: (e) => PL.menu(e.currentTarget, [
        { label: "Đánh dấu đã duyệt", run: () => PL.safe(() => PL.put("/api/pins/" + p.id, { status: "approved" }), "Đã duyệt") },
        { label: "Đánh dấu đã kiểm chứng (cần run đo được)", run: () => PL.safe(() => PL.put("/api/pins/" + p.id, { status: "verified" }), "Đã kiểm chứng") },
        { label: "Bỏ ghim", danger: true, run: () => PL.safe(() => PL.del("/api/pins/" + p.id), "Đã bỏ ghim") },
      ]) }));
  }

  async function memoryList() {
    const body = PL.panels.open("Đề xuất ghi nhớ", h("span.spin"));
    const r = await PL.get("/api/memory/candidates?status=pending").catch(() => ({ candidates: [] }));
    body.innerHTML = "";
    if (!r.candidates.length) body.append(h("p.muted", {}, "Không có đề xuất nào."));
    for (const c of r.candidates) {
      const row = h("div.card.pending", {}, h("div.card-b", {}, (c.payload || {}).text || ""),
        h("div.card-f", {}, h("span.spacer"),
          h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${c.id}/reject`, {})); row.remove(); } }, "Bỏ qua"),
          h("button.btn.accent.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${c.id}/approve`, {}), "Đã lưu"); row.remove(); } }, "Chấp nhận")));
      body.append(row);
    }
  }

  async function advanced(box) {
    const inner = h("div", {}, h("span.spin"));
    box.append(inner);
    const [d, acc, st] = await Promise.all([PL.get("/api/dashboard?advanced=1").catch(() => ({})), PL.get("/api/acceptance").catch(() => null),
      PL.get("/api/research").catch(() => null)]);
    inner.innerHTML = "";
    const res = d.resources || {};
    const t = h("table.grid", {}, h("tr", {}, h("th", {}, "Tài nguyên"), h("th", {}, "Slot"), h("th", {}, "Đang dùng bởi")));
    for (const [k, v] of Object.entries(res)) t.append(h("tr", {}, h("td", {}, k), h("td", {}, v.capacity), h("td.mono", {}, v.held_by.join(", ") || "—")));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Guard phần cứng (mỗi lúc 1 job GPU)"), t));
    const gp = (d.gpus || []).map((g) => h("div", { style: "margin:6px 0" }, h("div.row", {}, h("span.grow", {}, g.name || "GPU"),
      h("span.muted", {}, `${Math.round(g.vram_used_mb || 0)} / ${Math.round(g.vram_total_mb || 0)} MB · ${Math.round(g.util_pct || 0)}% · ${g.temp_c == null ? "?" : Math.round(g.temp_c)}°C`)),
    h("div.bar-meter", {}, h("i", { style: `width:${Math.min(100, Math.round(100 * (g.vram_used_mb || 0) / (g.vram_total_mb || 1)))}%` }))));
    const lm = d.local_models || {};
    const resident = [].concat(...Object.entries(lm).filter(([, v]) => Array.isArray(v)).map(([e, v]) => v.map((m) => `${e}: ${m}`)));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "GPU & mô hình trong VRAM"),
      gp.length ? gp : h("p.muted", {}, "Không đọc được GPU (nvidia-smi)."),
      h("div.row", { style: "margin-top:8px" }, h("span.grow.muted", {}, resident.length ? "Trong VRAM: " + resident.join(", ") : "Không có mô hình local nào trong VRAM"),
        h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/unload", { engine: "all" }), "Đã giải phóng VRAM") }, "Unload tất cả"))));
    const pv = h("div.list", {}, (d.providers || []).map((p) => h("div.li", {}, h("span.dot." + (p.ready ? "ok" : p.state === "NOT_CONFIGURED" ? "warn" : "")),
      h("div.m", {}, h("div.t", {}, `${p.label}`), h("div.s", {}, `${p.category} · ${p.state} — ${p.detail}`)))));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Research providers"), pv));
    if (acc) {
      const at = h("table.grid", {}, h("tr", {}, h("th", {}, ""), h("th", {}, "Tiêu chí nghiệm thu"), h("th", {}, "Kết luận"), h("th", {}, "Bằng chứng")));
      acc.criteria.forEach((c) => at.append(h("tr", {}, h("td", {}, c.priority), h("td", {}, c.title),
        h("td", {}, h("span.chip" + (c.verdict === "PASS" ? ".ok" : c.verdict === "FAIL" ? ".err" : ".warn"), {}, c.verdict)), h("td.muted", { style: "font-size:12px" }, c.evidence))));
      inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Nghiệm thu AI Research OS" + (acc.generated ? " · " + acc.generated : "")), at,
        h("details", { style: "margin-top:8px" }, h("summary.muted", {}, "Còn thiếu gì để chạy 90 ngày thật"), h("ul", {}, (acc.gaps || []).map((g) => h("li", {}, g))))));
    }
    if (st) {
      inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Trạng thái nghiên cứu"),
        h("div.row", { style: "flex-wrap:wrap" }, h("span.chip", {}, st.decisions.length + " quyết định"), h("span.chip", {}, st.hypotheses.length + " giả thuyết"),
          h("span.chip", {}, st.experiments.length + " thí nghiệm"), h("span.chip", {}, st.failures.length + " hướng thất bại"),
          h("button.btn.sm", { type: "button", onclick: memoryList }, "Đề xuất ghi nhớ đang chờ"))));
    }
  }
})(window);
