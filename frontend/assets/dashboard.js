/* PhD Research Lab — "Theo dõi": the minimal tracking dashboard. By default only what the researcher needs (current
   goal, current step + provider, status, pinned results, next decision); everything technical sits under
   "Chi tiết nâng cao" (resources, GPU, models in VRAM, providers, acceptance evidence, research state). */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  let off = null;

  PL.route("dashboard", async function () {
    PL.leaveChat();
    PL.setTitle(PL.t("Theo dõi"), "");
    PL.activeNav("dashboard");
    const v = PL.$("#view");
    v.innerHTML = "";
    const inner = h("div.page-in", {}, h("span.spin"));
    v.append(h("div.page", {}, inner));
    const paint = async () => {
      const d = await PL.get("/api/dashboard").catch((e) => ({ error: e.message }));
      if (d.error) { inner.innerHTML = ""; inner.append(h("p.err-line", {}, d.error)); return; }
      inner.innerHTML = "";
      inner.append(h("h1", {}, d.project), h("p.lead", {}, PL.t("Tiến độ nghiên cứu — chi tiết kỹ thuật nằm trong mục nâng cao.")));
      const cur = d.current;
      inner.append(h("div.tiles", {},
        tile(PL.t("Mục tiêu"), h("div.v.big", {}, d.goal || PL.t("Chưa có — bắt đầu bằng /outline")), () => PL.panels.outline(),
          h("div.muted", { style: "font-size:12px;margin-top:6px" }, PL.t("Đề cương cấp {0}/5{1}", d.outline_level, d.outline_label ? " · " + PL.t(d.outline_label) : ""))),
        tile(PL.t("Bước hiện tại"), cur ? h("div.v", {}, h("div", {}, cur.step || cur.title), h("div.muted", { style: "font-size:12.5px" }, `${cur.provider || ""} · ${cur.progress}`)) : h("div.v.muted", {}, PL.t("Không có run nào đang chạy")),
          cur ? () => PL.panels.run(cur.run) : null),
        tile(PL.t("Trạng thái"), h("div.v", {}, h("span.chip" + ({ running: ".info", "waiting approval": ".warn", idle: "" }[d.status] || ""), {},
          { running: PL.t("đang chạy"), "waiting approval": PL.t("chờ bạn duyệt"), idle: PL.t("rảnh") }[d.status] || d.status))),
        tile(PL.t("Quyết định tiếp theo"), h("div.v", {}, d.next_decision || h("span.muted", {}, PL.t("Không có gì cần bạn quyết định"))))));

      if (d.pending.length) {
        inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Cần bạn duyệt ({0})", d.pending.length)),
          h("div.list", {}, d.pending.map((p) => h("div.li", { style: "cursor:pointer", onclick: () => openPending(p) },
            h("span.dot.warn"), h("div.m", {}, h("div.t", {}, PL.ACTION[p.title] || p.title), h("div.s", {}, p.text || "")),
            p.kind === "run" ? PL.statusChip(p.status) : h("span.chip", {}, { approval: PL.t("đề xuất"), memory: PL.t("bộ nhớ") }[p.kind] || p.kind))))));
      }
      inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Kết quả đã ghim")),
        d.pins.length ? h("div.list", {}, d.pins.map(pinRow)) : h("p.muted", {}, PL.t("Chưa có. Kết quả của run và câu trả lời quan trọng có thể ghim từ chat."))));
      if (d.recent_runs.length) {
        const t = h("table.grid", {}, h("tr", {}, h("th", {}, "Run"), h("th", {}, PL.t("Trạng thái")), h("th", {}, PL.t("Tiến độ")), h("th", {}, PL.t("Cập nhật"))));
        d.recent_runs.forEach((r) => t.append(h("tr", { style: "cursor:pointer", onclick: () => PL.panels.run(r.id) },
          h("td", {}, r.title, r.synthetic ? h("span.chip.warn", { style: "margin-left:6px" }, "SYNTHETIC") : null), h("td", {}, PL.statusChip(r.status)),
          h("td", {}, `${r.done}/${r.steps}`), h("td.muted", {}, PL.ago(r.updated)))));
        inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Run gần đây")), t));
      }
      for (const r of d.compute_runs || []) {
        inner.append(h("div.panelbox", {}, h("div.row", {}, h("b.grow", {}, r.experiment_id), PL.statusChip(r.status)),
          h("p.muted", {}, `${r.compute_target} · ${r.run_id} · ${r.hypothesis_id || "—"}`),
          h("div.row.wrap", {},
            r.status === "awaiting_approval" ? h("button.btn.sm", { type: "button", onclick: async () => {
              if (await PL.confirm(`Bundle ${r.bundle_sha256}\n${r.files.map((f) => f.path).join("\n")}`, "Duyệt bundle")) { await PL.safe(() => PL.post(`/api/compute/runs/${r.run_id}/approve`, {})); paint(); }
            } }, "Duyệt bundle") : h("a.btn.sm", { href: `/api/compute/runs/${r.run_id}/bundle`, download: r.run_id + ".zip" }, "Experiment bundle"),
            h("button.btn.sm.ghost", { type: "button", onclick: async () => {
              const task = r.clearml_task_id || await PL.prompt("ClearML task", "Task ID thực tế (General/run_id phải khớp)", "");
              if (task) { await PL.safe(() => PL.post(`/api/compute/runs/${r.run_id}/sync`, { task_id: task, collect: true })); paint(); }
            } }, "Thu kết quả"),
            r.clearml_url ? h("a.btn.sm.ghost", { href: r.clearml_url, target: "_blank", rel: "noopener" }, "Open in ClearML ↗") : null)));
      }
      const adv = h("details.adv", { ontoggle: (e) => { if (e.target.open && !adv._done) { adv._done = true; advanced(adv); } } }, h("summary", {}, PL.t("Trạng thái hệ thống — tài nguyên, GPU, mô hình trong VRAM, providers")));
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
      h("span.chip" + (p.status === "verified" ? ".ok" : p.status === "approved" ? ".info" : ""), {}, { pinned: PL.t("đã ghim"), approved: PL.t("đã duyệt"), verified: PL.t("đã kiểm chứng") }[p.status] || p.status),
      h("button.icon", { type: "button", title: PL.t("Tuỳ chọn"), html: PL.icon("dots"), onclick: (e) => PL.menu(e.currentTarget, [
        { label: PL.t("Đánh dấu đã duyệt"), run: () => PL.safe(() => PL.put("/api/pins/" + p.id, { status: "approved" }), PL.t("Đã duyệt")) },
        { label: PL.t("Đánh dấu đã kiểm chứng (cần run đo được)"), run: () => PL.safe(() => PL.put("/api/pins/" + p.id, { status: "verified" }), PL.t("Đã kiểm chứng")) },
        { label: PL.t("Bỏ ghim"), danger: true, run: () => PL.safe(() => PL.del("/api/pins/" + p.id), PL.t("Đã bỏ ghim")) },
      ]) }));
  }

  async function memoryList() {
    const body = PL.panels.open(PL.t("Đề xuất ghi nhớ"), h("span.spin"));
    const r = await PL.get("/api/memory/candidates?status=pending").catch(() => ({ candidates: [] }));
    body.innerHTML = "";
    if (!r.candidates.length) body.append(h("p.muted", {}, PL.t("Không có đề xuất nào.")));
    for (const c of r.candidates) {
      const row = h("div.card.pending", {}, h("div.card-b", {}, (c.payload || {}).text || ""),
        h("div.card-f", {}, h("span.spacer"),
          h("button.btn.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${c.id}/reject`, {})); row.remove(); } }, PL.t("Bỏ qua")),
          h("button.btn.accent.sm", { type: "button", onclick: async () => { await PL.safe(() => PL.post(`/api/memory/candidates/${c.id}/approve`, {}), PL.t("Đã lưu")); row.remove(); } }, PL.t("Chấp nhận"))));
      body.append(row);
    }
  }

  async function advanced(box) {
    const inner = h("div", {}, h("span.spin"));
    box.append(inner);
    const [d, st] = await Promise.all([PL.get("/api/dashboard?advanced=1").catch(() => ({})), PL.get("/api/research").catch(() => null)]);
    inner.innerHTML = "";
    const res = d.resources || {};
    const t = h("table.grid", {}, h("tr", {}, h("th", {}, PL.t("Tài nguyên")), h("th", {}, "Slot"), h("th", {}, PL.t("Đang dùng bởi"))));
    for (const [k, v] of Object.entries(res)) t.append(h("tr", {}, h("td", {}, k), h("td", {}, v.capacity), h("td.mono", {}, v.held_by.join(", ") || "—")));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Guard phần cứng (mỗi lúc 1 job GPU)")), t));
    const gp = (d.gpus || []).map((g) => h("div", { style: "margin:6px 0" }, h("div.row", {}, h("span.grow", {}, g.name || "GPU"),
      h("span.muted", {}, `${Math.round(g.vram_used_mb || 0)} / ${Math.round(g.vram_total_mb || 0)} MB · ${Math.round(g.util_pct || 0)}% · ${g.temp_c == null ? "?" : Math.round(g.temp_c)}°C`)),
    h("div.bar-meter", {}, h("i", { style: `width:${Math.min(100, Math.round(100 * (g.vram_used_mb || 0) / (g.vram_total_mb || 1)))}%` }))));
    const lm = d.local_models || {};
    const resident = [].concat(...Object.entries(lm).filter(([, v]) => Array.isArray(v)).map(([e, v]) => v.map((m) => `${e}: ${m}`)));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("GPU & mô hình trong VRAM")),
      gp.length ? gp : h("p.muted", {}, PL.t("Không đọc được GPU (nvidia-smi).")),
      h("div.row", { style: "margin-top:8px" }, h("span.grow.muted", {}, resident.length ? "Trong VRAM: " + resident.join(", ") : PL.t("Không có mô hình local nào trong VRAM")),
        h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/unload", { engine: "all" }), PL.t("Đã giải phóng VRAM")) }, PL.t("Unload tất cả")))));
    const pv = h("div.list", {}, (d.providers || []).map((p) => h("div.li", {}, h("span.dot." + (p.ready ? "ok" : p.state === "NOT_CONFIGURED" ? "warn" : "")),
      h("div.m", {}, h("div.t", {}, `${p.label}`), h("div.s", {}, `${p.category} · ${p.state} — ${p.detail}`)))));
    inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, "Research providers"), pv));
    if (st) {
      inner.append(h("div.panelbox", {}, h("div.section-h", { style: "margin-top:10px" }, PL.t("Trạng thái nghiên cứu")),
        h("div.row", { style: "flex-wrap:wrap" }, h("span.chip", {}, st.decisions.length + PL.t(" quyết định")), h("span.chip", {}, st.hypotheses.length + PL.t(" giả thuyết")),
          h("span.chip", {}, st.experiments.length + PL.t(" thí nghiệm")), h("span.chip", {}, st.failures.length + PL.t(" hướng thất bại")),
          h("button.btn.sm", { type: "button", onclick: memoryList }, PL.t("Đề xuất ghi nhớ đang chờ")))));
    }
  }
})(window);
