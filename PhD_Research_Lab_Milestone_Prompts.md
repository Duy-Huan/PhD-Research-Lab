# PhD Research Lab — Migration Milestones & Claude Code Prompts

> **Mục tiêu:** Phát triển PhD Research Lab thành một **Research Operating System (Research OS)** bằng cách giữ lại phần tạo giá trị nghiên cứu và tích hợp các nền tảng đã trưởng thành như VS Code, Git, Docker, Jupyter và ClearML.
>
> **Cách dùng:** Mở repository trong VS Code, gửi prompt từng milestone cho Claude Code theo đúng thứ tự. Không chạy đồng thời các milestone có thể sửa cùng một nhóm file. Sau mỗi milestone, kiểm thử, rà soát thay đổi và commit trước khi chuyển tiếp.

---

## 1. Nguyên tắc kiến trúc

- Giữ và phát triển phần tạo giá trị nghiên cứu: **Research Core, Context Memory, AI Agents, scientific evaluation, research workflow và evidence traceability**.
- Tích hợp công cụ có sẵn thay vì tự xây lại IDE, experiment tracker hoặc nền tảng hạ tầng.
- VS Code là coding workspace; ClearML là experiment tracking/task platform; Docker là môi trường thực thi; Jupyter là notebook.
- PhD Research Lab là **control plane / Research OS** kết nối các nền tảng và lưu ngữ cảnh nghiên cứu.
- Mỗi milestone phải có acceptance criteria, kiểm thử phù hợp, báo cáo thay đổi và trạng thái rõ ràng.
- Không báo cáo thành công nếu thao tác chưa được thực thi và xác minh.
- Không xóa dữ liệu hay thay đổi lớn trước khi kiểm tra hành vi hiện tại và có kế hoạch rollback.

## 2. Lộ trình tổng thể

| Milestone | Trọng tâm | Kết quả cần đạt |
|---|---|---|
| M1 | Audit repository và kiến trúc | Hiểu hiện trạng, rủi ro và kế hoạch migration được duyệt |
| M2 | Integration Layer | Adapter/interface để tách Research Core khỏi nhà cung cấp cụ thể |
| M3 | VS Code + Git + Docker + Jupyter | Workspace nghiên cứu thực tế và môi trường có thể tái lập |
| M4 | ClearML | Theo dõi run, metrics, artifacts và task từ PhD Lab |
| M5 | Deep Learning Lab | Workflow cấu hình → training → evaluation → so sánh |
| M6 | Frontend Research Control Center | Điều phối research, timeline, experiments và integrations |
| M7 | Model Serving foundation | Chuẩn bị/triển khai serving phù hợp với môi trường thật |
| M8 | End-to-end validation | Kiểm chứng workflow và hoàn thiện tài liệu |

**Kế hoạch cơ sở:** khoảng 8 tuần, tương ứng mỗi tuần một milestone. Đây là mục tiêu lập kế hoạch, không phải cam kết hoàn thành. Với 12–20 giờ cuối tuần, hãy kéo dài milestone nếu cần.

---

# MILESTONE 1 — Audit & Architecture Plan

**Mục tiêu:** Hiểu codebase trước khi sửa; tránh viết lại chức năng đang hoạt động.

## Prompt cho Claude Code

You are the senior software architect responsible for evolving my existing PhD Research Lab into a modular Research Operating System.

### Context
The repository already contains an existing application. It may include a frontend, backend, research workflows, AI agents, Context Memory, a Python environment, Docker/sandbox execution, and experimental Deep Learning features. Do not assume any component exists or works until you inspect it.

My strategy is to integrate mature platforms instead of rebuilding generic infrastructure:
- VS Code for the coding workspace
- Git and GitHub for source control
- Docker and Dev Containers for reproducible environments
- Jupyter for notebooks
- ClearML for experiment tracking and task orchestration
- Optional future integrations: vLLM, BentoML, KServe and Kubernetes

The unique value of my product should remain its Research Core, Context Memory, research workflow, AI-agent orchestration, scientific evaluation, and traceability between evidence and conclusions.

### Tasks
1. Inspect the repository structure, entry points, dependencies, configuration, database, API, frontend, tests, and deployment setup.
2. Identify the existing implementation of:
   - Research projects and research questions
   - Papers, hypotheses, datasets and models
   - Context Memory
   - AI agents and agent orchestration
   - Deep Learning Lab
   - Python sandbox and Docker
   - Experiment tracking and results
   - Workspace and frontend navigation
3. Classify every relevant subsystem as KEEP, ADAPT, REPLACE, REMOVE, or UNKNOWN. Justify each classification with actual repository evidence.
4. Identify duplicate functionality that should be delegated to external platforms.
5. Design a target architecture with explicit module boundaries and integration adapters.
6. Identify migration risks, breaking changes, missing capabilities and dependency constraints.
7. Propose a phased implementation plan with dependencies and measurable acceptance criteria.
8. Record baseline build, test and runtime status where feasible.

### Deliverables
Create or update:
- `ARCHITECTURE_AUDIT.md`
- `ARCHITECTURE.md`
- `MIGRATION_PLAN.md`
- `INTEGRATION_STATUS.md`

### Strict rules
- AUDIT ONLY: do not perform broad refactoring or delete code.
- Do not invent repository capabilities.
- Preserve existing behavior and user data.
- Never expose secrets in generated documentation.
- Run existing tests only when safe and record failures accurately.
- Cite actual file paths and relevant code symbols in the audit.
- End with a concise report: current state, target state, top risks, proposed milestone order, and exact next steps.

Do not start Milestone 2 until the audit and architecture proposal are complete.

## Acceptance criteria
- Audit reports refer to actual repository files and symbols.
- Current build/test status is recorded where feasible.
- The user can review and approve the migration plan before major changes.

---

# MILESTONE 2 — Integration Architecture

**Mục tiêu:** Tạo lớp tích hợp để PhD Lab không phụ thuộc trực tiếp vào một nền tảng cụ thể.

## Prompt cho Claude Code

Implement the integration foundation described in the approved architecture and repository audit.

### Objectives
Create a modular integration layer that separates the Research Core from external infrastructure providers.

Potential interfaces, adapted to the existing language and framework:
- `IDEAdapter`
- `ExecutionBackend`
- `ExperimentBackend`
- `GitProvider`
- `NotebookProvider`
- `ModelRegistry`
- `ModelServingBackend`
- `StorageBackend`
- `ComputeBackend`

Do not create abstractions for every possible future technology without a concrete need. Prioritize interfaces required by the next milestones.

### Requirements
1. Follow the existing project conventions and dependency-injection patterns.
2. Define clear request/response schemas, configuration contracts and error handling.
3. Provide health checks and integration capability/status reporting.
4. Support disabled, unconfigured and unavailable integrations gracefully.
5. Keep external service credentials on the backend or in secure environment configuration.
6. Do not hard-code secrets, machine-specific paths or URLs.
7. Preserve the current application behavior and public API unless an approved migration requires a change.
8. Add unit tests for adapter contracts, invalid configuration, timeouts and unavailable services.
9. Document configuration using sanitized examples.
10. Do not implement fake integrations that report success without performing real operations.

### Deliverables
- Integration interfaces and implementations needed for subsequent milestones
- Configuration and validation
- Adapter contract tests
- `INTEGRATION_STATUS.md`
- Updates to `DEVELOPMENT.md`

### Acceptance criteria
- Existing application builds and tests remain healthy.
- The Research Core can call an integration through its interface rather than importing vendor-specific code throughout the application.
- Missing optional integrations do not crash unrelated functionality.
- All changes are committed as one logically isolated milestone after validation.

Inspect first, implement incrementally, test, and summarize modified files and known limitations.

---

# MILESTONE 3 — Developer Workspace Integration

**Mục tiêu:** Dùng công cụ có sẵn thay vì tự xây IDE, terminal hay notebook editor.

## Prompt cho Claude Code

Integrate the existing PhD Research Lab with the user's real development environment.

### Target tools
- VS Code or a compatible installed VS Code build
- Git, with optional GitHub integration
- Docker Engine/Desktop and Dev Containers where available
- Jupyter Notebook/JupyterLab where useful

### Tasks
1. Inspect the current operating system, workspace layout, application architecture and existing sandbox implementation.
2. Create a Workspace model containing project ID, repository path, Git branch, environment configuration, and integration status.
3. Implement safe actions to:
   - Open a project in VS Code
   - Inspect Git status and recent commits
   - Initialize or connect a Git repository when explicitly requested
   - Validate Docker availability
   - Create or validate a project-specific development environment
   - Open or launch Jupyter when configured
4. Generate reusable project templates for Python research and deep learning, using pinned dependencies where practical.
5. Provide optional Dev Container configuration and GPU configuration documentation.
6. Preserve the existing sandbox. Do not replace it until equivalent behavior has been verified.
7. Use explicit allowlists for filesystem operations and validate all user-provided paths.
8. Avoid arbitrary shell command execution through unauthenticated frontend endpoints.
9. Clearly distinguish an installed application from one that is unavailable or not configured.
10. Add setup instructions for Windows 11, with WSL2/Docker guidance only where supported by the current implementation.

### UI
Add workspace actions such as:
- Open in VS Code
- View Git status
- Open Terminal
- Launch Jupyter
- Check Docker

Do not build a browser-based clone of VS Code.

### Acceptance criteria
A research project can be associated with a real local repository and environment; VS Code opens the correct workspace; Git and Docker status are accurate; unavailable tools produce actionable errors.

Test the actual available environment. Do not claim that an operation succeeded if it was only mocked.

---

# MILESTONE 4 — ClearML Experiment Backend

**Mục tiêu:** ClearML quản lý experiment, metrics và artifacts; PhD Lab quản lý ý nghĩa khoa học.

## Prompt cho Claude Code

Integrate ClearML into the existing PhD Research Lab through the `ExperimentBackend` abstraction.

### Architecture
PhD Research Lab owns:
- Research questions and hypotheses
- Research plans and experiment intent
- Scientific conclusions and decisions
- Context Memory and research timeline
- AI interpretation and evidence traceability

ClearML owns the experiment execution/tracking capabilities it supports:
- Tasks and runs
- Hyperparameters and configuration
- Metrics and scalar logs
- Checkpoints and artifacts
- Task status and experiment history

### Tasks
1. Inspect the current experiment schema and map it to ClearML entities without duplicating all ClearML functionality.
2. Implement a ClearML adapter using the official supported SDK/API.
3. Support configurable ClearML Server URL, API credentials and file-server configuration.
4. Provide connection validation and a clear integration health status.
5. Support creating or associating a task, recording a run, synchronizing metrics and linking artifacts.
6. Persist external references such as ClearML task IDs in PhD Lab's research entities.
7. Handle retries, timeouts, duplicate requests and unavailable ClearML services.
8. Synchronize state safely; do not silently overwrite research conclusions or user-authored data.
9. Add a small real integration test that can be enabled when ClearML is configured, plus unit tests using controlled mocks.
10. Document local/self-hosted deployment options, security considerations and setup steps.

### UI
Show research-relevant information:
- Experiment status
- Best/current metrics
- Recent runs
- Linked artifacts
- ClearML task reference
- Open in ClearML action

Do not clone the ClearML dashboard.

### Acceptance criteria
A real configured training run can be linked to a research hypothesis, tracked in ClearML, and retrieved by PhD Lab with its task ID, metrics and artifacts.

Do not report successful synchronization unless verified. If ClearML is not available, show setup instructions and preserve unrelated functionality.

---

# MILESTONE 5 — Deep Learning Research Workflow

**Mục tiêu:** Hoàn thiện workflow phát triển mô hình; không viết lại tracking mà ClearML đã đảm nhiệm.

## Prompt cho Claude Code

Upgrade the existing Deep Learning Lab into a research-oriented model development workflow integrated with the established execution and experiment backends.

### Core capabilities
1. Model and experiment configuration
2. Dataset and preprocessing configuration
3. Training configuration
4. Fine-tuning configuration
5. Evaluation and comparison
6. Reproducibility and artifact tracking
7. AI-assisted code generation and analysis, with human approval gates

### Tasks
1. Audit the current Deep Learning Lab before modifying it.
2. Reuse the existing model configuration, code-generation, sandbox and evaluation capabilities wherever practical.
3. Define a structured experiment specification including:
   - Research question and hypothesis
   - Dataset/version and preprocessing
   - Model architecture and initialization
   - Training hyperparameters
   - Random seeds
   - Runtime/environment requirements
   - Evaluation metrics
   - Expected outputs
4. Support a controlled workflow: design → validate configuration → generate or update code → review → execute → evaluate → compare → save evidence.
5. Integrate ClearML through `ExperimentBackend` instead of building a second tracking database for the same run data.
6. Keep source code and configuration versioned in Git.
7. Support GPU capability detection and graceful CPU fallback where practical.
8. Validate GPU access and memory limits before starting costly training jobs when possible.
9. Add a baseline training example that can run in the available environment.
10. Add evaluation reports and structured results that can be linked to Context Memory.
11. Do not execute AI-generated code without appropriate validation, isolation and user authorization.
12. Do not promise automatic model architecture discovery or reliable research novelty without an implemented and tested method.

### Acceptance criteria
A user can define a model experiment, validate the configuration, execute a real training job, track it through ClearML, compare evaluation results, and save the research conclusion with links to the evidence.

Deliver an example project, tests, documentation and a list of unsupported capabilities.

---

# MILESTONE 6 — Research Control Center Frontend

**Mục tiêu:** Frontend là nơi điều phối nghiên cứu, không phải bản sao của VS Code hoặc ClearML.

## Prompt cho Claude Code

Redesign the existing PhD Research Lab frontend around research workflows while preserving working functionality and the current technology stack.

### Design principles
- Research-first, not infrastructure-first
- Clear navigation and consistent visual hierarchy
- Real data and meaningful empty/error/loading states
- Responsive layouts
- No fake metrics or simulated success states in production
- Reuse existing UI components and design conventions where practical

### Navigation
Adapt the following information architecture to the current application:
1. Dashboard
2. Research Projects
3. Literature and Papers
4. Hypotheses and Research Plans
5. Context Memory
6. Experiments
7. Results and Evaluation
8. Deep Learning Lab
9. Workspace
10. Models
11. Paper Writing
12. AI Agents
13. Infrastructure and Integrations

Do not add every item as an empty page. Implement functional pages in dependency order and clearly label capabilities that are not yet available.

### Dashboard
Display, where supported by real data:
- Active research project
- Current research question and hypothesis
- Recent experiments and status
- Best evaluation results
- Unresolved problems and next actions
- Recent Context Memory events
- AI-agent activity
- VS Code, Docker and ClearML integration health

### Signature feature: Research Timeline
Build a chronological view linking:
paper or finding → hypothesis → experiment → result/failure → interpretation → decision → next experiment.

Each event should link to the underlying entity and supporting evidence.

### Experiments and Workspace
- Show research-level summaries in PhD Lab.
- Link to ClearML for detailed tracking.
- Provide VS Code/Jupyter/workspace actions only when the relevant integration supports them.
- Keep external integration status visible.

### Tasks
Inspect the current frontend, routing, API contracts and design system before editing. Implement pages incrementally, connect them to real backend data, and add loading, error, empty and permission states.

### Acceptance criteria
The main research workflow can be navigated without dead-end pages; existing functionality remains accessible; research entities link to real evidence; the interface does not duplicate full external-platform UIs.

---

# MILESTONE 7 — Model Serving Foundation

**Mục tiêu:** Chuẩn bị đường mở rộng cho inference mà không bắt buộc triển khai Kubernetes ngay.

## Prompt cho Claude Code

Establish a modular model-serving integration that fits the current PhD Research Lab architecture.

### Scope
Evaluate and integrate only what is justified by the existing application and environment:
- vLLM for supported LLM inference workloads
- BentoML for packaging and serving custom models where appropriate
- KServe for future Kubernetes-based serving
- Kubernetes as a later deployment target, not a prerequisite for local research

### Tasks
1. Audit current model registry, model artifacts, deployment code and compute environment.
2. Define or complete `ModelServingBackend` and model deployment metadata.
3. Separate model registration, artifact references, deployment configuration, health checks and inference endpoint metadata.
4. Choose a minimal initial integration based on actual use cases.
5. Verify hardware, runtime and model compatibility before attempting deployment.
6. If local serving is not feasible, implement configuration validation and deployment documentation rather than pretending a service is running.
7. Keep model artifact provenance linked to Git commits, datasets, training runs and ClearML task IDs.
8. Secure inference endpoints; do not expose unauthenticated services publicly.
9. Add health checks, timeouts, resource limits and deployment status reporting.
10. Document a future path to remote GPU servers or Kubernetes without requiring it now.

### Acceptance criteria
At least one supported model-serving path is genuinely operational if the available hardware and dependencies permit it. Otherwise, the implemented foundation must accurately report what is configured, unavailable or pending.

Do not install a full Kubernetes stack merely to satisfy this milestone. Avoid unnecessary infrastructure that increases maintenance cost.

---

# MILESTONE 8 — End-to-End Validation and Handover

**Mục tiêu:** Chứng minh toàn bộ hệ thống hoạt động như một workflow nghiên cứu thực sự.

## Prompt cho Claude Code

Perform a complete integration validation of the PhD Research Lab after the preceding milestones.

### Required workflow
1. Create or open a research project.
2. Define a research question and hypothesis.
3. Link relevant literature or evidence.
4. Create a version-controlled experiment specification.
5. Associate the correct dataset and runtime configuration.
6. Open the workspace in VS Code when available.
7. Execute a small real training job in the configured environment.
8. Track the run in ClearML when configured.
9. Collect actual metrics, artifacts and logs.
10. Compare the result with the baseline.
11. Ask the analysis workflow to interpret the evidence without inventing findings.
12. Save the conclusion, limitations and next experiment in Context Memory.
13. Verify that the research timeline links all relevant entities.
14. Verify model serving only if Milestone 7 established an operational serving path.

### Validation requirements
- Run unit tests and integration tests.
- Run linting, type checks and build commands available in the repository.
- Test missing integrations, invalid credentials, unavailable services and failed jobs.
- Verify persistence and restart behavior.
- Check for leaked secrets, unsafe shell execution, path traversal and accidental exposure of internal services.
- Confirm that old user data and existing workflows remain intact.
- Record all unresolved defects; do not conceal failures.

### Traceability requirement
Where supported, verify the chain:

Research question → Hypothesis → Experiment → ClearML task → Git commit → Dataset version → Environment → Artifact → Evaluation → Conclusion → Next action.

Do not claim a link exists if the underlying reference is missing.

### Deliverables
Update:
- `ARCHITECTURE.md`
- `MIGRATION_PLAN.md`
- `INTEGRATION_STATUS.md`
- `DEVELOPMENT.md`
- `DEPLOYMENT.md`
- `RESEARCH_WORKFLOW.md`
- `CONTEXT_MEMORY.md`
- `CLEARML_INTEGRATION.md`
- `VSCODE_INTEGRATION.md`
- `MODEL_SERVING.md`, if applicable

Add an end-to-end test or documented reproducible validation procedure.

### Final report
Summarize:
- Implemented capabilities
- Test/build results
- Real integrations verified
- Integrations not configured
- Known limitations and remaining defects
- Security considerations
- Reproduction steps
- Recommended next development priorities

Never mark an acceptance criterion complete without evidence. Preserve the ability to run the existing application and clearly separate completed features from future roadmap items.

---

## 3. Cách làm việc với Claude Code

### Trước mỗi milestone
1. Kiểm tra `git status`.
2. Commit hoặc tạo branch/checkpoint an toàn.
3. Đọc trạng thái hiện tại trong `MIGRATION_PLAN.md` và `INTEGRATION_STATUS.md`.
4. Gửi prompt của milestone đang làm; không gửi cả 8 prompt cùng lúc.

### Sau mỗi milestone
1. Yêu cầu Claude liệt kê file đã thay đổi và lý do.
2. Chạy test/build thực tế.
3. Kiểm tra diff, đặc biệt migration, xóa file, cấu hình bảo mật và dữ liệu.
4. Cập nhật trạng thái milestone trong `MIGRATION_PLAN.md`.
5. Commit khi milestone đạt tiêu chí nghiệm thu hoặc commit riêng phần đã hoàn thành có ghi rõ phần còn thiếu.

### Quy tắc quản lý quota
- Chia công việc thành task nhỏ, có đầu vào và kết quả cụ thể.
- Dùng phiên mới cho task độc lập; cung cấp tài liệu kiến trúc và trạng thái thay vì buộc Claude đọc lại mọi thứ.
- Dành model mạnh hơn cho quyết định kiến trúc hoặc lỗi khó; dùng model tiết kiệm hơn cho task triển khai/test thường lệ nếu gói và cấu hình của bạn hỗ trợ.
- Theo dõi quota thực tế trong Claude Code. Không xem số token ước tính của dự án là số token được bảo đảm trong mỗi tuần.

## 4. Tiêu chí hoàn thành toàn dự án

- [ ] Research Core và Context Memory hiện có vẫn hoạt động.
- [ ] Các integration có trạng thái thật, cấu hình rõ ràng và xử lý lỗi phù hợp.
- [ ] Workspace có thể liên kết với Git và mở trong VS Code khi môi trường hỗ trợ.
- [ ] Môi trường thực thi và quy trình training có thể tái lập ở mức đã tài liệu hóa.
- [ ] ClearML tracking hoạt động khi server được cấu hình.
- [ ] Deep Learning Lab có workflow từ cấu hình đến evaluation.
- [ ] Frontend thể hiện được Research Timeline dựa trên dữ liệu thật.
- [ ] Kết quả có thể truy ngược về experiment và artifact tương ứng khi dữ liệu nguồn hỗ trợ.
- [ ] Kiểm thử, hạn chế và tích hợp chưa cấu hình được ghi rõ.
- [ ] Có tài liệu cài đặt, phát triển, vận hành và phục hồi.

**Thứ tự thực hiện:** M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8.

**Khuyến nghị:** M7 có thể thu hẹp thành phần nền tảng và tài liệu nếu hiện tại bạn chỉ cần training local trên RTX 3060. Ưu tiên một workflow nghiên cứu end-to-end đáng tin cậy hơn là triển khai quá nhiều hạ tầng cùng lúc.
