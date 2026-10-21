"""Integration layer (v3.2): adapters to external platforms behind stable interfaces — see base.py for the contract."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .base import IntegrationError, IntegrationStatus, NotSupported  # noqa: F401


def _docker() -> IntegrationStatus:
    from ..sandbox import docker_exe, docker_running
    if not docker_exe():
        return IntegrationStatus("docker", "Docker", "unavailable", "Docker CLI not found.",
                                 setup=["Install Docker Desktop with the WSL2 backend (Windows 11)"])
    if not docker_running(5):
        return IntegrationStatus("docker", "Docker", "unavailable", "Docker is installed but the daemon is not running.",
                                 setup=["Start Docker Desktop"])
    return IntegrationStatus("docker", "Docker", "available", "daemon running", capabilities=["sandbox", "dev_container"])


def _git() -> IntegrationStatus:
    from .. import gitops
    from ..config import load_config
    if not gitops.git_exe():
        return IntegrationStatus("git", "Git", "unavailable", "git not found.", setup=["Install Git (https://git-scm.com/download/win)"])
    st = gitops.status()
    head = gitops.head_info() if st.get("repo") else {}
    gh = "GitHub token set" if load_config()["github"].get("token") else "no GitHub token"
    detail = (f"branch {st['branch']} · {head.get('short') or 'no commit'}" + (" · uncommitted changes" if head.get("dirty") else "")
              if st.get("repo") else "code workspace is not a git repository yet")
    return IntegrationStatus("git", "Git / GitHub", "available", f"{detail} · {gh}",
                             extra={"repo": st.get("repo"), "branch": st.get("branch"), "remote": st.get("remote"), "head": head})


def _gpu() -> IntegrationStatus:
    from ..resources import gpus
    g = (gpus(2) or [None])[0]
    if not g:
        return IntegrationStatus("gpu", "NVIDIA GPU", "unavailable", "nvidia-smi not available — CPU only")
    return IntegrationStatus("gpu", "NVIDIA GPU", "available",
                             f"{g['name']} · {g.get('vram_used_mb') or 0:.0f}/{g.get('vram_total_mb') or 0:.0f} MB · {g.get('temp_c')} °C",
                             version=g.get("driver", ""), extra=g)


def _local_ai() -> list:
    import asyncio
    from .. import local_ai
    from ..config import load_config
    cfg = load_config()
    out = []
    for name, label, fn, url in (("ollama", "Ollama", local_ai.ollama_status, cfg["ollama_base_url"]),
                                 ("lmstudio", "LM Studio", local_ai.lmstudio_status, cfg["lmstudio_base_url"])):
        try:
            st = asyncio.run(fn(url))
        except Exception as e:
            st = {"online": False, "error": str(e)}
        loaded = [m["id"] if isinstance(m, dict) else m for m in st.get("loaded", [])]
        out.append(IntegrationStatus(name, label, "available" if st.get("online") else "unavailable",
                                     (f"loaded: {', '.join(loaded)}" if loaded else "no model loaded") if st.get("online") else st.get("error", "offline"),
                                     extra={"models": len(st.get("models", [])), "loaded": loaded}))
    return out


def all_status() -> list:
    """Status of every integration, probed in parallel (each probe has its own timeout)."""
    from .agents import CodexBackend
    from .experiment import ClearMLAdapter, LocalRunsBackend
    from .workspace import jupyter_status, vscode_status
    probes = [vscode_status, jupyter_status, _docker, _git, _gpu, lambda: ClearMLAdapter().status(),
              lambda: LocalRunsBackend().status(), lambda: CodexBackend().status(), _local_ai]
    out = []
    with ThreadPoolExecutor(max_workers=len(probes)) as ex:
        for fut in [ex.submit(p) for p in probes]:
            try:
                r = fut.result(timeout=60)
            except Exception as e:
                r = IntegrationStatus("unknown", "probe", "error", f"{type(e).__name__}: {e}"[:200])
            out.extend(r if isinstance(r, list) else [r])
    return [s.to_dict() for s in out]
