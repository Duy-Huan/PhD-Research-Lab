# Môi trường chạy: Python environment · Docker · Auto

Mục tiêu: **chọn môi trường một lần, bấm ▶ Chạy là chạy được** — thư viện tự cài, cùng một môi trường cho sandbox run,
notebook và VS Code.

## Ba lựa chọn (Workspace & Runs → thẻ Môi trường)

| Lựa chọn | Khi nào dùng | Cách hoạt động |
|---|---|---|
| ✨ **Auto** (mặc định) | Không muốn nghĩ về môi trường | Mỗi lần chạy: code dùng framework GPU (torch, tensorflow, jax, timm, lightning…) **và** máy có GPU NVIDIA **và** Docker đang chạy → Docker (image CUDA tái lập được); còn lại → Python environment (khởi động ngay). Lý do hiện ở đầu log. |
| 🐍 **Python environment** | Script CPU, phân tích dữ liệu, dùng lại môi trường bạn đã có | Chọn bất kỳ Python nào app dò được trên máy (Python hệ thống ngoài PATH, py launcher, conda env, venv). Hai kiểu: **venv riêng của dự án** tạo từ Python đó (cô lập, vẫn thấy thư viện của Python gốc) hoặc **dùng trực tiếp** Python đó (cho conda/venv bạn tự quản lý). |
| 🐳 **Docker** | Huấn luyện GPU cần tái lập, bộ CUDA cố định, chia sẻ cho người khác | Chọn image: đề xuất cho máy này ★, catalog đã kiểm chứng (PyTorch/CUDA runtime & devel, NGC, TensorFlow, Hugging Face, CUDA base, Python CPU, Jupyter), image đã có trên máy, hoặc 🔎 tìm Docker Hub → chọn repo → lọc và chọn tag, hoặc gõ tên đầy đủ (ghcr.io/…). Image chưa có sẽ được hỏi tải trước khi chạy. Container dài hạn giữ thư viện đã cài giữa các lần chạy. |

## Thư viện tự động

Trước mỗi lần chạy (có thể tắt), app phát hiện thư viện dự án cần từ:
1. `requirements*.txt`, `pyproject.toml` ([project] dependencies), `environment.yml`;
2. các `import` trong mọi `.py` và `.ipynb` (bỏ qua thư viện chuẩn, module của chính dự án, `.venv/`, `runs/`, `data/`…),
   đổi sang tên pip (`cv2 → opencv-python`, `sklearn → scikit-learn`, `PIL → Pillow`, `yaml → PyYAML`…).

Rồi chạy `.phdlab/ensure_deps.py` **bên trong môi trường đích** ngay trước lệnh của bạn, trong cùng log:
- chỉ cài cái thật sự thiếu ở môi trường đó; requirements đã đủ đúng phiên bản pin → không gọi pip (chạy được offline);
- máy có GPU NVIDIA và thiếu `torch` (ngoài Docker) → cài bản CUDA từ `https://download.pytorch.org/whl/cu124`
  (đổi bằng `torch_index`), thất bại thì thử index mặc định;
- cài không được → dừng trước khi chạy và báo tên gói (sửa bằng requirements.txt).
Lần đầu ~vài giây đến vài phút (tuỳ gói); các lần sau chỉ kiểm tra (<1 s). "⚙ Chuẩn bị môi trường" làm trước toàn bộ
(tạo venv / tải image + tạo container / cài thư viện) nếu bạn không muốn chờ ở lần chạy đầu.

## Các kịch bản phối hợp

| # | Kịch bản | Cấu hình gợi ý |
|---|---|---|
| 1 | Thử nhanh một script CPU | Auto (sẽ chọn Python env) |
| 2 | Huấn luyện GPU trên RTX 3060, cần tái lập | Auto hoặc Docker + `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`, tick GPU |
| 3 | Đã có conda env chuẩn với mọi thứ | Python env → chọn conda env → "Dùng trực tiếp" |
| 4 | Notebook khám phá dữ liệu | Jupyter: server lấy từ bất kỳ Python nào có JupyterLab; kernel **PhD-Lab · <dự án>** = môi trường dự án (cài ipykernel tự động) → notebook import đúng các thư viện như các lần chạy |
| 5 | Sửa/debug code trong đúng container | 🐳 Dev Container: một nút — tự cài extension Dev Containers, tự sinh `.devcontainer/` từ image sandbox (cùng giới hạn RAM/CPU/GPU, cùng `ensure_deps.py` qua `postCreateCommand`) rồi mở VS Code |
| 6 | Cần biên dịch CUDA extension (mamba-ssm, flash-attn) | Docker + image `…-devel` trong catalog |
| 7 | Image riêng của lab / từ bài báo | 🔎 Docker Hub hoặc gõ `ghcr.io/org/image:tag` |
| 8 | Smoke test khi LLM cục bộ đang giữ VRAM | tick "Chạy bằng CPU" cho lần chạy đó; quy tắc VRAM vẫn chặn chạy GPU |
| 9 | Nhờ AI sửa code | Codex/Claude (AI Gateway hoặc Codex runs) làm việc trên cùng thư mục code; lần chạy kế tiếp tự cài thư viện mới mà AI thêm vào |

## Giới hạn

- Kernel Jupyter dùng môi trường **Python** của dự án; notebook chạy *trong container* thì mở bằng Dev Container (VS Code).
- Ánh xạ import → tên pip là heuristic; gói hiếm có tên khác (vd. `import Bio` → `biopython`) nên được ghi vào requirements.txt.
- Wheel CUDA của PyTorch có thể chưa có cho Python mới nhất (3.14) — khi đó app thử index mặc định (bản CPU); dùng Docker
  hoặc một Python 3.11/3.12 cho huấn luyện GPU.
- Tìm Docker Hub cần mạng; catalog và image cục bộ dùng được offline.
