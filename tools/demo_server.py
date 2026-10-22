"""Dev-only demo server: the real app on a throw-away data folder with a FAKE language model (no API key, no GPU) and a
seeded project (outline, papers, decisions, a measured run, a research run, a conversation with proposals) — for
screenshots and manual UI checks. Usage: .venv/Scripts/python tools/demo_server.py [port] → http://127.0.0.1:<port>/"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["PHDLAB_DATA_DIR"] = tempfile.mkdtemp(prefix="phdlab-demo-")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import _env  # noqa: E402,F401  (creates the code project "main")

import uvicorn  # noqa: E402

from backend import memory  # noqa: E402
from backend.core import config  # noqa: E402
from backend.execution import sandbox  # noqa: E402
from backend.knowledge import library  # noqa: E402
from backend.memory import research  # noqa: E402
from backend.providers import models as llm  # noqa: E402
from backend.providers import research as RP  # noqa: E402

ANSWER = ("Dựa trên **2 tài liệu** trong thư viện và đề cương hiện tại, có hai khoảng trống rõ ràng:\n\n"
          "1. Chưa có ViT **dưới 5M tham số** đạt >85% top-1 trên tập con ImageNet khi chạy trên thiết bị 2 W.\n"
          "2. Các đánh giá chỉ báo accuracy; thiếu **độ trễ đo thật** trên phần cứng biên.\n\n"
          "| Hướng | Dữ liệu | Chỉ số |\n|---|---|---|\n| Token pruning + distillation | ImageNet-100 | Top-1, latency |\n\n"
          "Ước lượng FLOPs: $F \\approx 2 N d^2 L$ với $N$ token.\n\n"
          "```chart\n{\"type\": \"line\", \"title\": \"Top-1 theo số tham số (minh hoạ)\", \"xlabel\": \"Tham số (M)\", "
          "\"ylabel\": \"Top-1 (%)\", \"x\": [1, 2, 3, 5, 8], \"series\": [{\"name\": \"ViT-Tiny + pruning\", \"data\": [71.2, 76.5, "
          "79.8, 83.1, 84.6], \"error\": [0.6, 0.5, 0.4, 0.4, 0.3]}, {\"name\": \"MobileViT\", \"data\": [69.0, 74.1, 78.2, 81.0, 83.4]}]}\n```\n\n"
          "```mermaid\nflowchart LR\n  A[Ảnh đầu vào] --> B[Patch embedding] --> C[Token pruning] --> D[Distillation] --> E[Dự đoán]\n```\n\n"
          "Open question: pruning theo attention có giữ được độ chính xác ở độ phân giải thấp không?\n\n"
          '```phdlab-action\n{"action": "propose_gap", "args": {"text": "No sub-5M-parameter ViT with measured edge latency"}}\n```\n')


async def fake_stream(agent, system, messages, max_tokens=0, temperature=0.3):
    for i in range(0, len(ANSWER), 24):
        await asyncio.sleep(0.03)
        yield ("delta", ANSWER[i:i + 24])
    yield ("meta", {"engine": "local", "engine_label": "Demo", "note": "", "model": "demo", "text": ANSWER})


def fake_complete(agent, system, user, max_tokens=6000):
    if "experiment that runs on one PC" in system:
        return ("Kế hoạch: MLP nhỏ trên dữ liệu tổng hợp, seed 0, metric accuracy.\n"
                "```python path=main.py\nimport json, os, random\nrandom.seed(0)\nacc = 0.81 + random.random() * 0.02\n"
                "print('epoch 1 acc', acc)\njson.dump({'accuracy': acc}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n```\n"
                "```phdlab-run\npython main.py --batch-size 32\n```")
    return ("## Tổng quan (demo)\n\nCác hướng chính: token pruning, distillation, hybrid CNN-ViT [S1]. "
            "Một số nhận định chưa kiểm chứng (Smith et al., 2024).\n\n- Gap: thiếu đo độ trễ thật trên thiết bị biên.")


def seed() -> None:
    library.save_library({
        "smith2024.pdf": {"key": "smith2024", "key_locked": True, "file": "smith2024.pdf", "title": "Token pruning for lightweight vision transformers",
                          "authors": ["J. Smith", "A. Lee"], "year": "2024", "venue": "CVPR", "include": True, "status": "refined"},
        "nguyen2023.pdf": {"key": "nguyen2023", "key_locked": True, "file": "nguyen2023.pdf", "title": "Distilling ViTs for edge devices",
                           "authors": ["T. Nguyen"], "year": "2023", "venue": "ICCV", "include": True, "status": "parsed"}})
    from backend.agent import outline
    outline.update({"keywords": "lightweight ViT, edge devices, token pruning, distillation",
                    "topic": "Thiết kế và đánh giá Vision Transformer gọn nhẹ cho phân loại ảnh trên thiết bị hạn chế tài nguyên",
                    "direction": "Kết hợp token pruning thích ứng với distillation để giảm FLOPs mà vẫn giữ accuracy; đo độ trễ thật."},
                   "researcher", "demo")
    memory.add_decision("Dùng ImageNet-100 và CIFAR-100; ngân sách 1 GPU RTX 3060", "constraint")
    research.add_hypothesis("Token pruning thích ứng giảm ≥15% FLOPs với mất ≤0.5 điểm top-1")
    sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False, "gpu": False})
    (sandbox.code_dir() / "train.py").write_text("print('epoch 1 loss=0.50 acc=0.71')\nprint('epoch 2 loss=0.41 acc=0.78')\n", "utf-8")
    sandbox.run_blocking("python train.py", 120, "run", "train")
    config.save_config({"aiws": {"provider": "app:auto"}, "runs": {"web_search": False}})
    from backend.agent import orchestrator, runs, sessions
    s = sessions.create("Khoảng trống nghiên cứu ViT gọn nhẹ")
    orchestrator.start(s["id"], "Tìm research gap cho đề tài của mình")
    for _ in range(200):
        if sessions.get(s["id"])["status"] == "idle":
            break
        time.sleep(0.05)
    orchestrator.start(s["id"], "/lit lightweight vision transformers for edge devices")
    rid = sessions.get(s["id"])["messages"][-1].get("run_id")
    if rid:
        runs.wait(rid, 30)
    orchestrator.start(s["id"], "chạy thử ý tưởng MLP nhỏ trên dữ liệu tổng hợp")


if __name__ == "__main__":
    llm.stream_agent = fake_stream
    RP.app_complete = fake_complete
    seed()
    from backend.app import app
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8798, log_level="warning")
