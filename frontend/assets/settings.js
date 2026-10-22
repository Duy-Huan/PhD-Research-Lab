/* PhD Research Lab — Settings: everything technical lives here so the chat stays simple.
   Models & agents · Research providers · Experiments & hardware · Memory · Skills · Plugins (GitHub) · Appearance. */
(function (W) {
  "use strict";
  const PL = W.PL, h = PL.h;
  const S = (PL.settings = {});
  const TABS = [["models", PL.t("Mô hình & agent")], ["providers", PL.ui("Research providers")], ["hardware", PL.t("Thí nghiệm & phần cứng")],
    ["mcp", "MCP & ChatGPT"], ["memory", PL.t("Bộ nhớ & ngữ cảnh")], ["skills", PL.t("Kỹ năng (/)")], ["plugins", "Plugin (GitHub)"], ["look", PL.t("Giao diện & ngôn ngữ")]];
  let cfg = null;

  S.open = async function (tab) {
    cfg = await PL.get("/api/config").catch((e) => { PL.toast(e.message, "err"); return null; });
    if (!cfg) return;
    cfg.routing = cfg.routing || {};
    cfg.gateway = cfg.gateway || {};
    cfg.mcp = cfg.mcp || {};
    cfg.mcp_agent = cfg.mcp_agent || { enabled: false, models: [] };
    const nav = h("nav");
    const keywords = { models: "local API key model routing priority quota failover ollama LM Studio", providers: "CLI Codex Claude Gemini Feynman OpenScience research engine collaborative web search", mcp: "MCP ChatGPT tools protocol", hardware: "GPU Docker ClearML Colab experiment training", memory: "context cache memory", skills: "skills commands", plugins: "GitHub plugins", look: "language font theme" };
    const search = h("input.input.settings-search", { type: "search", placeholder: PL.ui("Search settings…"), "aria-label": PL.ui("Search settings"), oninput: (e) => {
      const q = e.target.value.trim().toLowerCase();
      const matches = TABS.filter(([k, label]) => (label + " " + keywords[k]).toLowerCase().includes(q));
      PL.$$(".nav", nav).forEach((b) => { b.hidden = !matches.some(([k]) => k === b.dataset.k); });
      if (q && matches.length) show(matches[0][0]);
      if (q && !matches.length) body.replaceChildren(h("p.help", {}, PL.ui("No matching settings")));
      if (!q) show(tab || "models");
    } });
    nav.append(search);
    const body = h("div.sb");
    const show = (k) => {
      PL.$$(".nav", nav).forEach((b) => b.classList.toggle("active", b.dataset.k === k));
      const pane = h("div");
      body.replaceChildren(pane);  // a late async response can only update its detached pane
      ({ models, providers, mcp, hardware, memory, skills, plugins, look })[k](pane);
    };
    for (const [k, label] of TABS) nav.append(h("button.nav", { type: "button", dataset: { k }, onclick: () => show(k) }, label));
    PL.modal({ title: PL.t("Cài đặt"), wide: true, raw: true, body: h("div.settings", {}, nav, body) });
    show(tab || "models");
  };

  const save = (patch, msg) => PL.safe(async () => { cfg = await PL.post("/api/config", patch); return cfg; }, msg || PL.t("Đã lưu"));
  const field = (label, el, help) => h("label.field", {}, h("span", {}, label), el, help ? h("small.muted", {}, help) : null);
  const sel = (opts, value, onchange) => h("select.input", { onchange: (e) => onchange(e.target.value) },
    opts.map(([v, l]) => h("option", { value: v, selected: String(v) === String(value) || null }, l)));
  const toggle = (label, value, onchange, help) => h("div.field", {}, h("label.switch", {}, h("input", { type: "checkbox", checked: value || null, onchange: (e) => onchange(e.target.checked) }), label),
    help ? h("small.muted", {}, help) : null);
  const num = (value, onchange, attrs) => h("input.input", Object.assign({ type: "number", value, onchange: (e) => onchange(Number(e.target.value)) }, attrs));
  const modelSelect = (options, value, onchange) => {
    const select = sel(options.concat([["__custom__", PL.ui("Custom model…")]]), value, async (v) => {
      if (v === "__custom__") {
        const name = await PL.prompt("Model", PL.t("Model ID của provider"), "");
        if (!name || name === "__custom__") { select.value = value; return; }
        select.append(h("option", { value: name }, name)); select.value = name; v = name;
      }
      value = v; onchange(v);
    });
    return select;
  };

  // ------------------------------------------------------------------ models & agents
  async function models(b) {
    b.append(h("h3", {}, PL.t("Hai agent + một tiện ích chạy nền")),
      h("p.help", {}, PL.t("Research agent điều phối mọi việc (nghiên cứu, thiết kế, code, viết bài); Reviewer agent phản biện và kiểm chứng. Kỹ năng (/) quyết định agent làm gì — không cần một agent cho mỗi công cụ.")));
    const engines = [["mcp", PL.ui("MCP inference tool")], ["auto", PL.t("Tự động (local → cloud)")], ["claude", PL.t("Claude (nếu có key)")], ["cloud", PL.t("Cloud mặc định")], ["local", "LM Studio (local)"], ["ollama", "Ollama (local)"]]
      .concat(Object.entries(cfg.provider_specs).map(([k, v]) => [k, v.label]));
    const t = h("table.grid.agent-model-grid", {}, h("tr", {}, h("th", {}, PL.ui("Agent")), h("th", {}, PL.ui("Engine")), h("th", {}, PL.t("Model (tuỳ chọn)"))));
    let localCatalog = {};
    const providerCatalog = {};
    const agentRows = [];
    const sourceFor = (mode) => mode === "cloud" ? cfg.default_cloud : mode === "claude" ? (cfg.providers.anthropic.has_key ? "anthropic" : cfg.default_cloud) : mode;
    const choices = (mode) => {
      const pid = sourceFor(mode);
      if (pid === "auto") return [];
      if (pid === "mcp") return cfg.mcp_agent.models;
      if (pid === "local" || pid === "ollama") return [cfg[pid === "local" ? "local_model" : "ollama_model"], ...(localCatalog[pid] || [])].filter(Boolean);
      return [cfg.providers[pid].model, ...(providerCatalog[pid] || cfg.provider_specs[pid].models || [])].filter(Boolean);
    };
    for (const [a, spec] of Object.entries(cfg.agents)) {
      let mode = cfg.agent_modes[a], value = (cfg.agent_models || {})[a] || "";
      const cell = h("td", { "data-label": PL.ui("Model") });
      let boundSource = sourceFor(mode);
      const paint = () => {
        const nextSource = sourceFor(mode);
        if (nextSource !== boundSource) value = "";
        boundSource = nextSource;
        const model = modelSelect([["", PL.t("mặc định của engine")], ...Array.from(new Set([...choices(mode), value].filter(Boolean))).map((m) => [m, m])], value, (v) => { value = v; save({ agent_models: { [a]: v } }); });
        model.setAttribute("aria-label", a + " · " + PL.ui("Model"));
        model.disabled = mode === "auto";
        cell.replaceChildren(model);
      };
      const source = sel(engines, mode, async (v) => {
        source.disabled = true;
        cell.querySelector("select").disabled = true;
        const result = await save({ agent_modes: { [a]: v }, agent_models: { [a]: "" } });
        if (result) { mode = v; value = ""; paint(); await PL.chat.loadModels(); }
        else { source.value = mode; paint(); }
        source.disabled = false;
      });
      source.setAttribute("aria-label", a + " · " + PL.ui("Model source"));
      agentRows.push({ paint });
      paint();
      t.append(h("tr", {}, h("td", {}, h("b", {}, a), h("div.muted", { style: "font-size:12px" }, PL.t(spec.label))), h("td", { "data-label": PL.ui("Model source") }, source), cell));
    }
    b.append(h("div.table-scroll", { role: "region", "aria-label": PL.ui("Agent models"), tabindex: 0 }, t),
      h("p.help", {}, PL.ui("Chat’s Auto option uses these agent assignments; a fixed provider in chat overrides them.")),
      h("p.help", {}, PL.ui("Choose a source, then its model. Auto routing uses each provider’s own default. MCP needs an inference tool; a general tool server is not a model.")));
    const ma = cfg.mcp_agent;
    b.append(h("details.mcp-agent-config", {}, h("summary", {}, PL.ui("Configure MCP inference agent")),
      toggle(PL.ui("Enable MCP inference agent"), ma.enabled, (v) => save({ mcp_agent: { enabled: v } })),
      field(PL.ui("MCP endpoint"), h("input.input", { value: ma.url || "", placeholder: "http://127.0.0.1:8766/mcp", onchange: (e) => save({ mcp_agent: { url: e.target.value } }) })),
      field(PL.ui("Inference tool name"), h("input.input", { value: ma.tool || "research", onchange: (e) => save({ mcp_agent: { tool: e.target.value } }) })),
      field(PL.ui("MCP model catalog (one ID per line)"), h("textarea.input", { rows: 3, value: ma.models.join("\n"), onchange: async (e) => {
        const result = await save({ mcp_agent: { models: Array.from(new Set(e.target.value.split(/\n|,/).map((m) => m.trim()).filter(Boolean))) } });
        if (result) agentRows.forEach((row) => row.paint());
      } })),
      field(PL.ui("MCP access token"), h("input.input", { type: "password", autocomplete: "off", placeholder: ma.has_token ? PL.t("•••••• (đã lưu)") : PL.t("chưa có"), onchange: async (e) => { const result = await save({ mcp_agent: { token: e.target.value } }); if (result) e.target.value = ""; } })),
      h("p.help", {}, PL.ui("The named tool must accept system (string) and messages (array); model, max_tokens and temperature are optional. Responses appear after completion. Only this endpoint receives its token."))));
    b.append(h("h3", {}, PL.ui("Cloud API")), h("p.help", {}, PL.t("Key chỉ được gửi tới máy chủ của chính nhà cung cấp đó; giao diện không bao giờ hiển thị lại key.")));
    b.append(field(PL.t("Cloud mặc định"), sel(Object.entries(cfg.provider_specs).map(([k, v]) => [k, v.label]), cfg.default_cloud, async (v) => { const result = await save({ default_cloud: v }); if (result) agentRows.forEach((row) => row.paint()); })));
    const keys = h("table.grid", {}, h("tr", {}, h("th", {}, PL.t("Nhà cung cấp")), h("th", {}, "API key"), h("th", {}, "Model"), h("th", {}, "")));
    const more = h("table.grid");
    const specs = Object.entries(cfg.provider_specs);
    const main = new Set(["anthropic", "openai", "gemini", "deepseek", cfg.default_cloud]);
    for (const [pid, spec] of specs) {
      const p = cfg.providers[pid] || {};
      const table = p.has_key || main.has(pid) ? keys : more;
      const key = h("input.input", { type: "password", placeholder: p.has_key ? PL.t("•••••• (đã lưu)") : PL.t("chưa có"), autocomplete: "off" });
      const model = modelSelect(Array.from(new Set([p.model, ...(spec.models || [])].filter(Boolean))).map((m) => [m, m]), p.model || "", () => {});
      table.append(h("tr", {}, h("td", {}, spec.label), h("td", {}, key, h("details", {}, h("summary.muted", {}, PL.ui("Endpoint")), field(PL.ui("Base URL (optional)"), h("input.input", { value: p.base_url || "", placeholder: spec.base_url, onchange: (e) => save({ providers: { [pid]: { base_url: e.target.value } } }) })))), h("td", {}, model, h("datalist", { id: "ml-" + pid }, (spec.models || []).map((m) => h("option", { value: m })))),
        h("td", {}, h("div.row", {}, h("button.btn.sm", { type: "button", onclick: async (e) => {
          const button = e.currentTarget; button.disabled = true;
          const patch = { model: model.value };
          if (key.value) patch.api_key = key.value;
          const result = await save({ providers: { [pid]: patch } });
          if (result) { key.value = ""; agentRows.forEach((row) => row.paint()); await PL.chat.loadModels(); }
          button.disabled = false;
        } }, PL.t("Lưu")), h("button.btn.sm.ghost", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/test", { provider: pid }).then((r) => PL.toast(`OK · ${r.model}: ${r.reply}`))) }, PL.t("Thử")),
        h("button.btn.sm.ghost", { type: "button", onclick: () => PL.safe(async () => {
          const r = await PL.post("/api/models/list", { provider: pid });
          const current = model.value;
          providerCatalog[pid] = r.models;
          model.replaceChildren(...Array.from(new Set([current, ...r.models].filter(Boolean))).map((m) => h("option", { value: m, selected: m === current || null }, m)), h("option", { value: "__custom__" }, PL.ui("Custom model…")));
          agentRows.forEach((row) => row.paint());
        }) }, "↻ Models")))));
    }
    b.append(h("div.table-scroll", { tabindex: 0, "aria-label": PL.ui("Cloud API") }, keys), h("details", { style: "margin-top:8px" }, h("summary.muted", { style: "cursor:pointer;font-size:13px" }, PL.t("Nhà cung cấp khác ({0})", more.childNodes.length)), h("div.table-scroll", { tabindex: 0 }, more)));
    b.append(h("h3", {}, PL.t("Thứ tự ưu tiên & năng lực / Routing")),
      toggle(PL.ui("Capability-aware failover"), cfg.routing.capability_aware !== false, (v) => save({ routing: { capability_aware: v } }), PL.t("Giữ checkpoint và chờ provider phù hợp khi hết quota.")));
    const chainOptions = [["@cloud", PL.t("Cloud mặc định")], ["@claude", "Claude API"], ["ollama", "Ollama"], ["local", "LM Studio"], ...Object.entries(cfg.provider_specs).map(([k, v]) => [k, v.label])];
    for (const kind of ["reasoning", "code", "writing", "summarize", "extract"]) {
      const current = (cfg.routing.chains || {})[kind] || [];
      const slots = Array.from({ length: 4 }, (_, i) => sel([["", "—"], ...chainOptions], current[i] || "", () => {}));
      b.append(field(kind, h("div.row", {}, ...slots, h("button.btn.sm", { type: "button", onclick: () => save({ routing: { chains: Object.assign({}, cfg.routing.chains, { [kind]: Array.from(new Set(slots.map((s) => s.value).filter(Boolean))) }) } }) }, PL.t("Lưu thứ tự")))));
      if (["reasoning", "code", "writing"].includes(kind)) {
        const qualified = ((cfg.routing.verified_fallbacks || {})[kind] || []);
        const choices = [["local", cfg.local_model], ["ollama", cfg.ollama_model], ...Object.entries(cfg.providers).map(([id, p]) => [id, p.model])].filter(([, model]) => model);
        b.append(field(`${kind} · ${PL.ui("Qualified fallback models")}`, h("select.input", { multiple: true, size: 3, onchange: (e) => save({ routing: { verified_fallbacks: Object.assign({}, cfg.routing.verified_fallbacks, { [kind]: Array.from(e.target.selectedOptions).map((o) => o.value) }) } }) },
          choices.map(([id, model]) => h("option", { value: `${id}:${model}`, selected: qualified.includes(`${id}:${model}`) || null }, `${id} · ${model}`))), PL.t("Chỉ đánh dấu sau khi bạn đã đánh giá năng lực cho tác vụ này. Đổi model sẽ cần kiểm chứng lại.")));
      }
    }
    b.append(h("h3", {}, PL.t("Mô hình trên máy (VRAM)")),
      toggle(PL.ui("Use configured cloud if a local model fails"), cfg.fallback_to_cloud, (v) => save({ fallback_to_cloud: v }), PL.ui("Cloud fallback may incur API charges. Disable it to keep a fixed local agent local.")));
    const st = h("div.muted", {}, h("span.spin"));
    const localSelect = sel([["", "Auto"], ...[cfg.local_model].filter(Boolean).map((m) => [m, m])], cfg.local_model || "", (v) => save({ local_model: v }));
    const ollamaSelect = sel([["", "Auto"], ...[cfg.ollama_model].filter(Boolean).map((m) => [m, m])], cfg.ollama_model || "", (v) => save({ ollama_model: v }));
    b.append(h("div.grid2", {}, field("LM Studio URL", h("input.input", { value: cfg.lmstudio_base_url, onchange: (e) => save({ lmstudio_base_url: e.target.value }) })),
      field("Model LM Studio", localSelect),
      field("Ollama URL", h("input.input", { value: cfg.ollama_base_url, onchange: (e) => save({ ollama_base_url: e.target.value }) })),
      field("Model Ollama", ollamaSelect)), st);
    b.append(toggle(PL.t("Gỡ mô hình local khỏi VRAM khi tắt PhD Lab"), cfg.lifecycle.unload_on_exit, (v) => save({ lifecycle: { unload_on_exit: v } })),
      field(PL.t("Tự gỡ mô hình khi rảnh sau (phút)"), num(cfg.lifecycle.local_idle_min, (v) => save({ lifecycle: { local_idle_min: v } }), { min: 1, max: 240 }),
        PL.t("Tác vụ nền (tóm tắt, trích xuất) luôn: nạp → chạy → gỡ ngay.")));
    PL.get("/api/models/local").then((r) => {
      st.innerHTML = "";
      const lm = r.lmstudio || {}, ol = r.ollama || {};
      localCatalog = { local: (lm.models || []).map((m) => m.id || m), ollama: (ol.models || []).map((m) => m.id || m) };
      agentRows.forEach((row) => row.paint());
      for (const [select, models, current] of [[localSelect, lm.models || [], cfg.local_model], [ollamaSelect, ol.models || [], cfg.ollama_model]]) {
        select.replaceChildren(h("option", { value: "" }, "Auto"), ...Array.from(new Set([current, ...models.map((m) => m.id || m)].filter(Boolean))).map((m) => h("option", { value: m, selected: m === current || null }, m)));
      }
      const loaded = [].concat((lm.loaded || []).map((m) => "LM Studio: " + m), (ol.loaded || []).map((m) => "Ollama: " + (m.id || m)));
      st.append(h("div.row", {}, h("span.dot." + (lm.online ? "ok" : "")), "LM Studio", h("span.dot." + (ol.online ? "ok" : "")), "Ollama",
        h("span.grow", {}, loaded.length ? PL.ui(" · Loaded in VRAM: ") + loaded.join(", ") : PL.t(" · VRAM trống")),
        h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post("/api/models/unload", { engine: "all" }), PL.t("Đã gỡ mô hình khỏi VRAM")) }, PL.t("Unload tất cả"))));
    }).catch(() => { st.textContent = PL.t("Không đọc được trạng thái local."); });
  }

  // ------------------------------------------------------------------ research providers
  async function providers(b) {
    for (const pid of ["codex", "claude_code", "gemini_cli", "antigravity"]) {
      b.append(field(`${pid} · model catalog`, h("textarea.input", { rows: 2, placeholder: PL.t("Mỗi dòng một model ID đã kiểm chứng"), value: ((cfg.gateway.cli_models || {})[pid] || []).join("\n"), onchange: (e) => save({ gateway: { cli_models: Object.assign({}, cfg.gateway.cli_models, { [pid]: Array.from(new Set(e.target.value.split(/\n|,/).map((m) => m.trim()).filter(Boolean))) }) } }) }), PL.t("Danh sách dùng trong model picker; catalog không xác nhận quota hoặc gói miễn phí.")));
    }
    b.append(h("button.btn.sm", { type: "button", onclick: () => PL.safe(async () => {
      const r = await PL.post("/api/models/cli/codex", {}); await PL.chat.loadModels(); PL.toast(`${r.models.length} ${PL.ui("models (catalog; access checked when chatting)")}`);
    }) }, "↻ Codex model catalog"));
    b.append(h("h3", {}, "CLI · MCP"),
      toggle("Codex app-server (prototype)", cfg.gateway.codex_app_server, (v) => save({ gateway: { codex_app_server: v } }), PL.t("Mặc định tắt. Chỉ fallback sang exec trước khi gửi turn; giữ native thread resume.")));
    b.append(h("h3", {}, PL.t("Research providers chạy song song")),
      h("p.help", {}, PL.t("PhD Lab giữ trạng thái nghiên cứu; mỗi provider chỉ nhận một nhiệm vụ có phạm vi rõ trong workspace riêng. Provider chưa sẵn sàng được báo trung thực và tác vụ dùng mô hình của ứng dụng.")));
    const list = h("div.list", {}, h("span.spin"));
    b.append(list);
    // Slow CLI probes update only their status list, never block the settings form below it.
    PL.get("/api/providers?fresh=1").catch(() => ({ providers: [] })).then((r) => {
      list.innerHTML = "";
      const cat = { research: PL.t("Nghiên cứu"), coding: "Code", experiment: PL.t("Thí nghiệm"), publication: PL.t("Xuất bản") };
      for (const p of r.providers) {
      list.append(h("div.li", {}, h("span.dot." + (p.ready ? "ok" : ["NOT_CONFIGURED", "STOPPED"].includes(p.state) ? "warn" : "")),
        h("div.m", {}, h("div.t", {}, p.label, " ", h("span.chip", {}, cat[p.category] || p.category)), h("div.s", { style: "white-space:normal" }, `${p.state} — ${p.detail}`),
          (p.setup || []).length ? h("div.s.mono", { style: "white-space:normal" }, p.setup.join("  ·  ")) : null),
        ["feynman", "claude_code", "codex", "gemini_cli", "antigravity"].includes(p.id) && !p.ready ?
          h("button.btn.sm", { type: "button", onclick: () => PL.safe(() => PL.post(`/api/providers/${p.id}/connect`), PL.t("Đã mở cửa sổ đăng nhập của nhà cung cấp")) }, PL.t("Đăng nhập")) : null));
      }
    });
    const rp = cfg.research_providers;
    const osci = cfg.openscience || {};
    const engineToken = h("input.input", { type: "password", autocomplete: "off", placeholder: osci.has_token ? PL.t("•••••• (đã lưu)") : PL.ui("OpenScience deployment token") });
    b.append(h("h3", {}, PL.ui("Research engines · Feynman / OpenScience")),
      field(PL.ui("Research engine mode"), sel([["auto", PL.ui("Auto Research")], ["feynman", PL.ui("Feynman Only")], ["openscience", PL.ui("OpenScience Only")], ["collaborative", PL.ui("Collaborative (2 stages)")]], rp.engine_mode || "auto", (v) => save({ research_providers: { engine_mode: v } }))),
      h("p.help", {}, PL.ui("Research engines are configured separately from model providers. OpenScience uses its own models, skills and runtime tools; its skills are not copied into the plugin registry.")),
      toggle(PL.ui("Enable OpenScience runtime adapter"), osci.enabled, (v) => save({ openscience: { enabled: v } })),
      field(PL.ui("OpenScience loopback URL"), h("input.input", { value: osci.base_url || "http://127.0.0.1:4096", onchange: (e) => save({ openscience: { base_url: e.target.value } }) })),
      field(PL.ui("Deployment token"), h("div.row", {}, engineToken, h("button.btn.sm", { type: "button", onclick: () => PL.safe(async () => {
        if (engineToken.value) await save({ openscience: { token: engineToken.value } }); engineToken.value = "";
      }) }, PL.ui("Save token")))),
      toggle(PL.ui("I reviewed the separate runtime, permissions and trace sharing"), osci.policy_confirmed, (v) => save({ openscience: { policy_confirmed: v } }), PL.ui("A local runtime can still send research to its model and tracing services. Review the integration guide before enabling it.")),
      toggle(PL.ui("Allow proposed code execution in the workspace"), osci.allow_execution, (v) => save({ openscience: { allow_execution: v } }), PL.ui("Approve each sensitive permission. Remote compute and native worker delegation are disabled in this adapter.")),
      field(PL.ui("OpenScience timeout (seconds)"), num(osci.timeout_s || 600, (v) => save({ openscience: { timeout_s: v } }), { min: 5, max: 7200 })),
      field(PL.ui("Artifact budget (MiB total)"), num(osci.max_artifact_mb || 64, (v) => save({ openscience: { max_artifact_mb: v } }), { min: 1, max: 1024 })),
      field(PL.ui("OpenScience model provider (optional; required for Auto qualification)"), h("input.input", { value: osci.model_provider || "", onchange: (e) => save({ openscience: { model_provider: e.target.value, qualified_tasks: [] } }) })),
      field(PL.ui("OpenScience model ID"), h("input.input", { value: osci.model_id || "", onchange: (e) => save({ openscience: { model_id: e.target.value, qualified_tasks: [] } }) })),
      field(PL.ui("Qualified tasks for this configured model"), h("select.input", { multiple: true, size: 4, onchange: (e) => save({ openscience: { qualified_tasks: Array.from(e.target.selectedOptions).map((o) => o.value) } }) },
        ["literature", "analysis", "prototype", "review"].map((k) => h("option", { value: k, selected: (osci.qualified_tasks || []).includes(k) || null }, PL.ui(k))))),
      h("p.help", {}, PL.ui("Use /science for supervised tasks. OpenScience manages the default model unless overridden. Agent completion does not verify training or scientific conclusions.")));
    b.append(h("h3", {}, "Feynman"),
      toggle(PL.t("Dùng Feynman cho /lit, /deepresearch, /compare, /review"), rp.feynman_enabled, (v) => save({ research_providers: { feynman_enabled: v } })),
      toggle(PL.t("Cho Feynman dùng API key Anthropic / OpenAI của ứng dụng"), rp.feynman_share_app_key, (v) => save({ research_providers: { feynman_share_app_key: v } }),
        PL.t("Tắt: Feynman dùng đăng nhập riêng (`feynman model login`). Bật: chi phí tính vào tài khoản API của bạn.")),
      field(PL.t("Giới hạn thời gian mỗi tác vụ Feynman (giây)"), num(rp.feynman_timeout_s, (v) => save({ research_providers: { feynman_timeout_s: v } }), { min: 60, max: 7200 })),
      h("h3", {}, "Code"),
      field(PL.t("Coding provider mặc định cho /code"), sel([["claude_code", "Claude Code"], ["codex", "OpenAI Codex"], ["gemini_cli", "Gemini CLI"], ["antigravity", "Antigravity"], ["app", PL.t("Mô hình của ứng dụng")]],
        rp.coding_default, (v) => save({ research_providers: { coding_default: v } }))));
    const ws = cfg.search || {};
    b.append(h("h3", {}, PL.t("Tìm paper & web")),
      h("p.help", {}, PL.t("Lit tìm trên OpenAlex, Semantic Scholar, arXiv và web. IEEE API và Google Scholar qua SerpAPI dùng key riêng. Kết quả không có PDF mở vẫn lưu được thông tin vào thư viện.")),
      field(PL.t("Công cụ tìm web"), sel([["duckduckgo", PL.t("DuckDuckGo (không cần key)")], ["tavily", "Tavily"], ["brave", "Brave Search"]], ws.web_engine || "duckduckgo", (v) => save({ search: { web_engine: v } }))),
      field(PL.t("Số kết quả tìm kiếm"), num(ws.n_results || 12, (v) => save({ search: { n_results: v } }), { min: 1, max: 30 })),
      field(PL.t("Email cho API học thuật (tuỳ chọn)"), h("input.input", { type: "email", value: ws.mailto || "", onchange: (e) => save({ search: { mailto: e.target.value } }) })),
      toggle(PL.t("Đọc nội dung trang web khi tìm kiếm"), ws.read_pages, (v) => save({ search: { read_pages: v } })));
    const searchKeys = h("div.grid2");
    for (const [key, label] of [["tavily_key", "Tavily API key"], ["brave_key", "Brave Search API key"], ["s2_key", "Semantic Scholar API key"],
      ["openalex_key", "OpenAlex API key"], ["ieee_key", "IEEE Xplore API key"], ["serpapi_key", "SerpAPI key (Google Scholar)"]]) {
      const input = h("input.input", { type: "password", autocomplete: "off", placeholder: ws[key] || ws["has_" + key] ? PL.t("Đã lưu key · nhập để thay thế") : PL.t("Chưa cấu hình") });
      searchKeys.append(field(label, h("div.row", {}, input, h("button.btn.sm", { type: "button", onclick: async () => {
        if (!input.value.trim()) return;
        if (await save({ search: { [key]: input.value.trim() } })) input.value = "";
      } }, PL.t("Lưu key")))));
    }
    b.append(searchKeys, h("p.help", {}, PL.t("Xếp hạng hiển thị kèm nguồn và năm khi có dữ liệu. Chỉ số trích dẫn / h-index của tạp chí không được suy ra thành Q1–Q4 hoặc điểm chất lượng bài báo.")));
    const rankingYear = h("input.input", { type: "number", min: 1999, max: new Date().getFullYear(), value: new Date().getFullYear() - 1, "aria-label": PL.t("Năm dữ liệu xếp hạng"), style: "max-width:110px" });
    const rankingFile = h("input.input", { type: "file", accept: ".csv,text/csv", "aria-label": "File SCImago CSV" });
    const rankingStatus = h("p.muted", { role: "status" });
    const rankingImport = h("button.btn.sm", { type: "button", onclick: async () => {
      if (!rankingFile.files.length) { rankingStatus.textContent = PL.t("Chọn file CSV trước khi nhập."); return; }
      if (!rankingYear.checkValidity()) { rankingYear.reportValidity(); return; }
      const data = new W.FormData();
      data.append("file", rankingFile.files[0]); data.append("year", rankingYear.value);
      rankingImport.disabled = true; rankingStatus.textContent = PL.t("Đang nhập dữ liệu…");
      try {
        const r = await PL.api("POST", "/api/journals/import", data);
        rankingStatus.textContent = PL.t("Đã nhập {0} tạp chí · {1} · {2}", r.records, r.year, r.source);
      } catch (e) { rankingStatus.textContent = e.message; }
      finally { rankingImport.disabled = false; }
    } }, PL.t("Nhập bảng xếp hạng"));
    const rk = cfg.ranking || {};
    const rstat = h("div.rank-status", {}, h("span.spin"));
    const paintRank = async (refresh) => {
      const st = await PL.get("/api/ranking" + (refresh ? "?refresh=1" : "")).catch((e) => ({ error: e.message }));
      rstat.replaceChildren();
      if (st.error) { rstat.append(h("p.err-line", {}, st.error)); return; }
      const j = st.journals || {}, c = st.conferences || {};
      rstat.append(h("div", {}, h("div.kv-row", {}, h("span.dot." + (c.records ? "ok" : "warn")), h("b", {}, PL.t("Hội nghị (CORE): ")),
        c.records ? PL.t("{0} hội nghị · {1} · cập nhật {2}", c.records, c.source, String(c.fetched_at || "").slice(0, 10)) : PL.t("chưa tải — bấm Cập nhật ngay")),
      h("div.kv-row", {}, h("span.dot." + (j.records ? "ok" : "warn")), h("b", {}, PL.t("Tạp chí (SCImago): ")),
        j.records ? PL.t("{0} tạp chí · năm {1}{2}", j.records, j.year, j.origin ? " · " + j.origin : "") : PL.t("chưa có dữ liệu")),
      ((st.refreshed || {}).scimago || {}).imported ? h("p.chip.ok", {}, PL.t("Đã tự nhập {0} từ Downloads", st.refreshed.scimago.file)) : null,
      ((st.refreshed || {}).core || {}).error ? h("p.err-line", {}, PL.t("CORE: {0}", st.refreshed.core.error)) : null));
    };
    b.append(h("h3", {}, PL.t("Xếp hạng venue tự động (plugin ranking)")),
      h("p.help", {}, PL.t("Mỗi bài tìm được hoặc lưu vào thư viện được tự kiểm tra hạng: hội nghị theo CORE (A*, A, B, C — tải và làm mới tự động), tạp chí theo SCImago (Q1–Q4, SJR). SCImago chặn tải tự động, nên chỉ cần bấm “Tải bảng SCImago” một lần trên trình duyệt: file scimagojr*.csv trong thư mục Downloads sẽ được nhập tự động. Dữ liệu lưu ở data/plugins/ranking/.")),
      toggle(PL.t("Tự kiểm tra ranking (tải CORE, theo dõi Downloads)"), rk.auto, (v) => save({ ranking: { auto: v } })),
      h("div.grid2", {}, field(PL.t("Bộ xếp hạng CORE"), sel([["ICORE2026", "ICORE2026"], ["CORE2023", "CORE2023"], ["CORE2021", "CORE2021"]], rk.core_source || "ICORE2026", (v) => save({ ranking: { core_source: v } }).then(() => paintRank(true)))),
        field(PL.t("Làm mới CORE sau (ngày)"), num(rk.refresh_days || 30, (v) => save({ ranking: { refresh_days: v } }), { min: 1, max: 365 }))),
      rstat,
      h("div.row.wrap", { style: "margin:8px 0" }, h("button.btn.sm", { type: "button", onclick: () => { rstat.replaceChildren(h("span.spin")); paintRank(true); } }, h("span", { html: PL.icon("sync") }), PL.t("Cập nhật ngay")),
        h("a.btn.sm", { href: "https://www.scimagojr.com/journalrank.php?out=xls", target: "_blank", rel: "noopener" }, h("span", { html: PL.icon("download") }), PL.t("Tải bảng SCImago (mở trình duyệt)"))),
      h("details", {}, h("summary.muted", { style: "cursor:pointer;font-size:13px" }, PL.t("Nhập CSV SCImago thủ công")),
        h("p.help", {}, PL.t("Giữ các cột Title, Issn, SJR, SJR Best Quartile, Categories, Sourceid.")),
        h("div.row", { style: "flex-wrap:wrap" }, rankingFile, rankingYear, rankingImport), rankingStatus));
    paintRank(false);
  }

  function mcp(b) {
    b.append(h("h3", {}, "MCP & ChatGPT"),
      h("p.help", {}, PL.t("MCP kết nối công cụ, không cấp quyền model miễn phí. ChatGPT dùng đăng nhập Codex; model và quota phụ thuộc tài khoản. Các model local/API dùng chung công cụ nghiên cứu do PhD Lab thực thi.")),
      field("PhD Lab MCP endpoint (local clients)", h("code", {}, W.location.origin + "/mcp")),
      toggle(PL.ui("MCP research tools"), cfg.mcp.expose_research, (v) => save({ mcp: { expose_research: v } })),
      toggle(PL.t("MCP write proposals (vẫn cần duyệt)"), cfg.mcp.allow_writes, (v) => save({ mcp: { allow_writes: v } })),
      h("p.help", {}, PL.t("Endpoint hiện chỉ phục vụ client local. ChatGPT hosted không thể gọi localhost. Colab MCP là server bên ngoài riêng; kết nối notebook và dataset transfer chưa được triển khai trong adapter MVP.")));
  }

  // ------------------------------------------------------------------ experiments & hardware
  function hardware(b) {
    b.append(h("h3", {}, "Remote Compute · ClearML Server"),
      toggle("ClearML Server (online)", cfg.clearml.server_enabled, (v) => save({ clearml: { server_enabled: v } }), PL.t("Cấu hình xác thực bằng clearml.conf. Colab cần truy cập được Server và artifact storage.")),
      field("ClearML Web URL", h("input.input", { value: cfg.clearml.web_url || "http://localhost:8080", onchange: (e) => save({ clearml: { web_url: e.target.value } }) })),
      h("p.help", {}, PL.t("Local GPU / Docker tiếp tục dùng runner hiện có. Colab là attended handoff: bundle được duyệt → notebook → ClearML → thu và xác minh artifacts. Chưa có upload/resume dataset hoặc chạy Colab unattended.")));
    const ru = cfg.runs, rs = cfg.resources;
    b.append(h("h3", {}, PL.t("Chạy ngầm & quyền")),
      h("p.help", {}, PL.t("Run viết code hoặc dùng GPU luôn chờ bạn Chấp nhận. Mức dưới đây chỉ áp dụng cho việc đọc / ghi bên trong dự án.")),
      field(PL.t("Tự chạy không cần hỏi"), sel([[0, PL.t("Chỉ việc chỉ-đọc (tìm tài liệu, phản biện)")], [1, PL.t("Cả việc ghi trong dự án (báo cáo, PDF)")]], ru.auto_approve_risk, (v) => save({ runs: { auto_approve_risk: +v } }))),
      h("div.grid2", {}, field(PL.t("Ngân sách mỗi run (phút)"), num(ru.max_minutes, (v) => save({ runs: { max_minutes: v } }), { min: 1, max: 1440 })),
        field(PL.t("Số lần tự phục hồi (vd OOM → giảm batch)"), num(ru.max_retries, (v) => save({ runs: { max_retries: v } }), { min: 0, max: 5 }))),
      toggle(PL.t("Tự phục hồi lỗi có cách sửa an toàn (ghi rõ thay đổi cấu hình)"), ru.auto_recover, (v) => save({ runs: { auto_recover: v } })),
      toggle(PL.t("Tìm bài báo thật (OpenAlex, Semantic Scholar, arXiv) trước khi tổng hợp /lit"), ru.web_search, (v) => save({ runs: { web_search: v } })),
      h("h3", {}, PL.t("Guard phần cứng")),
      h("p.help", {}, PL.t("RTX 3060 12 GB: không bao giờ chạy 2 job GPU cùng lúc. Có thể giảm các slot khác nếu máy chậm.")),
      h("div.grid2", {}, ...["cpu", "local_llm", "cli", "cloud"].map((k) => field({ cpu: PL.t("Job CPU đồng thời"), local_llm: PL.t("Mô hình local đồng thời"), cli: PL.t("CLI provider đồng thời"), cloud: PL.t("Gọi cloud đồng thời") }[k],
        num(ru["slot_" + k], (v) => save({ runs: { ["slot_" + k]: v } }), { min: 1, max: { cpu: 1, local_llm: 1, cli: 2, cloud: 3 }[k] })))),
      toggle(PL.t("Tự gỡ mô hình local đang rảnh khỏi VRAM khi cần GPU cho thí nghiệm"), rs.auto_unload_for_gpu, (v) => save({ resources: { auto_unload_for_gpu: v } })),
      field(PL.t("Nhiệt độ GPU tối đa (°C) — vượt thì chạy CPU"), num(rs.gpu_temp_limit_c, (v) => save({ resources: { gpu_temp_limit_c: v } }), { min: 60, max: 95 })),
      h("h3", {}, "VS Code"),
      field(PL.t("Đường dẫn VS Code (để trống = tự tìm)"), h("input.input", { value: cfg.workspace.vscode_path || "", onchange: (e) => save({ workspace: { vscode_path: e.target.value } }) })));
  }

  // ------------------------------------------------------------------ memory & context
  function memory(b) {
    const a = cfg.aiws;
    b.append(h("h3", {}, PL.t("Bộ nhớ ngữ cảnh chạy ngầm")),
      h("p.help", {}, PL.t("Ngữ cảnh dự án (đề cương, quyết định, giả thuyết, run, tài liệu) được biên dịch tự động cho mỗi câu hỏi. Việc ghi nhớ chỉ xuất hiện như đề xuất trong chat để bạn Chấp nhận / Bỏ qua.")),
      field(PL.t("Ghi nhớ"), sel([["suggest", PL.t("Đề xuất — bạn duyệt từng mục (khuyên dùng)")], ["manual", PL.t("Thủ công — chỉ khi bạn bấm Ghi nhớ")], ["auto", PL.t("Tự động có giới hạn (câu hỏi mở)")], ["off", PL.t("Tắt")]], a.memory_mode, (v) => save({ aiws: { memory_mode: v } }))),
      field(PL.t("Chế độ"), sel([["automation", PL.t("Tự động — AI tự dùng công cụ chỉ-đọc, mọi thay đổi chờ bạn duyệt")], ["manual", PL.t("Thủ công — xem ngữ cảnh trước khi gửi, duyệt mọi bước")]], a.operating_mode, (v) => save({ aiws: { operating_mode: v } }))),
      field(PL.t("Ngân sách ngữ cảnh (token)"), num(a.context_budget_tokens, (v) => save({ aiws: { context_budget_tokens: v } }), { min: 500, max: 60000, step: 500 })),
      field(PL.t("Thời gian tối đa một câu trả lời (giây)"), num(a.max_turn_s, (v) => save({ aiws: { max_turn_s: v } }), { min: 30, max: 7200 })));
  }

  // ------------------------------------------------------------------ skills
  async function skills(b) {
    b.append(h("h3", {}, PL.t("Kỹ năng")), h("p.help", {}, PL.t("Mỗi lệnh / là một file Markdown: built-in, của bạn (mọi dự án) hoặc của dự án này. Kỹ năng không cấp thêm quyền — việc rủi ro vẫn chờ bạn duyệt.")));
    const r = await PL.get("/api/skills").catch(() => ({ skills: [], errors: [] }));
    const t = h("table.grid", {}, h("tr", {}, h("th", {}, PL.t("Lệnh")), h("th", {}, PL.t("Mô tả")), h("th", {}, PL.t("Kiểu")), h("th", {}, "")));
    for (const s of r.skills) {
      t.append(h("tr", {}, h("td.mono", {}, "/" + s.name), h("td", {}, s.title, h("div.muted", { style: "font-size:12px" }, s.description)),
        h("td", {}, h("span.chip", {}, s.mode === "run" ? PL.t("chạy nền") : "chat"), " ", h("span.chip", {}, s.origin)),
        h("td", {}, ["user", "project"].includes(s.origin) ? h("button.icon", { type: "button", title: PL.t("Xoá"), html: PL.icon("trash"), onclick: async () => { if (await PL.safe(() => PL.del("/api/skills/" + s.name), PL.t("Đã xoá"))) { PL.chat.loadSkills(); b.innerHTML = ""; skills(b); } } }) : null)));
    }
    b.append(t);
    (r.errors || []).forEach((e) => b.append(h("div.err-line", {}, `${e.file}: ${e.error}`)));
    const tpl = PL.t("---\nname: tomtat\ntitle: Tóm tắt bài báo\ndescription: Tóm tắt một bài báo theo mẫu của tôi\nusage: <tên bài / file>\ncategory: research\nagent: research\nmode: chat\nrisk: 0\n---\nTóm tắt theo mẫu: vấn đề, phương pháp, dữ liệu, kết quả, hạn chế, liên hệ với đề cương của tôi.\n");
    const ta = h("textarea.input.mono", { rows: "12" }, tpl);
    const scope = sel([["project", PL.t("Chỉ dự án này")], ["user", PL.t("Mọi dự án")]], "project", () => {});
    b.append(h("h3", {}, PL.t("Tạo / sửa kỹ năng")), ta, h("div.row", { style: "margin-top:8px" }, scope, h("span.grow"),
      h("button.btn.accent", { type: "button", onclick: async () => { if (await PL.safe(() => PL.post("/api/skills", { text: ta.value, scope: scope.value }), PL.t("Đã lưu kỹ năng"))) { PL.chat.loadSkills(); b.innerHTML = ""; skills(b); } } }, PL.t("Lưu kỹ năng"))));
  }

  // ------------------------------------------------------------------ plugins from GitHub
  async function plugins(b) {
    b.append(h("h3", {}, PL.t("Plugin kỹ năng từ GitHub")),
      h("p.help", {}, PL.t("Cài kỹ năng từ bất kỳ repository GitHub nào: thư mục có SKILL.md (Agent Skills) hoặc file kỹ năng PhD Lab trong skills/. Plugin được lưu một lần trong data/plugins/ và bật / tắt riêng cho từng dự án. Không có mã nào của plugin được chạy; kỹ năng không cấp thêm quyền.")));
    const url = h("input.input", { placeholder: PL.t("https://github.com/owner/repo  (hoặc …/tree/main/skills/ten-skill)"), "aria-label": "URL repository GitHub" });
    const go = h("button.btn.accent", { type: "button", onclick: async () => {
      if (!url.value.trim()) { url.focus(); return; }
      go.disabled = true; go.textContent = PL.t("Đang tải…");
      const r = await PL.safe(() => PL.post("/api/plugins", { url: url.value.trim() }));
      go.disabled = false; go.textContent = PL.t("Cài plugin");
      if (r) { PL.toast(PL.t("Đã cài {0} · {1} kỹ năng", r.id, (r.skills || []).length)); url.value = ""; PL.chat.loadSkills(); paint(); }
    } }, PL.t("Cài plugin"));
    url.addEventListener("keydown", (e) => { if (e.key === "Enter") go.click(); });
    const list = h("div", {}, h("span.spin"));
    const suggest = h("div.row.wrap", { style: "margin:6px 0 4px" }, h("span.muted.small", {}, PL.t("Gợi ý:")),
      [["SakanaAI/AI-Scientist-v2", "https://github.com/SakanaAI/AI-Scientist-v2"], ["K-Dense scientific skills", "https://github.com/K-Dense-AI/scientific-agent-skills"],
        ["Anthropic skills", "https://github.com/anthropics/skills"]].map(([l, u]) => h("button.chip", { type: "button", onclick: () => { url.value = u; url.focus(); } }, l)));
    b.append(h("div.row", {}, url, go), suggest, list);
    async function paint() {
      const r = await PL.get("/api/plugins").catch((e) => ({ plugins: [], error: e.message }));
      list.replaceChildren();
      if (r.error) list.append(h("p.err-line", {}, r.error));
      if (!r.plugins.length) { list.append(h("p.muted", {}, PL.t("Chưa có plugin nào."))); return; }
      list.append(h("p.help", {}, PL.t("Thư mục plugin: {0}", r.root)));
      for (const p of r.plugins) {
        const skills = p.skills || [];
        list.append(h("div.plugin-card", {},
          h("div.row", {}, h("span", { html: PL.icon("plug") }), h("div.grow", {}, h("b", {}, p.owner + "/" + p.repo + (p.subdir ? "/" + p.subdir : "")),
            h("div.muted.small", {}, PL.t("{0} · commit {1} · {2} kỹ năng{3}", p.ref, String(p.commit || "").slice(0, 8), skills.length, p.adapter ? " · adapter " + p.adapter : ""))),
          h("label.switch", { title: PL.t("Bật cho dự án này") }, h("input", { type: "checkbox", checked: p.enabled || null, onchange: async (e) => { await PL.safe(() => PL.put("/api/plugins/" + p.id, { enabled: e.target.checked })); PL.chat.loadSkills(); paint(); } }), PL.t("Bật")),
          h("button.icon", { type: "button", title: PL.t("Cập nhật từ GitHub"), "aria-label": PL.t("Cập nhật từ GitHub"), html: PL.icon("sync"), onclick: async () => { if (await PL.safe(() => PL.post(`/api/plugins/${p.id}/update`), PL.t("Đã cập nhật"))) { PL.chat.loadSkills(); paint(); } } }),
          h("button.icon", { type: "button", title: PL.t("Gỡ plugin"), "aria-label": PL.t("Gỡ plugin"), html: PL.icon("trash"), onclick: async () => { if (await PL.confirm(PL.t("Gỡ plugin {0}? (thư mục được chuyển vào data/plugins/_trash)", p.id), PL.t("Gỡ"))) { await PL.safe(() => PL.del("/api/plugins/" + p.id)); PL.chat.loadSkills(); paint(); } } })),
          skills.length ? h("details", { open: skills.length <= 6 || null }, h("summary.muted.small", { style: "cursor:pointer" }, PL.t("{0} kỹ năng", skills.length)),
            h("div.list", {}, skills.map((s) => h("div.li", {}, h("input", { type: "checkbox", checked: s.enabled !== false || null, title: PL.t("Dùng kỹ năng này"), disabled: !p.enabled || null,
              onchange: async (e) => { await PL.safe(() => PL.put("/api/plugins/skills/" + encodeURIComponent(s.name), { enabled: e.target.checked })); PL.chat.loadSkills(); } }),
            h("div.m", {}, h("div.t.mono", {}, "/" + s.name), h("div.s", { style: "white-space:normal" }, s.description || s.title)))))) : h("p.muted.small", {}, PL.t("Không tìm thấy SKILL.md trong repository này.")),
          (p.errors || []).length ? h("div.err-line", {}, PL.t("{0} file không đọc được", p.errors.length)) : null));
      }
    }
    paint();
  }

  // ------------------------------------------------------------------ appearance & language
  function look(b) {
    let cur = "system";
    try { cur = W.localStorage.getItem("pl.theme") || "system"; } catch (e) { /* private mode */ }
    const ui = cfg.ui || {};
    b.append(h("h3", {}, PL.t("Giao diện")), field(PL.t("Chủ đề màu"), sel([["system", PL.t("Theo hệ thống")], ["light", PL.t("Sáng")], ["dark", PL.t("Tối")], ...PL.themes.list().map(t => [t.id, t.name])], cur, (v) => {
      PL.themes.select(v);
    })),
    field(PL.t("Font chữ của câu trả lời"), sel([["sans", PL.t("Sans-serif (Segoe UI — dễ đọc tiếng Việt)")], ["serif", PL.t("Serif (Cambria — kiểu bài báo)")]], ui.prose_font || "sans", (v) => {
      PL.setFont(v);
      save({ ui: { prose_font: v } });
    })),
    h("h3", {}, PL.t("Ngôn ngữ")),
    field(PL.t("Ngôn ngữ giao diện và câu trả lời của AI"), sel([["vi", PL.t("Tiếng Việt")], ["en", "English"]], PL.lang, async (v) => {
      if (await save({ ui: { language: v } }, v === "en" ? "Saved" : PL.t("Đã lưu"))) PL.setLang(v);
    }), PL.t("Đổi ngôn ngữ sẽ tải lại giao diện. AI trả lời bằng ngôn ngữ này trừ khi bạn viết bằng ngôn ngữ khác.")),
    h("p.help", {}, PL.t("PhD Research Lab {0} · dữ liệu dự án: {1}", cfg.version, cfg.project.data_dir || "")));
    b.querySelector("select").id = "theme-select";
    PL.themes.render(b);
  }
})(window);
