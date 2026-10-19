### MASTER PROMPT — PhD Research Lab Open Platform Integration & Frontend Redesign

### 0. Vai trò

Bạn là Senior Software Architect + ML Platform Engineer + Research Infrastructure Engineer.

Tôi đang có một project tên PhD Research Lab đã được xây dựng một phần.

Mục tiêu hiện tại không phải xây lại hệ thống từ đầu.

Mục tiêu là:

Giữ lại toàn bộ Research Core, Context Memory và các tính năng nghiên cứu có giá trị đã xây dựng; từng bước loại bỏ các thành phần hạ tầng phổ thông tự xây và thay thế bằng các nền tảng open-source / mature platform đã có sẵn.

Kiến trúc mục tiêu:

                         PhD Research Lab
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
        Research Core      Context Memory       AI Agents
             │                  │                  │
             └──────────────────┼──────────────────┘
                                │
                         Research Orchestrator
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
       VS Code               ClearML               Docker
       Coding             Experiment/MLOps         Runtime
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                         Compute / GPU Layer
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                  Local       K8s         Cloud

### 1. NGUYÊN TẮC KIẾN TRÚC QUAN TRỌNG NHẤT

Không được tiếp tục tự xây lại các hệ thống đã có nền tảng mature.

Không tự xây
* IDE
* Code editor
* Terminal
* Debugger
* Git implementation
* Git hosting
* Container runtime
* Experiment tracker
* MLOps dashboard
* Model serving engine
* Kubernetes orchestration
* Notebook engine
* GPU scheduler nếu nền tảng chuyên dụng đã đáp ứng

Ưu tiên tích hợp
Chức năng	Nền tảng
Coding IDE	VS Code / Code-OSS integration
Source control	Git
Remote source hosting	GitHub
Container	Docker
Dev environment	Dev Containers
Notebook	Jupyter
Experiment tracking	ClearML
Task / queue / experiment execution	ClearML
Container orchestration	Kubernetes
Model serving abstraction	KServe
LLM serving	vLLM
Custom model serving	BentoML hoặc KServe custom runtime
Cloud GPU	Cloud provider / Kubernetes
Research intelligence	PhD Research Lab
Context Memory	PhD Research Lab
Research workflow	PhD Research Lab
Research reasoning	AI Agents
Scientific evaluation	PhD Research Lab

Không tích hợp tất cả ngay lập tức.

Thiết kế abstraction layer để các backend có thể thay thế được.

### 2. BẮT BUỘC AUDIT CODE TRƯỚC KHI THAY ĐỔI

Trước khi sửa bất kỳ file nào:

1. Đọc cấu trúc repository.
2. Xác định frontend.
3. Xác định backend.
4. Xác định database.
5. Xác định Context Memory.
6. Xác định AI agent architecture.
7. Xác định Deep Learning Lab hiện tại.
8. Xác định execution/sandbox system.
9. Xác định Docker integration hiện tại.
10. Xác định Git/GitHub integration hiện tại.
11. Xác định experiment tracking hiện tại.
12. Xác định model serving hiện tại.
13. Xác định các phần đã hoàn thiện và đang được sử dụng.

Không được xóa hoặc refactor lớn chỉ vì thấy code chưa tối ưu.

Phải tạo:
ARCHITECTURE_AUDIT.md
MIGRATION_PLAN.md
INTEGRATION_STATUS.md

### 3. PHÂN LOẠI CODE HIỆN TẠI

Mỗi subsystem phải được phân loại:
KEEP
ADAPT
REPLACE
REMOVE
UNKNOWN

Ví dụ:
Context Memory        → KEEP
Research Workflow     → KEEP
AI Agent System       → KEEP
Custom IDE            → REPLACE
Custom Experiment UI  → ADAPT
Custom Docker runner  → ADAPT/REPLACE
Custom Git system     → REPLACE
Custom model server   → REPLACE

Không được xóa implementation cũ cho đến khi implementation mới đã được kiểm chứng.

### 4. TARGET ARCHITECTURE

Thiết kế architecture theo mô hình:

                    ┌──────────────────────┐
                    │   PhD Research Lab  │
                    │                      │
                    │ Research Core       │
                    │ Context Memory      │
                    │ AI Agents           │
                    │ Research Workflow   │
                    │ Scientific Eval     │
                    └──────────┬───────────┘
                               │
                         Internal APIs
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
     Workspace API       Experiment API       Serving API
          │                    │                    │
          ↓                    ↓                    ↓
       VS Code              ClearML              KServe
          │                    │                    │
       Docker             ClearML Agent       Kubernetes
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                         Compute Layer
                               │
                    Local / GPU / Cloud

PhD Research Lab phải là control plane / research orchestration layer.

Không biến nó thành một implementation clone của VS Code, ClearML hoặc Kubernetes.

### 5. VS CODE INTEGRATION

Thiết kế WorkspaceAdapter.

Ví dụ:
Workspace
├── project
├── repository
├── branch
├── devcontainer
├── python environment
├── datasets
├── experiment configuration
└── compute target

Frontend phải có:
[Open in VS Code]
[Open Terminal]
[Open Jupyter]
[Open Repository]

PhD Lab chỉ quản lý metadata và lifecycle.

VS Code chịu trách nhiệm:
* editor
* IntelliSense
* extensions
* terminal
* debugger
* Git UI
* Python
* Jupyter
* Dev Containers
* remote development

Không xây editor riêng.

### 6. DOCKER / DEV CONTAINER

PhD Lab phải có: Environment Manager

Nhiệm vụ:
* generate Dockerfile
* generate devcontainer.json
* chọn Python version
* chọn CUDA version
* chọn PyTorch version
* mount datasets
* mount repository
* configure GPU
* configure environment variables
* reproducibility metadata

Ví dụ:
Research Project
      ↓
Environment Specification
      ↓
Docker / Dev Container
      ↓
VS Code

Không xây container runtime riêng.

### 7. GIT / GITHUB

Tích hợp Git native.

PhD Lab chỉ lưu:
repository_url
branch
commit_sha
tag
experiment_commit
paper_commit

Mỗi experiment phải có khả năng truy ngược:
Experiment
     ↓
Git Commit
     ↓
Code
     ↓
Environment
     ↓
Dataset Version

Không xây Git hosting riêng.

Nếu repository/GitHub integration cần API access, tạo adapter riêng.

### 8. JUPYTER

Tích hợp Jupyter/JupyterLab.

Frontend:
[Open Jupyter]

Notebook phải liên kết được với:
Research Project
Experiment
Git Commit
Dataset
ClearML Task

Notebook không được trở thành nơi lưu research truth duy nhất.

Các kết luận quan trọng phải được ghi vào Context Memory.

### 9. CLEARML INTEGRATION

Tạo: ClearMLAdapter

Không để application phụ thuộc trực tiếp vào ClearML SDK ở mọi nơi.

Ví dụ interface:
ExperimentBackend
create_experiment()
start_run()
log_metric()
log_parameter()
log_artifact()
log_model()
finish_run()
get_experiment()
compare_experiments()

ClearML là implementation:
ExperimentBackend
        │
        └── ClearMLAdapter

Sau này có thể thêm: MLflowAdapter mà không thay đổi Research Core.

### 10. CLEARML RESPONSIBILITIES

ClearML chịu trách nhiệm:
* experiment tracking
* task management
* metrics
* logs
* artifacts
* checkpoints
* experiment comparison
* queues
* workers/agents
* reproducibility metadata
* execution tracking

PhD Lab chịu trách nhiệm:
* research question
* hypothesis
* experiment rationale
* research decisions
* interpretation
* failed hypothesis
* scientific conclusions
* research memory

Không duplicate toàn bộ ClearML database vào Context Memory.

Context Memory chỉ lưu:
Experiment ID
Research meaning
Observation
Interpretation
Decision
Conclusion
Next action

### 11. KUBERNETES

Không triển khai Kubernetes ngay trên local machine chỉ để cho đủ tính năng.

Thiết kế:
ComputeBackend
LocalDockerBackend
ClearMLBackend
KubernetesBackend
CloudBackend

Kubernetes chỉ trở thành cần thiết khi:
* nhiều GPU
* nhiều worker
* multi-user
* remote cluster
* scalable serving
* production inference

### 12. MODEL SERVING

Khảo sát và tích hợp nền tảng chuyên dụng.

Ưu tiên architecture:
PhD Lab
    │
    ↓
Model Serving Adapter
    │
    ↓
KServe
    │
    ├── vLLM
    ├── Triton
    ├── HuggingFace
    ├── PyTorch/custom runtime
    └── other supported runtimes

KServe là serving abstraction chính cho Kubernetes.

vLLM là backend ưu tiên cho LLM inference.

BentoML có thể được hỗ trợ như một alternative cho custom model services.

Không tự viết inference server nếu không thực sự cần.

Frontend phải hỗ trợ: Deploy Model với:
Model, Version, Runtime, GPU, Replicas, Autoscaling, Endpoint, Status, Logs, Metrics.

### 13. MODEL REGISTRY

Không tự xây model registry nếu ClearML/KServe/storage đã đáp ứng.

Thiết kế abstraction: ModelRegistry

Backend có thể là:
ClearML
MLflow
Hugging Face
Object Storage

Phải có:
model_id
version
experiment_id
git_commit
dataset_version
metrics
artifact_uri
serving_status

### 14. CONTEXT MEMORY

Đây là subsystem cần giữ lại và tiếp tục phát triển.

Context Memory phải lưu được:
Research
│
├── Papers
├── Concepts
├── Research Questions
├── Hypotheses
├── Decisions
├── Experiments
├── Failed Experiments
├── Observations
├── Conclusions
├── Open Problems
└── Next Actions

Quan trọng:

Context Memory phải liên kết tới external systems:
Experiment → ClearML Task ID
Code → Git Commit
Workspace → VS Code Workspace
Model → Registry ID
Deployment → KServe InferenceService

Không copy dữ liệu lớn vào memory.

Memory lưu semantic meaning + references.

### 15. AI AGENT ARCHITECTURE

Giữ AI Agent system hiện tại.

Có thể tổ chức:
Research Director
       │
       ├── Literature Agent
       ├── Research Gap Agent
       ├── Method Agent
       ├── Coding Agent
       ├── Experiment Agent
       ├── Analysis Agent
       ├── Reviewer Agent
       └── Paper Agent

AI agent phải sử dụng tools:
VS Code / Workspace, Git, Docker, ClearML, Jupyter, KServe, Context Memory, File system, Research database.

Không cho agent trực tiếp thao tác mọi hệ thống bằng cách import SDK ở mọi nơi.

Sử dụng Tool/Adapter layer.

### 16. FRONTEND REDESIGN

Thiết kế frontend theo concept: Research Control Center

Không thiết kế thành IDE clone.

Navigation:
┌───────────────────────────────────────┐
│ PhD Research Lab                     │
├───────────────────────────────────────┤
│ 🏠 Dashboard                          │
│ 📚 Research                           │
│ 🧠 Context Memory                     │
│ 🧪 Experiments                        │
│ 📊 Results                            │
│ 💻 Workspace                          │
│ 🚀 Models                             │
│ 📄 Paper                              │
│ 🤖 AI Agents                          │
│ ⚙️ Infrastructure                    │
└───────────────────────────────────────┘

### 17. DASHBOARD

Dashboard phải hiển thị:
Current Project, Research Progress, Current Hypothesis, Active Experiments, Best Results, Failed Experiments, AI Agent Status, GPU Status, ClearML Status, Docker Status, API Usage.

Thiết kế clean, technical, research-oriented.

Không biến thành dashboard thương mại màu mè.

### 18. RESEARCH PAGE

Các tab: Papers, Literature Map, SOTA, Research Gap, Research Questions, Hypotheses.

Ví dụ:
Research Gap #03
Confidence: 82%
Evidence: Paper A, Paper B, Paper C
Current hypothesis: ...
[Create Experiment]
[Ask Research Agent]
[Save to Memory]

### 19. CONTEXT MEMORY UI

Hi
