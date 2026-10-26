# Native AI Research Environment — ràng buộc thiết kế và nghiệm thu

Nguồn: checklist do chủ repository cung cấp ngày 2026-10-27, audit baseline PhD-Research-Lab v6.5.11. Đây là yêu cầu thiết kế đang hoạt động cho đợt nâng cấp core 6.6.xx, không phải báo cáo kết quả hoặc chứng nhận năng lực.

## Quy tắc áp dụng bắt buộc

1. Mọi AI agent phải đọc tài liệu này cùng AGENT.md, STATE.md, PLAN.md, DEVELOPMENT_WORKFLOW.md, RESEARCH_QUALITY_OBJECTIVES.md và ZERO_FAKE_TESTING_POLICY.md trước khi thiết kế hoặc sửa core, prompt, orchestrator, workflow, context, memory, tool, provider hoặc runtime.
2. Thứ tự chủ repository đã giao: sửa và chứng minh CI/CD tự động dev → qa → main trước; tiếp theo audit/nâng cấp core trên nhánh dev hiện có, version 6.6.xx. Quy tắc coding phải browser GitHub web và chứng minh commit đã vào main vẫn áp dụng. Không tạo nhánh phát triển khác, không bypass protection, không xóa skills/ hoặc agent/, không mất dữ liệu/nghiên cứu hay thay đổi của người dùng.
3. AI quyết định chiến lược khoa học trong phạm vi nhiệm vụ đã được cấp quyền. Code chỉ cưỡng chế authorization, sandbox, workspace isolation, resource budgets, giao thức/schema cần thiết và kiểm chứng evidence. Không thay quyết định khoa học bằng keyword, regex, phase cố định, fixed team hoặc template bắt buộc. Workflow/skill tái sử dụng phải là lựa chọn.
4. Reuse các thành phần native hiện có. Không tạo Research Engine, orchestrator, memory store, verification framework hoặc provider stack chồng lặp để đạt checklist. Không đổi tên một pipeline giả lập thành native agent.
5. Mỗi mục checklist phải có ID ổn định và được đối chiếu trong ma trận audit bằng một trong các trạng thái: PASS, FAIL, PARTIAL, NOT IMPLEMENTED, NOT VERIFIED, NOT APPLICABLE. Không tự tích các ô bên dưới thành PASS. NOT APPLICABLE cần lý do theo phạm vi, không phải cách loại bỏ một failure.
6. Mỗi kết luận phải ghi source file, function, line, runtime behavior, severity, phương pháp kiểm tra, source revision/hash, command, số case/phạm vi, evidence thực thi và giới hạn. Finding cần cách tái hiện, correction và before/after khi thích hợp. Không coi inventory, cấu hình, schema hợp lệ, mock, skip hoặc LLM tự báo thành công là real execution.
7. Sửa confirmed P0/P1 trong thành phần hiện có khi khả thi; viết/review Feature Quality Contract, behavioral regression và adversarial cases; search/review các GitHub skills phù hợp, dùng nguồn đã pin cùng license/provenance. Không sửa oracle, bỏ assertion hoặc suppress failure để lấy PASS. Giữ ledger tối đa ba failed repair cycles cho mỗi stable task/PR; không reset UAT allowance.
8. Mandatory software regression phải chạy đủ và PASS theo policy CI hiện hành. Báo production line/branch coverage bằng numerator/denominator; mục tiêu 100% chưa đo đạt thì không được tuyên bố đạt. Software PASS, actual model/tool execution và scientific L3/L4 là ba loại qualification riêng. Checklist không đổi quyền truy cập, không cấp paid-provider fallback và không mở rộng ngân sách tự động.
9. Benchmark phải định nghĩa case set, baseline/candidate, model/provider, quyền tool, compute/token/time budget, verifier, repeat/stopping rules và held-out split trước khi chạy. Giữ mọi attempt, null/negative result, failure và infrastructure blocker. Independent evaluation phải có bằng chứng độc lập; same-agent review phải được ghi rõ.
10. Chỉ gọi sản phẩm là “validated Native AI Research Environment” khi final acceptance bên dưới có real execution traces tương ứng. Không tuyên bố L3/L4, learning improvement, generalization hay multi-agent superiority khi chưa có benchmark phù hợp và evidence kiểm chứng độc lập.
11. Bảy deliverable bắt buộc: SOURCE_AUDIT_REPORT.md, REASONING_INTERFERENCE_REPORT.md, NATIVE_AGENT_RUNTIME_REPORT.md, CONTEXT_MEMORY_AUDIT.md, SCIENTIFIC_AUTONOMY_BENCHMARK.md, REGRESSION_TEST_REPORT.md, REMAINING_BLOCKERS.md. Báo cáo/ma trận phải liên kết raw evidence; chưa hoàn thành phải ghi rõ blocker và next steps.
12. Các mục yêu cầu nhiều provider, local/CLI, MATLAB/GPU/external tools phải ghi actual available/unavailable/unsupported/not-run theo môi trường thật. Không thay native CLI launch bằng vendor website, không dùng dữ liệu cá nhân để test, không đưa devtools/verification vào dependency của Research Agent runtime.

---

# Checklist nguyên văn của chủ repository

# PhD-Research-Lab v6.5.11
# NATIVE AI RESEARCH ENVIRONMENT — AUDIT & UPGRADE CHECKLIST

## 0. MỤC TIÊU CỐT LÕI

Biến PhD-Research-Lab thành một Native AI Research Environment,
nơi AI Agent được cung cấp môi trường, công cụ, bộ nhớ, tài nguyên
và quyền tự chủ để thực hiện nghiên cứu khoa học theo chỉ thị
của người dùng.

### Triết lý kiến trúc

- AI quyết định WHAT, WHY, HOW và WHEN trong phạm vi nhiệm vụ.
- Environment cung cấp WHERE, TOOLS, MEMORY, COMPUTE và EVIDENCE.
- Backend không thay AI đưa ra quyết định khoa học.
- Workflow là công cụ hỗ trợ, không phải quy trình bắt buộc.
- Prompt định hướng nhiệm vụ, không lập trình cứng cách suy luận.
- Agent được phép thay đổi chiến lược dựa trên kết quả thực tế.
- Learning phải dựa trên bằng chứng, không phải tự tuyên bố thông minh hơn.
- Không đánh đổi sandbox, bảo mật hoặc tính toàn vẹn khoa học
  để đạt quyền tự chủ.

### Định nghĩa hoàn thành

[ ] Agent có thể tiếp nhận một mục tiêu nghiên cứu bằng ngôn ngữ tự nhiên.
[ ] Agent tự phân tích mục tiêu, xây dựng giả thuyết và chiến lược.
[ ] Agent tự khám phá các công cụ và tài nguyên được cấp quyền.
[ ] Agent tự lựa chọn công cụ mà không cần workflow cố định.
[ ] Agent thực hiện được nhiều vòng reasoning → action → observation.
[ ] Agent tự phát hiện và xử lý lỗi thực nghiệm.
[ ] Agent có thể thay đổi hoặc bác bỏ chiến lược ban đầu.
[ ] Agent lưu và tái sử dụng kiến thức giữa các phiên.
[ ] Agent phân biệt giả thuyết, bằng chứng và kết luận.
[ ] Agent tạo được scientific artifacts có thể tái lập.
[ ] Agent hoạt động trên nhiều provider/model khác nhau.
[ ] Các năng lực trên được chứng minh bằng real execution.

---

# P0 — CRITICAL ARCHITECTURAL CORRECTIONS

## 1. PROMPT ARCHITECTURE

### 1.1 Audit toàn bộ prompt

[ ] Tìm tất cả system prompts.
[ ] Tìm tất cả developer/agent/role prompts.
[ ] Tìm tất cả workflow-specific prompts.
[ ] Tìm tất cả skill instructions.
[ ] Tìm mọi đoạn prompt được hardcode trong backend.
[ ] Tìm logic tự động inject prompt.
[ ] Tìm các cơ chế thay đổi prompt theo keyword.
[ ] Tìm các prompt giới hạn cách agent giải quyết vấn đề.
[ ] Kiểm tra thứ tự ưu tiên instruction.
[ ] Kiểm tra prompt khi chuyển đổi model/provider.

### 1.2 Loại bỏ reasoning interference

[ ] Không tự động kích hoạt workflow dựa trên keyword đơn giản.
[ ] Không ép agent vào một phương pháp nghiên cứu cụ thể.
[ ] Không bắt agent tuân theo một chuỗi bước khoa học cố định.
[ ] Không ép mọi nhiệm vụ phải sử dụng multi-agent.
[ ] Không ép mọi nghiên cứu phải đi qua literature review.
[ ] Không ép mọi nhiệm vụ phải tạo experiment.
[ ] Không sử dụng regex để thay thế quyết định khoa học của AI.
[ ] Không tự động thay đổi mục tiêu nghiên cứu của người dùng.
[ ] Không âm thầm cắt bỏ các ràng buộc khoa học trong prompt.
[ ] Không bắt model trả JSON nếu không cần thiết cho giao tiếp công cụ.

### 1.3 Thiết kế prompt tối giản

[ ] Xây dựng minimal core agent instruction.
[ ] Tách user intent khỏi execution policy.
[ ] Tách scientific guidance khỏi operational restrictions.
[ ] Cho phép agent tự lựa chọn phương pháp.
[ ] Cho phép agent chủ động đề xuất công cụ bổ sung.
[ ] Cho phép agent chủ động yêu cầu thêm thông tin.
[ ] Cho phép agent tự tổ chức các bước nghiên cứu.
[ ] Chỉ sử dụng structured output tại boundary cần thiết.
[ ] Đảm bảo nội dung lấy từ tool/memory không thể ghi đè quyền hạn.
[ ] Không để prompt framework chiếm phần lớn context window.

### Acceptance Criteria

[ ] Cùng một nhiệm vụ có thể tạo ra các chiến lược hợp lý khác nhau.
[ ] Agent không bị backend ép lựa chọn một workflow cố định.
[ ] Không mất yêu cầu quan trọng khi prompt đi qua gateway.
[ ] Prompt hoạt động nhất quán trên các provider được hỗ trợ.
[ ] Có regression tests cho instruction hierarchy.
[ ] Có adversarial tests phát hiện prompt injection.
[ ] Có before/after evidence chứng minh đã giảm reasoning interference.

---

## 2. AGENT-NATIVE ORCHESTRATION

### 2.1 Phân tách trách nhiệm

[ ] Agent quyết định chiến lược nghiên cứu.
[ ] Orchestrator điều phối việc thực thi.
[ ] Tool runtime thực thi các hành động được cấp quyền.
[ ] Memory system cung cấp tri thức và trạng thái.
[ ] Evidence system quản lý nguồn và kết quả.
[ ] Policy engine quản lý authorization, sandbox và budget.
[ ] Backend không tự đưa ra kết luận khoa học thay agent.

### 2.2 Dynamic planning

[ ] Agent tự tạo research plan.
[ ] Agent tự điều chỉnh plan.
[ ] Agent có thể bỏ plan cũ.
[ ] Agent có thể tạo plan mới từ kết quả quan sát.
[ ] Agent có thể bỏ qua các bước không cần thiết.
[ ] Agent có thể quay lại bước trước.
[ ] Agent có thể thực hiện exploratory research.
[ ] Agent có thể chuyển từ exploration sang exploitation.
[ ] Agent có thể tự quyết định sử dụng single-agent hoặc multi-agent.
[ ] Workflow templates chỉ là optional capabilities.

### 2.3 Không áp đặt giới hạn suy luận tùy tiện

[ ] Audit hardcoded maximum planning iterations.
[ ] Audit hardcoded replan generation limits.
[ ] Audit hardcoded number of research phases.
[ ] Audit forced role transitions.
[ ] Audit forced workflow termination.
[ ] Audit fixed agent-role assignments.
[ ] Chuyển giới hạn tùy tiện thành configurable resource budgets.
[ ] Cho phép agent xin mở rộng budget khi có lý do.
[ ] Vẫn duy trì hard limits cho chi phí, thời gian và an toàn.

### Acceptance Criteria

[ ] Agent tự thiết kế được workflow mới.
[ ] Agent có thể thay đổi workflow khi thực nghiệm thất bại.
[ ] Không cần developer tạo workflow riêng cho từng loại nghiên cứu.
[ ] Workflow không bị khóa vào một domain khoa học.
[ ] Có execution traces chứng minh dynamic replanning thực sự xảy ra.

---

## 3. TRUE AGENT EXECUTION LOOP

### 3.1 Native agent loop

[ ] Implement/verify model reasoning step.
[ ] Implement/verify tool discovery.
[ ] Implement/verify tool selection.
[ ] Implement/verify tool invocation.
[ ] Implement/verify observation ingestion.
[ ] Implement/verify reflection/replanning.
[ ] Implement/verify error recovery.
[ ] Implement/verify termination decision.
[ ] Implement/verify human approval checkpoints.
[ ] Implement/verify checkpoint and resume.

### 3.2 Tool capabilities

[ ] Agent có thể liệt kê các tool hiện có.
[ ] Agent hiểu input/output schema của từng tool.
[ ] Agent có thể phối hợp nhiều tool.
[ ] Agent có thể viết code phục vụ thực nghiệm.
[ ] Agent có thể chạy và kiểm tra code.
[ ] Agent có thể sửa code khi thực nghiệm thất bại.
[ ] Agent có thể phân tích kết quả chạy.
[ ] Agent có thể sử dụng external tools qua adapter.
[ ] Tool failure không làm mất toàn bộ research context.
[ ] Tool timeout không khiến agent báo thành công giả.

### 3.3 Real execution

[ ] Test với ít nhất một real LLM provider.
[ ] Test với local model.
[ ] Test với CLI model.
[ ] Test với multi-step coding task.
[ ] Test với scientific computation.
[ ] Test với tool failures.
[ ] Test với execution interruption.
[ ] Test checkpoint/resume.
[ ] Test provider switching.
[ ] Không sử dụng mock result để chứng nhận real execution.

### Acceptance Criteria

[ ] Một nhiệm vụ có thể cần nhiều lần gọi model và tool.
[ ] Agent tự sửa lỗi thay vì dừng ngay ở lần thất bại đầu tiên.
[ ] Execution trace thể hiện rõ mọi hành động thực tế.
[ ] Agent không được tuyên bố đã thực nghiệm nếu tool chưa chạy.
[ ] Agent không được tạo dữ liệu khoa học giả để hoàn thành nhiệm vụ.

---

## 4. CONTEXT ENGINEERING & MEMORY

### 4.1 Context fidelity

[ ] Audit toàn bộ context compiler.
[ ] Audit history token budget.
[ ] Audit context ranking.
[ ] Audit prompt clipping.
[ ] Audit summarization pipeline.
[ ] Audit conversation compaction.
[ ] Audit retrieval truncation.
[ ] Audit cross-agent context handoff.
[ ] Audit context propagation qua provider gateway.

### 4.2 Không làm mất tri thức quan trọng

[ ] Bảo toàn user research objectives.
[ ] Bảo toàn scientific constraints.
[ ] Bảo toàn mathematical equations.
[ ] Bảo toàn experimental assumptions.
[ ] Bảo toàn negative findings.
[ ] Bảo toàn unresolved questions.
[ ] Bảo toàn research decisions.
[ ] Bảo toàn evidence references.
[ ] Bảo toàn provenance.
[ ] Bảo toàn trạng thái thực nghiệm khi chuyển phiên.

### 4.3 Long-term research memory

[ ] Episodic memory.
[ ] Semantic memory.
[ ] Procedural memory.
[ ] Research project memory.
[ ] Experiment history.
[ ] Research decision history.
[ ] Failure memory.
[ ] Scientific evidence memory.
[ ] Cross-session retrieval.
[ ] Cross-agent knowledge sharing.
[ ] Memory versioning.
[ ] Memory contradiction detection.
[ ] Memory confidence tracking.
[ ] Memory provenance tracking.

### 4.4 Memory retrieval

[ ] Kết hợp semantic retrieval và exact retrieval.
[ ] Hỗ trợ tìm kiếm theo metadata.
[ ] Hỗ trợ tìm kiếm theo research project.
[ ] Hỗ trợ tìm kiếm theo experiment.
[ ] Hỗ trợ truy xuất nguyên văn công thức.
[ ] Hỗ trợ truy xuất negative results.
[ ] Hỗ trợ kiểm tra nguồn gốc nội dung.
[ ] Không để summary thay thế hoàn toàn original evidence.
[ ] Không để memory injection ghi đè system instructions.

### Acceptance Criteria

[ ] Agent tiếp tục được một nghiên cứu sau khi restart.
[ ] Agent nhớ chính xác giả thuyết từng bị bác bỏ.
[ ] Agent truy xuất đúng công thức và tham số cũ.
[ ] Agent không tự bịa ký ức.
[ ] Agent có thể giải thích nguồn gốc từng memory.
[ ] Long-session regression tests PASS.
[ ] Cross-session retrieval tests PASS.

---

## 5. SCIENTIFIC RESEARCH INTEGRITY

### 5.1 Scientific evidence

[ ] Phân biệt hypothesis và verified finding.
[ ] Phân biệt simulation và physical measurement.
[ ] Phân biệt model prediction và experimental result.
[ ] Phân biệt citation thật và citation chưa xác minh.
[ ] Mỗi kết luận quan trọng liên kết được với evidence.
[ ] Lưu experimental configurations.
[ ] Lưu datasets và versions.
[ ] Lưu scripts và source revisions.
[ ] Lưu execution logs.
[ ] Lưu random seeds khi phù hợp.

### 5.2 Scientific verification

[ ] Agent có thể kiểm tra giả thuyết.
[ ] Agent có thể thiết kế experiment.
[ ] Agent có thể xác định evaluation metrics.
[ ] Agent có thể so sánh baseline.
[ ] Agent có thể phát hiện kết quả bất thường.
[ ] Agent có thể tìm alternative explanations.
[ ] Agent có thể nhận ra insufficient evidence.
[ ] Agent có thể chủ động yêu cầu independent verification.
[ ] Agent có thể bác bỏ kết luận ban đầu.
[ ] Agent không bị ép đưa ra positive findings.

### Acceptance Criteria

[ ] Có thể tái lập experiment từ artifacts.
[ ] Không có fabricated citations.
[ ] Không có fabricated experimental measurements.
[ ] Negative results được lưu như positive results.
[ ] Unsupported conclusions được đánh dấu rõ ràng.

---

# P1 — ADVANCED NATIVE CAPABILITIES

## 6. MULTI-AGENT COLLABORATION

[ ] Agent có thể tự nhận biết khi nào cần cộng tác.
[ ] Agent có thể tự đề xuất agent roles.
[ ] Agent có thể tự chia research tasks.
[ ] Agent có thể tự thay đổi team composition.
[ ] Agent có thể yêu cầu independent review.
[ ] Agent có thể phân công parallel experiments.
[ ] Agent có thể tổng hợp conflicting findings.
[ ] Agent có thể giải quyết disagreement bằng evidence.
[ ] Agent có thể loại bỏ agent không còn cần thiết.
[ ] Không bắt buộc sử dụng fixed research team.
[ ] Không để agent count trở thành thước đo intelligence.
[ ] Có shared workspace và task ownership.
[ ] Có artifact handoff.
[ ] Có cơ chế chống race condition.
[ ] Có cơ chế chống ghi đè kết quả giữa các agent.

### Acceptance Criteria

[ ] Multi-agent có thể vượt single-agent trong ít nhất
    một benchmark được kiểm soát.
[ ] Team configuration do agent đề xuất được thực thi thật.
[ ] Handoff không làm mất research context.
[ ] Không có fabricated collaboration.

---

## 7. OPEN-ENDED CAPABILITY LEARNING

### 7.1 Learning mechanism

[ ] Agent tự nhận diện capability gaps.
[ ] Agent tự đề xuất new tools.
[ ] Agent tự đề xuất new skills.
[ ] Agent có thể xây dựng reusable procedures.
[ ] Agent có thể học từ failed experiments.
[ ] Agent có thể lưu successful strategies.
[ ] Agent có thể truy xuất reusable procedures.
[ ] Agent có thể cải thiện procedures theo feedback.
[ ] Agent có thể phát hiện procedure lỗi thời.
[ ] Agent có thể rollback skill không hiệu quả.

### 7.2 Learning validation

[ ] Mỗi learned skill có version.
[ ] Mỗi learned skill có provenance.
[ ] Mỗi learned skill có evaluation result.
[ ] Mỗi learned skill có applicability conditions.
[ ] Không tự động tin tưởng skill do agent tạo ra.
[ ] Test skill trên held-out tasks.
[ ] So sánh với previous skill version.
[ ] Chỉ promote skill khi có measurable improvement.
[ ] Không nhầm memory accumulation với model weight training.

### Acceptance Criteria

[ ] Agent sử dụng được kinh nghiệm cũ cho nhiệm vụ mới.
[ ] Có bằng chứng improvement trước/sau learning.
[ ] Skill thất bại có thể bị loại bỏ.
[ ] Agent không tự chứng nhận năng lực của chính mình.

---

## 8. NATIVE RESEARCH WORKSPACE

[ ] Workspace được quản lý theo project.
[ ] Agent có quyền đọc/ghi trong phạm vi được cấp phép.
[ ] Có file versioning.
[ ] Có experiment directories.
[ ] Có datasets management.
[ ] Có artifact management.
[ ] Có execution logs.
[ ] Có checkpoint snapshots.
[ ] Có reproducibility manifests.
[ ] Có scientific computation runtime.
[ ] Có hỗ trợ Python.
[ ] Có hỗ trợ MATLAB hoặc adapter tương đương nếu được cấu hình.
[ ] Có hỗ trợ simulation tools.
[ ] Có hỗ trợ GPU workloads nếu tài nguyên cho phép.
[ ] Có khả năng chạy Docker/container workloads.
[ ] Có resource monitoring.
[ ] Có quyền kiểm soát destructive operations.
[ ] Có workspace isolation giữa các project.

---

## 9. MODEL & PROVIDER INDEPENDENCE

[ ] Audit toàn bộ model gateway.
[ ] Hỗ trợ API-based providers.
[ ] Hỗ trợ CLI-based providers.
[ ] Hỗ trợ local inference providers.
[ ] Hỗ trợ external agent runtime qua adapter.
[ ] Kiểm tra Hermes Agent integration.
[ ] Không để model-specific prompt phá vỡ core architecture.
[ ] Không phụ thuộc vào một model duy nhất.
[ ] Chuẩn hóa tool capability discovery.
[ ] Chuẩn hóa error reporting.
[ ] Chuẩn hóa execution tracing.
[ ] Không tuyên bố tương thích nếu chưa thực thi thành công.
[ ] Kiểm tra provider fallback.
[ ] Kiểm tra context transfer khi đổi provider.
[ ] Theo dõi model usage và resource costs.

---

## 10. RELIABILITY & SECURITY

[ ] Sandbox isolation.
[ ] Workspace access control.
[ ] Secrets isolation.
[ ] Permission boundaries.
[ ] Human approval for sensitive actions.
[ ] Network permissions.
[ ] Compute budget enforcement.
[ ] Execution time limits.
[ ] Resource quota enforcement.
[ ] Audit logging.
[ ] Prompt injection defense.
[ ] Untrusted tool output isolation.
[ ] Rollback support.
[ ] Checkpoint/resume.
[ ] Recovery after container restart.
[ ] Recovery after provider failure.
[ ] Recovery after network interruption.
[ ] Không cho agent tự ý vượt quyền hạn.
[ ] Không đánh đồng unrestricted reasoning với unrestricted execution.

---

# P2 — SCIENTIFIC AUTONOMY VALIDATION

## 11. REAL RESEARCH BENCHMARK

Xây dựng benchmark không phụ thuộc vào việc agent
có tuân theo một workflow template hay không.

### Benchmark A — Open-ended reasoning

[ ] Giao research question chưa có workflow định nghĩa trước.
[ ] Agent tự xây dựng strategy.
[ ] Agent tự lựa chọn tools.
[ ] Agent tự phát hiện missing information.
[ ] Đánh giá strategy quality bằng independent evaluator.

### Benchmark B — Autonomous experimentation

[ ] Giao một bài toán có thể thực nghiệm.
[ ] Agent tự viết experiment code.
[ ] Agent tự chạy experiment.
[ ] Agent tự đánh giá kết quả.
[ ] Agent tự sửa lỗi.
[ ] Agent tự điều chỉnh phương pháp.
[ ] Xác minh actual execution logs.

### Benchmark C — Long-horizon research

[ ] Nghiên cứu qua nhiều sessions.
[ ] Có restart environment.
[ ] Có context compaction.
[ ] Có thay đổi research objectives.
[ ] Có conflicting evidence.
[ ] Agent giữ được scientific continuity.
[ ] Agent không quên negative findings.

### Benchmark D — Learning transfer

[ ] Training/experience phase.
[ ] Held-out evaluation phase.
[ ] So sánh agent có memory và không có memory.
[ ] So sánh skill reuse và no skill reuse.
[ ] Đánh giá improvement có ý nghĩa.
[ ] Không sử dụng dữ liệu benchmark để tự tối ưu trực tiếp
    rồi tuyên bố generalization.

### Benchmark E — Multi-agent research

[ ] Single-agent baseline.
[ ] Multi-agent configuration.
[ ] Same model budget.
[ ] Same tool permissions.
[ ] Same experimental resources.
[ ] Independent evaluation.
[ ] So sánh quality/cost/latency.

---

# 12. SOFTWARE TEST REQUIREMENTS

[ ] Backend unit tests.
[ ] Backend integration tests.
[ ] Backend end-to-end tests.
[ ] Frontend regression tests.
[ ] Browser E2E tests.
[ ] Provider contract tests.
[ ] Real provider smoke tests.
[ ] Tool execution tests.
[ ] Memory persistence tests.
[ ] Context fidelity tests.
[ ] Workflow flexibility tests.
[ ] Multi-agent coordination tests.
[ ] Scientific evidence tests.
[ ] Adversarial prompt tests.
[ ] Recovery tests.
[ ] Cross-platform tests.

### Testing policy

- Không thay real execution bằng mock để chứng nhận năng lực.
- Mock được phép dùng cho isolated unit tests.
- Không sửa test chỉ để biến failure thành PASS.
- Không skip test thất bại mà không báo cáo.
- Không fabricated benchmark results.
- Không tuyên bố 100% coverage nếu chưa đo đầy đủ.
- Phân biệt code coverage với behavioral coverage.
- Phân biệt software correctness với scientific autonomy.

---

# 13. IMPLEMENTATION PRIORITY

## Phase 1 — P0

[ ] Fix reasoning interference.
[ ] Fix prompt architecture.
[ ] Fix dynamic planning.
[ ] Verify genuine agent execution.
[ ] Fix context fidelity.
[ ] Fix evidence integrity.

## Phase 2 — P1

[ ] Improve multi-agent collaboration.
[ ] Implement evidence-backed learning.
[ ] Improve native workspace capabilities.
[ ] Improve provider independence.
[ ] Harden reliability and security.

## Phase 3 — P2

[ ] Run scientific autonomy benchmark.
[ ] Run long-horizon research benchmark.
[ ] Run learning-transfer evaluation.
[ ] Compare single-agent vs multi-agent.
[ ] Identify remaining scientific autonomy limitations.

---

# 14. CODEX EXECUTION INSTRUCTIONS

You are responsible for auditing and upgrading the actual
PhD-Research-Lab codebase, branch `dev`, version 6.5.11.

## Mandatory workflow

1. Inspect the current source code and architecture.
2. Identify implementation evidence for each checklist item.
3. Mark each item as:
   - PASS
   - FAIL
   - PARTIAL
   - NOT IMPLEMENTED
   - NOT VERIFIED
   - NOT APPLICABLE
4. Provide exact source file and line references.
5. Prioritize confirmed P0 defects.
6. Fix defects in existing components where practical.
7. Avoid introducing redundant frameworks or workflow engines.
8. Add appropriate regression tests.
9. Perform real agent/tool execution tests.
10. Document evidence and unresolved blockers.

## Non-negotiable constraints

- Do not replace intelligence with hardcoded workflows.
- Do not replace agent autonomy with deterministic keyword routing.
- Do not build unnecessary abstraction layers.
- Do not create fake agents that only wrap one LLM call.
- Do not fabricate tool execution.
- Do not fabricate scientific results.
- Do not compromise sandbox security.
- Do not silently discard scientific context.
- Do not break existing user workflows.
- Do not mark incomplete tasks as completed.

## Required deliverables

[ ] SOURCE_AUDIT_REPORT.md
[ ] REASONING_INTERFERENCE_REPORT.md
[ ] NATIVE_AGENT_RUNTIME_REPORT.md
[ ] CONTEXT_MEMORY_AUDIT.md
[ ] SCIENTIFIC_AUTONOMY_BENCHMARK.md
[ ] REGRESSION_TEST_REPORT.md
[ ] REMAINING_BLOCKERS.md

Each completed item must include:

- Source code reference
- Identified issue or verified behavior
- Applied correction, if needed
- Test method
- Actual execution evidence
- Before/after comparison, where relevant
- Remaining limitations

## Final acceptance gate

PhD-Lab is considered a validated Native AI Research Environment
only when:

[ ] An AI agent can independently plan a research task.
[ ] The agent can discover and use authorized tools.
[ ] The agent can execute and analyze real experiments.
[ ] The agent can change research strategies dynamically.
[ ] The agent can retain scientific context across sessions.
[ ] The agent can reproduce and verify its findings.
[ ] The system does not unnecessarily override model reasoning.
[ ] The system enforces operational safety and resource budgets.
[ ] The complete behavior is demonstrated by real execution traces.

Passing software unit tests alone is NOT sufficient.

L3/L4 scientific autonomy must be evaluated separately.
Do not claim L3 or L4 without a defined benchmark and
independently verifiable evidence.

# END OF CHECKLIST

