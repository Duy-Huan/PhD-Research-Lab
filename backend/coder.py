"""Co-coding agent (v3.0): Human-AI pair programming (Workspace & Runs tab) with an automatic self-debugging loop.

Text protocol (works with every model, including local 14B models without function calling):
    ```python file=src/train.py        → create/replace that file (complete content)
    ```run                              → run that command in the sandbox
In AUTO mode the agent's files are written, the command runs in the Docker sandbox, and on a non-zero exit the
stderr/stdout tail is sent back to the agent to fix — up to N attempts (self-debugging loop).
"""
from __future__ import annotations

import asyncio
import difflib
import json
import re

from . import ide_fs, sandbox
from .config import workspace

FILE_RE = re.compile(r"```[ \t]*([\w+.-]*)[ \t]+(?:file|path)\s*=\s*[\"']?([^\s`\"']+)[\"']?[^\n]*\n(.*?)```", re.S)
RUN_RE = re.compile(r"```[ \t]*(?:run|bash[ \t]+run|sh[ \t]+run|shell[ \t]+run)[ \t]*\n(.*?)```", re.S)

CODER_SYS = """You are the Co-coding Agent of a PhD research IDE: a senior research engineer pair-programming with the researcher.
You see the workspace files, the research blueprint and the latest run output. The code runs in a sandbox
(Docker container, working directory /workspace = the workspace root; NVIDIA GPU when available) or a local Python venv.

How to act (STRICT protocol — the IDE parses it):
1. To create or change a file, output the COMPLETE new file content in ONE fenced block whose info line has file=<relative path>:
```python file=src/train.py
...entire file...
```
   Never use diffs or "..." placeholders — always the whole file. Only touch files that need to change.
2. To run something, output exactly one block:
```run
python src/train.py --epochs 2
```
   Install packages with `pip install …` in a run block when needed (prefer adding them to requirements.txt).
3. Before the blocks, explain the plan in 1-5 short bullet points. After a failed run you receive stderr: find the root
   cause, fix it, and run again. Do not repeat a fix that already failed.

Research-code conventions (the IDE picks them up automatically):
- write final metrics as a flat JSON object of numbers to os.path.join(os.environ.get("RUN_DIR", "."), "metrics.json")
- log progress lines like `epoch 3 loss=0.1234 psnr=28.41` (plotted live)
- save figures (matplotlib Agg) as PNG into $RUN_DIR; seed everything; keep smoke-test runs short (few epochs/samples)
- never fabricate results; never hard-code metric values."""


def _blueprint() -> str:
    parts = []
    for name, n in (("experiment_design.md", 9000), ("lit2plan.md", 4000)):
        f = workspace() / name
        if f.exists():
            parts.append(f"--- {name} (excerpt) ---\n{f.read_text('utf-8', errors='replace')[:n]}")
    return "\n\n".join(parts)


def _last_run() -> str:
    runs = sandbox.list_runs(3)
    if not runs:
        return ""
    r = runs[0]
    try:
        d = sandbox.get_run(r["id"])
    except Exception:
        return ""
    return (f"LAST RUN {r['id']}: `{r.get('cmd')}` → {r.get('status')} (exit {r.get('exit_code')}), metrics {json.dumps(r.get('metrics') or {})[:300]}\n"
            f"stderr tail:\n{d.get('stderr', '')[-2500:]}\nstdout tail:\n{d.get('stdout', '')[-1500:]}")


def system_prompt(open_file: str = "", extra_context: str = "", query: str = "") -> str:
    from .context_graph import pinned_block, purged_ids
    from .memory.compiler import agent_block
    s = CODER_SYS
    pinned = pinned_block()
    if pinned:
        s += "\n\n# MUST-FOLLOW CONTEXT (pinned by the researcher)\n" + pinned
    s += agent_block("ide", "", query, purged_ids())
    bp = _blueprint()
    if bp:
        s += "\n\n# RESEARCH BLUEPRINT\n" + bp
    st = sandbox.load_settings()
    mode = sandbox.effective_mode(st)
    s += f"\n\n# SANDBOX\nmode={mode}" + (f", image={sandbox.effective_image(st)}, gpu={'yes' if st['gpu'] else 'no'}" if mode == "docker" else ", local Python venv")
    lr = _last_run()
    if lr:
        s += "\n\n# " + lr
    s += "\n\n# " + ide_fs.snapshot(focus=[open_file] if open_file else None, max_chars=50000)
    if open_file:
        s += f"\n\n(The researcher currently has `{open_file}` open in the editor.)"
    if extra_context:
        s += "\n\n" + extra_context
    return s


def parse(text: str) -> dict:
    files = []
    for lang, path, body in FILE_RE.findall(text):
        path = path.strip().lstrip("./").replace("\\", "/")
        if path and not any(f["path"] == path for f in files):
            files.append({"path": path, "lang": lang, "content": body if body.endswith("\n") else body + "\n"})
    runs = [c.strip().splitlines()[0].strip() for c in RUN_RE.findall(text) if c.strip()]
    return {"files": files, "run": runs[0] if runs else ""}


def preview(files: list) -> list:
    out = []
    for f in files:
        try:
            old = ide_fs.read(f["path"]).get("content", "")
            exists = True
        except Exception:
            old, exists = "", False
        d = list(difflib.unified_diff(old.splitlines(), f["content"].splitlines(), lineterm="", n=0))
        add = sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
        rem = sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
        out.append({**f, "old": old, "exists": exists, "added": add, "removed": rem})
    return out


def apply(files: list) -> list:
    done = []
    for f in files:
        ide_fs.write(f["path"], f["content"])
        done.append(f["path"])
    return done


async def run_and_wait(cmd: str, emit, title: str = "", cpu: bool = False) -> dict:
    job = await asyncio.to_thread(sandbox.start_job, cmd, "run", title or f"agent: {cmd[:60]}",
                                  {"CUDA_VISIBLE_DEVICES": ""} if cpu else None)
    await emit({"type": "run_start", "job": job.info()})
    last = 0
    try:
        while True:
            new = job.since(last)
            if new:
                last = new[-1][0]
                await emit({"type": "run_lines", "job_id": job.id, "lines": [[s, t] for _, s, t in new[-400:]]})
            if job.status != "running" and not job.since(last):
                break
            await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        if job.status == "running":
            await asyncio.to_thread(sandbox.stop_job, job.id)
        raise
    info = job.info()
    await emit({"type": "run_end", "job": info})
    return {"job": info, "stderr": job.tail(60, "err"), "stdout": job.tail(40, "out"), "meta": job.meta}
