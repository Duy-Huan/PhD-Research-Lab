/* PhD Research Lab — Settings: everything technical lives here so the chat stays simple.
   Models & agents · Research providers · Experiments & hardware · Memory · Skills · Appearance. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const S = (PL.settings = {});
  const TABS = [["models", "Mô hình & agent"], ["providers", "Research providers"], ["hardware", "Thí nghiệm & phần cứng"],
    ["memory", "Bộ nhớ & ngữ cảnh"], ["skills", "Kỹ năng (/)"], ["look", "Giao diện"]];
  let cfg = null;

  S.open = async function (tab) {
    cfg = await PL.get("/api/config").catch((e) => { PL.toast(e.message, "err"); return null; });
    if (!cfg) return;
    const nav = h("nav");
    const body = h("div.sb");
    const show = (k) => {
      PL.$$(".nav", nav).forEach((b) => b.classList.toggle("active", b.dataset.k === k));
      body.innerHTML = "";
      ({ models, providers, hardware, memory, skills, look })[k](body);
    };
    for (const [k, label] of TABS) nav.append(h("button.nav", { type: "button", dataset: { k }, onclick: () => show(k) }, label));
    PL.modal({ title: "Cài đặt", wide: true, raw: true, body: h("div.settings", {}, nav, body) });
    show(tab || "models");
  };

  const save = (patch, msg) => PL.safe(async () => { cfg = await PL.post("/api/config", patch); return cfg; }, msg || "Đã lưu");
  const field = (label, el, help) => h("label.field", {}, h("span", {}, label), el, help ? h("small.muted", {}, help) : null);
  const sel = (opts, value, onchange) => h("select.input", { onchange: (e) => onchange(e.target.value) },
    opts.map(([v, l]) => h("option", { value: v, selected: String(v) === String(value) || null }, l)));
  const toggle = (label, value, onchange, help) => h("div.field", {}, h("label.switch", {}, h("input", { type: "checkbox", checked: value || null, onchange: (e) => onchange(e.target.checked) }), label),
    help ? h("small.muted", {}, help) : null);
  const num = (value, onchange, attrs) => h("input.input", Object.assign({ type: "number", value, onchange: (e) => onchange(Number(e.target.value)) }, attrs));

  // ------------------------------------------------------------------ models & agents
  async function models(b) {
    b.append(h("h3", {}, "Hai agent + một tiện ích chạy nền"),
      h("p.help", {}, "Research agent điều phối mọi việc (nghiên cứu, thiết kế, code, viết bài); Reviewer agent phản biện và kiểm chứng. Kỹ năng (/) quyết định agent làm gì — không cần một agent cho mỗi công cụ."));
    const engines = [["auto", "Tự động (local → cloud)"], ["claude", "Claude (nếu có key)"], ["cloud", "Cloud mặc định"], ["local", "LM Studio (local)"], ["ollama", "Ollama (local)"]]
      .concat(Object.entries(cfg.provider_specs).map(([k, v]) => [k, v.label]));
    const t = h("table.grid", {}, h("tr", {}, h("th", {}, "Agent"), h("th", {}, "Engine"), h("th", {}, "Model (tuỳ chọn)")));
    for (const [a, spec] of Object.entries(cfg.agents)) {
      t.append(h("tr", {}, h("td", {}, h("b", {}, a), h("div.muted", { style: "font-size:12px" }, spec.label)),
        h("td", {}, sel(engines, cfg.agent_modes[a], (v) => save({ agent_modes: { [a]: v } }))),
        h("td", {}, h("input.input", { value: (cfg.agent_models || {})[a] || "", placeholder: "mặc định của engine", onchange: (e) => save({ agent_models: { [a]: e.target.value } }) }))));
    }
    b.append(t);
    b.append(h("h3", {}, "Cloud API"), h("p.help", {}, "Key chỉ được gửi tới máy chủ của chính nhà cung cấp đó; giao diện không bao giờ hiển thị lại key."));
    b.append(field("Cloud mặc định", sel(Object.entries(cfg.provider_specs).map(([k, v]) => [k, v.label]), cfg.default_cloud, (v) => save({ default_cloud: v }))));
    const keys = h("table.grid", {}, h("tr", {}, h("th", {}, "Nhà cung cấp"), h("th", {}, "API key"), h("th", {}, "Model"), h("th", {}, "")));
    const more = h("table.grid");
    const specs = Object.entries(cfg.provider_specs);
    const main = new Set(["anthropic", "openai", "gemini", "deepseek", cfg.default_cloud]);
    for (const [pid, spec] of specs) {
      const p = cfg.providers[pid] || {};
      const table = p.has_key || main.has(pid) ? keys : more;
      const key = h("input.input", { type: "password", placeholder: p.has_key ? "•••••• (đã lưu)" : "chưa có", autocomplete: "off" });
      const model = h("input.input", { value: p.model || "", list: "ml-" + pid });
      table.append(h("tr", {}, h("td", {}, spec.label), h("td", {}, key), h("td", {}, model, h("datalist", { id: "ml-" + pid }, (spec.models || []).map((m) => h("option", { value: m })))),
        h("td", {}, h("div.row", {}, h("button.btn.sm", { type: "button", onclick: () => {
          const patch = { model: model.value };
          if (key.value) patch.api_key = key.value;
          save({ providers: { [pid]: patch } }).then(() => { key.value = ""; PL.chat.loadModels(); });
        } }, "Lưu"), h("button.btn.sm.ghost", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/test", { provider: pid }).then((r) => PL.toast(`OK · ${r.model}: ${r.reply}`))) }, "Thử")))));
    }
    b.append(keys, h("details", { style: "margin-top:8px" }, h("summary.muted", { style: "cursor:pointer;font-size:13px" }, `Nhà cung cấp khác (${more.childNodes.length})`), more));
    b.append(h("h3", {}, "Mô hình trên máy (VRAM)"));
    const st = h("div.muted", {}, h("span.spin"));
    b.append(h("div.grid2", {}, field("LM Studio URL", h("input.input", { value: cfg.lmstudio_base_url, onchange: (e) => save({ lmstudio_base_url: e.target.value }) })),
      field("Model LM Studio", h("input.input", { value: cfg.local_model, onchange: (e) => save({ local_model: e.target.value }) })),
      field("Ollama URL", h("input.input", { value: cfg.ollama_base_url, onchange: (e) => save({ ollama_base_url: e.target.value }) })),
      field("Model Ollama", h("input.input", { value: cfg.ollama_model, onchange: (e) => save({ ollama_model: e.target.value }) }))), st);
    b.append(toggle("Gỡ mô hình local khỏi VRAM khi tắt PhD Lab", cfg.lifecycle.unload_on_exit, (v) => save({ lifecycle: { unload_on_exit: v } })),
      field("Tự gỡ mô hình khi rảnh sau (phút)", num(cfg.lifecycle.local_idle_min, (v) => save({ lifecycle: { local_idle_min: v } }), { min: 1, max: 240 }),
        "Tác vụ nền (tóm tắt, trích xuất) luôn: nạp → chạy → gỡ ngay."));
    PL.get("/api/models/local").then((r) => {
      st.innerHTML = "";
      const lm = r.lmstudio || {}, ol = r.ollama || {};
      const loaded = [].concat((lm.loaded || []).map((m) => "LM Studio: " + m), (ol.loaded || []).map((m) => "Ollama: " + (m.id || m)));
      st.append(h("div.row", {}, h("span.dot." + (lm.online ? "ok" : "")), "LM Studio", h("span.dot." + (ol.online ? "ok" : "")), "Ollama",
        h("span.grow", {}, loaded.length ? " · Trong VRAM: " + loaded.join(", ") : " · VRAM trống"),
        h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/unload", { engine: "all" }), "Đã gỡ mô hình khỏi VRAM") }, "Unload tất cả")));
    }).catch(() => { st.textContent = "Không đọc được trạng thái local."; });
  }

  // ------------------------------------------------------------------ research providers
  async function providers(b) {
    b.append(h("h3", {}, "Research providers chạy song song"),
      h("p.help", {}, "PhD Lab giữ trạng thái nghiên cứu; mỗi provider chỉ nhận một nhiệm vụ có phạm vi rõ trong workspace riêng. Provider chưa sẵn sàng được báo trung thực và tác vụ dùng mô hình của ứng dụng."));
    const list = h("div.list", {}, h("span.spin"));
    b.append(list);
    const r = await PL.get("/api/providers?fresh=1").catch(() => ({ providers: [] }));
    list.innerHTML = "";
    const cat = { research: "Nghiên cứu", coding: "Code", experiment: "Thí nghiệm", publication: "Xuất bản" };
    for (const p of r.providers) {
      list.append(h("div.li", {}, h("span.dot." + (p.ready ? "ok" : ["NOT_CONFIGURED", "STOPPED"].includes(p.state) ? "warn" : "")),
        h("div.m", {}, h("div.t", {}, p.label, " ", h("span.chip", {}, cat[p.category] || p.category)), h("div.s", { style: "white-space:normal" }, `${p.state} — ${p.detail}`),
          (p.setup || []).length ? h("div.s.mono", { style: "white-space:normal" }, p.setup.join("  ·  ")) : null),
        ["feynman", "claude_code", "codex", "gemini_cli", "antigravity"].includes(p.id) && !p.ready ?
          h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post(`/api/providers/${p.id}/connect`), "Đã mở cửa sổ đăng nhập của nhà cung cấp") }, "Đăng nhập") : null));
    }
    const rp = cfg.research_providers;
    b.append(h("h3", {}, "Feynman"),
      toggle("Dùng Feynman cho /lit, /deepresearch, /compare, /review", rp.feynman_enabled, (v) => save({ research_providers: { feynman_enabled: v } })),
      toggle("Cho Feynman dùng API key Anthropic / OpenAI của ứng dụng", rp.feynman_share_app_key, (v) => save({ research_providers: { feynman_share_app_key: v } }),
        "Tắt: Feynman dùng đăng nhập riêng (`feynman model login`). Bật: chi phí tính vào tài khoản API của bạn."),
      field("Giới hạn thời gian mỗi tác vụ Feynman (giây)", num(rp.feynman_timeout_s, (v) => save({ research_providers: { feynman_timeout_s: v } }), { min: 60, max: 7200 })),
      h("h3", {}, "Code"),
      field("Coding provider mặc định cho /code", sel([["claude_code", "Claude Code"], ["codex", "OpenAI Codex"], ["gemini_cli", "Gemini CLI"], ["antigravity", "Antigravity"], ["app", "Mô hình của ứng dụng"]],
        rp.coding_default, (v) => save({ research_providers: { coding_default: v } }))));
    const ws = cfg.search || {};
    b.append(h("h3", {}, "Tìm paper & web"),
      h("p.help", {}, "Lit tìm trên OpenAlex, Semantic Scholar, arXiv và web. IEEE API và Google Scholar qua SerpAPI dùng key riêng. Kết quả không có PDF mở vẫn lưu được thông tin vào thư viện."),
      field("Công cụ tìm web", sel([["duckduckgo", "DuckDuckGo (không cần key)"], ["tavily", "Tavily"], ["brave", "Brave Search"]], ws.web_engine || "duckduckgo", (v) => save({ search: { web_engine: v } }))),
      field("Số kết quả tìm kiếm", num(ws.n_results || 12, (v) => save({ search: { n_results: v } }), { min: 1, max: 30 })),
      field("Email cho API học thuật (tuỳ chọn)", h("input.input", { type: "email", value: ws.mailto || "", onchange: (e) => save({ search: { mailto: e.target.value } }) })),
      toggle("Đọc nội dung trang web khi tìm kiếm", ws.read_pages, (v) => save({ search: { read_pages: v } })));
    const searchKeys = h("div.grid2");
    for (const [key, label] of [["tavily_key", "Tavily API key"], ["brave_key", "Brave Search API key"], ["s2_key", "Semantic Scholar API key"],
      ["openalex_key", "OpenAlex API key"], ["ieee_key", "IEEE Xplore API key"], ["serpapi_key", "SerpAPI key (Google Scholar)"]]) {
      const input = h("input.input", { type: "password", autocomplete: "off", placeholder: ws[key] || ws["has_" + key] ? "Đã lưu key · nhập để thay thế" : "Chưa cấu hình" });
      searchKeys.append(field(label, h("div.row", {}, input, h("button.btn.sm", { type: "button", onclick: async () => {
        if (!input.value.trim()) return;
        if (await save({ search: { [key]: input.value.trim() } })) input.value = "";
      } }, "Lưu key"))));
    }
    b.append(searchKeys, h("p.help", {}, "Xếp hạng hiển thị kèm nguồn và năm khi có dữ liệu. Chỉ số trích dẫn / h-index của tạp chí không được suy ra thành Q1–Q4 hoặc điểm chất lượng bài báo."));
    const rankingYear = h("input.input", { type: "number", min: 1999, max: new Date().getFullYear(), value: new Date().getFullYear() - 1, "aria-label": "Năm dữ liệu xếp hạng", style: "max-width:110px" });
    const rankingFile = h("input.input", { type: "file", accept: ".csv,text/csv", "aria-label": "File SCImago CSV" });
    const rankingStatus = h("p.muted", { role: "status" });
    const rankingImport = h("button.btn.sm", { type: "button", onclick: async () => {
      if (!rankingFile.files.length) { rankingStatus.textContent = "Chọn file CSV trước khi nhập."; return; }
      if (!rankingYear.checkValidity()) { rankingYear.reportValidity(); return; }
      const data = new W.FormData();
      data.append("file", rankingFile.files[0]); data.append("year", rankingYear.value);
      rankingImport.disabled = true; rankingStatus.textContent = "Đang nhập dữ liệu…";
      try {
        const r = await PL.api("POST", "/api/journals/import", data);
        rankingStatus.textContent = `Đã nhập ${r.records} tạp chí · ${r.year} · ${r.source}`;
      } catch (e) { rankingStatus.textContent = e.message; }
      finally { rankingImport.disabled = false; }
    } }, "Nhập bảng xếp hạng");
    b.append(h("h3", {}, "Journal ranking · SCImago"), h("p.help", {}, "Nhập CSV SCImago của năm tương ứng để hiển thị SJR và Q1–Q4. Giữ các cột Title, Issn, SJR, SJR Best Quartile, Categories, Sourceid."),
      h("div.row", { style: "flex-wrap:wrap" }, rankingFile, rankingYear, rankingImport), rankingStatus);
  }

  // ------------------------------------------------------------------ experiments & hardware
  function hardware(b) {
    const ru = cfg.runs, rs = cfg.resources;
    b.append(h("h3", {}, "Chạy ngầm & quyền"),
      h("p.help", {}, "Run viết code hoặc dùng GPU luôn chờ bạn Chấp nhận. Mức dưới đây chỉ áp dụng cho việc đọc / ghi bên trong dự án."),
      field("Tự chạy không cần hỏi", sel([[0, "Chỉ việc chỉ-đọc (tìm tài liệu, phản biện)"], [1, "Cả việc ghi trong dự án (báo cáo, PDF)"]], ru.auto_approve_risk, (v) => save({ runs: { auto_approve_risk: +v } }))),
      h("div.grid2", {}, field("Ngân sách mỗi run (phút)", num(ru.max_minutes, (v) => save({ runs: { max_minutes: v } }), { min: 1, max: 1440 })),
        field("Số lần tự phục hồi (vd OOM → giảm batch)", num(ru.max_retries, (v) => save({ runs: { max_retries: v } }), { min: 0, max: 5 }))),
      toggle("Tự phục hồi lỗi có cách sửa an toàn (ghi rõ thay đổi cấu hình)", ru.auto_recover, (v) => save({ runs: { auto_recover: v } })),
      toggle("Tìm bài báo thật (OpenAlex, Semantic Scholar, arXiv) trước khi tổng hợp /lit", ru.web_search, (v) => save({ runs: { web_search: v } })),
      h("h3", {}, "Guard phần cứng"),
      h("p.help", {}, "RTX 3060 12 GB: không bao giờ chạy 2 job GPU cùng lúc. Có thể giảm các slot khác nếu máy chậm."),
      h("div.grid2", {}, ...["cpu", "local_llm", "cli", "cloud"].map((k) => field({ cpu: "Job CPU đồng thời", local_llm: "Mô hình local đồng thời", cli: "CLI provider đồng thời", cloud: "Gọi cloud đồng thời" }[k],
        num(ru["slot_" + k], (v) => save({ runs: { ["slot_" + k]: v } }), { min: 1, max: { cpu: 1, local_llm: 1, cli: 2, cloud: 3 }[k] })))),
      toggle("Tự gỡ mô hình local đang rảnh khỏi VRAM khi cần GPU cho thí nghiệm", rs.auto_unload_for_gpu, (v) => save({ resources: { auto_unload_for_gpu: v } })),
      field("Nhiệt độ GPU tối đa (°C) — vượt thì chạy CPU", num(rs.gpu_temp_limit_c, (v) => save({ resources: { gpu_temp_limit_c: v } }), { min: 60, max: 95 })),
      h("h3", {}, "VS Code"),
      field("Đường dẫn VS Code (để trống = tự tìm)", h("input.input", { value: cfg.workspace.vscode_path || "", onchange: (e) => save({ workspace: { vscode_path: e.target.value } }) })));
  }

  // ------------------------------------------------------------------ memory & context
  function memory(b) {
    const a = cfg.aiws;
    b.append(h("h3", {}, "Bộ nhớ ngữ cảnh chạy ngầm"),
      h("p.help", {}, "Ngữ cảnh dự án (đề cương, quyết định, giả thuyết, run, tài liệu) được biên dịch tự động cho mỗi câu hỏi. Việc ghi nhớ chỉ xuất hiện như đề xuất trong chat để bạn Chấp nhận / Bỏ qua."),
      field("Ghi nhớ", sel([["suggest", "Đề xuất — bạn duyệt từng mục (khuyên dùng)"], ["manual", "Thủ công — chỉ khi bạn bấm Ghi nhớ"], ["auto", "Tự động có giới hạn (câu hỏi mở)"], ["off", "Tắt"]], a.memory_mode, (v) => save({ aiws: { memory_mode: v } }))),
      field("Chế độ", sel([["automation", "Tự động — AI tự dùng công cụ chỉ-đọc, mọi thay đổi chờ bạn duyệt"], ["manual", "Thủ công — xem ngữ cảnh trước khi gửi, duyệt mọi bước"]], a.operating_mode, (v) => save({ aiws: { operating_mode: v } }))),
      field("Ngân sách ngữ cảnh (token)", num(a.context_budget_tokens, (v) => save({ aiws: { context_budget_tokens: v } }), { min: 500, max: 60000, step: 500 })),
      field("Thời gian tối đa một câu trả lời (giây)", num(a.max_turn_s, (v) => save({ aiws: { max_turn_s: v } }), { min: 30, max: 7200 })));
  }

  // ------------------------------------------------------------------ skills
  async function skills(b) {
    b.append(h("h3", {}, "Kỹ năng"), h("p.help", {}, "Mỗi lệnh / là một file Markdown: built-in, của bạn (mọi dự án) hoặc của dự án này. Kỹ năng không cấp thêm quyền — việc rủi ro vẫn chờ bạn duyệt."));
    const r = await PL.get("/api/skills").catch(() => ({ skills: [], errors: [] }));
    const t = h("table.grid", {}, h("tr", {}, h("th", {}, "Lệnh"), h("th", {}, "Mô tả"), h("th", {}, "Kiểu"), h("th", {}, "")));
    for (const s of r.skills) {
      t.append(h("tr", {}, h("td.mono", {}, "/" + s.name), h("td", {}, s.title, h("div.muted", { style: "font-size:12px" }, s.description)),
        h("td", {}, h("span.chip", {}, s.mode === "run" ? "chạy nền" : "chat"), " ", h("span.chip", {}, s.origin)),
        h("td", {}, s.origin !== "builtin" ? h("button.icon", { type: "button", title: "Xoá", html: PL.icon("trash"), onclick: async () => { if (await PL.safe(() => PL.del("/api/skills/" + s.name), "Đã xoá")) { PL.chat.loadSkills(); b.innerHTML = ""; skills(b); } } }) : null)));
    }
    b.append(t);
    (r.errors || []).forEach((e) => b.append(h("div.err-line", {}, `${e.file}: ${e.error}`)));
    const tpl = "---\nname: tomtat\ntitle: Tóm tắt bài báo\ndescription: Tóm tắt một bài báo theo mẫu của tôi\nusage: <tên bài / file>\ncategory: research\nagent: research\nmode: chat\nrisk: 0\n---\nTóm tắt theo mẫu: vấn đề, phương pháp, dữ liệu, kết quả, hạn chế, liên hệ với đề cương của tôi.\n";
    const ta = h("textarea.input.mono", { rows: "12" }, tpl);
    const scope = sel([["project", "Chỉ dự án này"], ["user", "Mọi dự án"]], "project", () => {});
    b.append(h("h3", {}, "Tạo / sửa kỹ năng"), ta, h("div.row", { style: "margin-top:8px" }, scope, h("span.grow"),
      h("button.btn.accent", { type: "button", onclick: async () => { if (await PL.safe(() => PL.post("/api/skills", { text: ta.value, scope: scope.value }), "Đã lưu kỹ năng")) { PL.chat.loadSkills(); b.innerHTML = ""; skills(b); } } }, "Lưu kỹ năng")));
  }

  // ------------------------------------------------------------------ appearance
  function look(b) {
    let cur = "system";
    try { cur = W.localStorage.getItem("pl.theme") || "system"; } catch (e) { /* private mode */ }
    b.append(h("h3", {}, "Giao diện"), field("Chủ đề", sel([["system", "Theo hệ thống"], ["light", "Sáng"], ["dark", "Tối"]], cur, (v) => {
      try { if (v === "system") W.localStorage.removeItem("pl.theme"); else W.localStorage.setItem("pl.theme", v); } catch (e) { /* private mode */ }
      if (v === "system") delete W.document.documentElement.dataset.theme; else W.document.documentElement.dataset.theme = v;
    })), h("p.help", {}, `PhD Research Lab ${cfg.version} · dữ liệu dự án: ${cfg.project.data_dir || ""}`));
  }
})(window);
