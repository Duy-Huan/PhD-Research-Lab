"""Hyperparameter optimisation (v4.1 M5/M6): search-space validation, Optuna studies, the local sequential runner and the
optional Ray Tune adapter, Pareto fronts and confirmation statistics.

Source of truth (no two competing owners of one study)
    engine "optuna"   Optuna owns suggestions and trial state (SQLite storage <project>/workflows/studies/optuna.db);
                      the JSON study record mirrors finished trials for the UI and provenance (derived, rebuildable).
    engine "builtin"  random / grid sampling implemented here when Optuna is not installed or switched off
                      (features.optuna_hpo = false); the JSON study record is canonical.
    runner "local"    one trial at a time by default (single consumer GPU); CPU-only objectives may run up to
                      budgets.max_parallel_trials concurrently.
    runner "ray"      optional (features.ray_tune). The adapter only reports availability: it is NOT validated on this
                      machine, so a study asking for it is refused with a clear message and the local runner is offered.

Search spaces proposed by an agent are data, never code: validate_space() checks types, bounds, log scales,
conditional parameters, duplicates, grid size, trial budget, objective directions and test-split leakage.
"""
from __future__ import annotations

import asyncio
import importlib.util
import itertools
import json
import math
import random
import re
import secrets
import statistics
import time
from pathlib import Path

PARAM_TYPES = ("float", "int", "categorical", "bool")
DIRECTIONS = ("minimize", "maximize")
SAMPLERS = ("auto", "random", "grid", "tpe", "cmaes", "nsga2")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,47}$")
LEAK_RE = re.compile(r"(?i)^(test|holdout)[_\-.]")
MAX_PARAMS = 32
MAX_GRID = 5000
# measurement labels (Template 5 / §8): what a number IS
MEASURED, ESTIMATED, UNAVAILABLE, SYNTHETIC = "MEASURED", "ESTIMATED", "UNAVAILABLE", "SYNTHETIC"


class HPOError(ValueError):
    pass


# ------------------------------------------------------------------ search space
def validate_space(space: dict, objectives: list, max_trials: int = 0, sampler: str = "auto",
                   est_trial_minutes: float = 0.0, max_runtime_minutes: float = 0.0) -> dict:
    """{valid, errors, warnings, params (normalised), objectives, grid_size, est_runtime_min}. Never executes anything."""
    errors, warnings, norm = [], [], {}
    if not isinstance(space, dict) or not space:
        return {"valid": False, "errors": ["search space must be a non-empty object {name: spec}"], "warnings": [],
                "params": {}, "objectives": [], "grid_size": 0, "est_runtime_min": 0}
    if len(space) > MAX_PARAMS:
        errors.append(f"at most {MAX_PARAMS} parameters")
    lower = {}
    for name, spec in space.items():
        if not NAME_RE.match(str(name)):
            errors.append(f"{name!r}: parameter names are identifiers (letters, digits, _)")
            continue
        if name.lower() in lower:
            errors.append(f"{name}: duplicate of {lower[name.lower()]} (names must differ beyond letter case)")
            continue
        lower[name.lower()] = name
        if not isinstance(spec, dict) or spec.get("type") not in PARAM_TYPES:
            errors.append(f"{name}: type must be one of {', '.join(PARAM_TYPES)}")
            continue
        t = spec["type"]
        p = {"type": t}
        if t in ("float", "int"):
            lo, hi = spec.get("low"), spec.get("high")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (lo, hi)):
                errors.append(f"{name}: low and high must be finite numbers")
                continue
            if t == "int" and not (float(lo).is_integer() and float(hi).is_integer()):
                errors.append(f"{name}: int bounds must be integers")
                continue
            if lo >= hi:
                errors.append(f"{name}: low must be < high")
                continue
            log = bool(spec.get("log", False))
            if log and lo <= 0:
                errors.append(f"{name}: a log scale needs low > 0")
                continue
            step = spec.get("step")
            if step is not None:
                if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0 or step > hi - lo:
                    errors.append(f"{name}: step must be > 0 and ≤ high − low")
                    continue
                if log:
                    errors.append(f"{name}: step and log cannot be combined")
                    continue
            p.update(low=int(lo) if t == "int" else float(lo), high=int(hi) if t == "int" else float(hi), log=log)
            if step is not None:
                p["step"] = int(step) if t == "int" else float(step)
            if spec.get("grid_points") is not None:
                gp = spec["grid_points"]
                if not isinstance(gp, int) or isinstance(gp, bool) or not 2 <= gp <= 50:
                    errors.append(f"{name}: grid_points must be an integer 2–50")
                    continue
                p["grid_points"] = gp
        elif t == "categorical":
            ch = spec.get("choices")
            if not isinstance(ch, list) or not ch:
                errors.append(f"{name}: choices must be a non-empty list")
                continue
            if any(not isinstance(c, (str, int, float, bool)) or c is None for c in ch):
                errors.append(f"{name}: choices must be strings, numbers or booleans")
                continue
            if len({json.dumps(c) for c in ch}) != len(ch):
                errors.append(f"{name}: duplicate choices")
                continue
            p["choices"] = list(ch)
        else:
            p["choices"] = [False, True]
        if spec.get("condition") is not None:
            p["condition"] = spec["condition"]
        if spec.get("why"):
            p["why"] = str(spec["why"])[:300]
        norm[name] = p
    for name, p in norm.items():
        c = p.get("condition")
        if c is None:
            continue
        if not isinstance(c, dict) or set(c) != {"param", "equals"}:
            errors.append(f"{name}: condition must be {{'param': <categorical/bool>, 'equals': <choice>}}")
            continue
        parent = norm.get(c["param"])
        if not parent or parent["type"] not in ("categorical", "bool") or parent is p:
            errors.append(f"{name}: condition parent '{c['param']}' must be another categorical/bool parameter")
        elif c["equals"] not in parent["choices"]:
            errors.append(f"{name}: condition value {c['equals']!r} is not a choice of {c['param']}")
    if not errors and _cond_order(norm) is None:
        errors.append("conditional parameters form a cycle")
    objs = []
    if not isinstance(objectives, list) or not objectives:
        errors.append("at least one objective {name, direction} is required")
    else:
        names = set()
        for o in objectives:
            if not isinstance(o, dict) or not NAME_RE.match(str(o.get("name", ""))) or o.get("direction") not in DIRECTIONS:
                errors.append(f"objective {o!r}: needs a metric name and direction minimize|maximize")
                continue
            if o["name"] in names:
                errors.append(f"objective {o['name']}: listed twice")
                continue
            if LEAK_RE.match(o["name"]):
                errors.append(f"objective {o['name']}: optimising a test/holdout metric leaks the test set — use a "
                              "validation metric and keep the test split for the final report")
                continue
            names.add(o["name"])
            objs.append({"name": o["name"], "direction": o["direction"]})
        clash = names & set(norm)
        if clash:
            errors.append(f"objective and parameter share a name: {', '.join(sorted(clash))}")
    if sampler not in SAMPLERS:
        errors.append(f"sampler must be one of {', '.join(SAMPLERS)}")
    grid = grid_size(norm) if not errors else 0
    if sampler == "grid" and not errors:
        if grid == 0:
            errors.append("grid search needs step or grid_points on every float parameter")
        elif grid > MAX_GRID:
            errors.append(f"grid has {grid} points (max {MAX_GRID}) — narrow the space or use random/tpe")
    if sampler == "cmaes" and any(p["type"] in ("categorical", "bool") for p in norm.values()):
        warnings.append("CMA-ES ignores categorical parameters (Optuna samples them independently)")
    if len(objs) > 1 and sampler in ("tpe", "cmaes"):
        warnings.append(f"{sampler} with several objectives: nsga2 is usually the better sampler")
    est = round(est_trial_minutes * max_trials, 1) if est_trial_minutes and max_trials else 0
    if est and max_runtime_minutes and est > max_runtime_minutes:
        errors.append(f"estimated runtime {est} min ({max_trials} trials × {est_trial_minutes} min) exceeds the "
                      f"runtime budget {max_runtime_minutes} min")
    if max_trials and len(norm) > max_trials and sampler not in ("grid",):
        warnings.append(f"{len(norm)} parameters but only {max_trials} trials: the search will be very sparse")
    if not norm and not errors:  # pragma: no cover - every invalid param already produced an error
        errors.append("no valid parameter")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "params": norm, "objectives": objs,
            "grid_size": grid, "est_runtime_min": est}


def _cond_order(norm: dict) -> list | None:
    order, done = [], set()
    pending = list(norm)
    for _ in range(len(norm) + 1):
        nxt = []
        for n in pending:
            c = norm[n].get("condition")
            if c is None or c["param"] in done:
                order.append(n)
                done.add(n)
            else:
                nxt.append(n)
        if not nxt:
            return order
        if len(nxt) == len(pending):
            return None
        pending = nxt
    return None  # pragma: no cover


def _grid_values(p: dict) -> list:
    if p["type"] in ("categorical", "bool"):
        return list(p["choices"])
    if p["type"] == "int":
        step = p.get("step") or 1
        vals = list(range(p["low"], p["high"] + 1, step))
        if p.get("grid_points") and len(vals) > p["grid_points"]:
            n = p["grid_points"]
            vals = sorted({vals[round(i * (len(vals) - 1) / (n - 1))] for i in range(n)})
        return vals
    if p.get("step"):
        n = int(math.floor((p["high"] - p["low"]) / p["step"] + 1e-9)) + 1
        return [round(p["low"] + i * p["step"], 12) for i in range(n)]
    if p.get("grid_points"):
        n = p["grid_points"]
        if p.get("log"):
            a, b = math.log(p["low"]), math.log(p["high"])
            return [math.exp(a + i * (b - a) / (n - 1)) for i in range(n)]
        return [p["low"] + i * (p["high"] - p["low"]) / (n - 1) for i in range(n)]
    return []


def grid_size(norm: dict) -> int:
    n = 1
    for p in norm.values():
        k = len(_grid_values(p))
        if k == 0:
            return 0
        n *= k
    return n


def active(norm: dict, params: dict) -> list:
    """Parameter names that apply given the parent choices (conditional spaces)."""
    out = []
    for n in _cond_order(norm):
        c = norm[n].get("condition")
        if c is None or (c["param"] in out and params.get(c["param"]) == c["equals"]):
            out.append(n)
    return out


def sample_random(norm: dict, rng: random.Random) -> dict:
    out = {}
    for n in _cond_order(norm):
        p = norm[n]
        c = p.get("condition")
        if c is not None and (c["param"] not in out or out[c["param"]] != c["equals"]):
            continue
        if p["type"] in ("categorical", "bool"):
            out[n] = rng.choice(p["choices"])
        elif p["type"] == "int":
            step = p.get("step") or 1
            if p.get("log"):
                v = int(round(math.exp(rng.uniform(math.log(p["low"]), math.log(p["high"])))))
            else:
                v = p["low"] + step * rng.randint(0, (p["high"] - p["low"]) // step)
            out[n] = max(p["low"], min(p["high"], v))
        else:
            if p.get("log"):
                out[n] = math.exp(rng.uniform(math.log(p["low"]), math.log(p["high"])))
            elif p.get("step"):
                out[n] = round(p["low"] + p["step"] * rng.randint(0, int((p["high"] - p["low"]) / p["step"] + 1e-9)), 12)
            else:
                out[n] = rng.uniform(p["low"], p["high"])
    return out


def grid_points(norm: dict) -> list:
    """Every grid point (conditional children only where their parent choice applies; duplicates removed)."""
    names = list(norm)
    seen, out = set(), []
    for combo in itertools.product(*[_grid_values(norm[n]) for n in names]):
        full = dict(zip(names, combo))
        act = active(norm, full)
        pt = {n: full[n] for n in act}
        key = json.dumps(pt, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(pt)
    return out


# ------------------------------------------------------------------ Pareto & statistics
def dominates(a: list, b: list, directions: list) -> bool:
    better = False
    for x, y, d in zip(a, b, directions):
        if (x > y if d == "minimize" else x < y):
            return False
        if x != y:
            better = True
    return better


def pareto_front(trials: list, objectives: list) -> list:
    """Non-dominated COMPLETE trials (every objective present and finite)."""
    names, dirs = [o["name"] for o in objectives], [o["direction"] for o in objectives]
    ok = [t for t in trials if t.get("state") == "COMPLETE" and all(_finite(t.get("values", {}).get(n)) for n in names)]
    vecs = [[t["values"][n] for n in names] for t in ok]
    return [t for i, t in enumerate(ok) if not any(dominates(vecs[j], vecs[i], dirs) for j in range(len(ok)) if j != i)]


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179,
       15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042}


def summary_stats(values: list) -> dict:
    """mean, sample std, n and a two-sided 95 % t confidence interval (n ≥ 2)."""
    v = [x for x in values if _finite(x)]
    n = len(v)
    if not n:
        return {"n": 0, "mean": None, "std": None, "ci95": None}
    mean = statistics.fmean(v)
    if n < 2:
        return {"n": 1, "mean": mean, "std": None, "ci95": None}
    sd = statistics.stdev(v)
    df = n - 1
    t = 1.96 if df > 30 else T95[max(k for k in T95 if k <= df)]  # conservative: nearest tabulated df below
    h = t * sd / math.sqrt(n)
    return {"n": n, "mean": mean, "std": sd, "ci95": [mean - h, mean + h]}


def rank(trials: list, objective: dict) -> list:
    ok = [t for t in trials if t.get("state") == "COMPLETE" and _finite(t.get("values", {}).get(objective["name"]))]
    return sorted(ok, key=lambda t: t["values"][objective["name"]], reverse=objective["direction"] == "maximize")


# ------------------------------------------------------------------ objectives
def analytic(name: str, params: dict, seed: int = 0, step: int | None = None) -> dict:
    """Synthetic benchmark functions (tests, benchmarks, demos). Values are SYNTHETIC — never research results."""
    rng = random.Random(f"{name}:{json.dumps(params, sort_keys=True)}:{seed}")
    num = {k: float(v) for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if name == "quadratic":
        final = {"loss": sum((v - 0.3) ** 2 for v in num.values()) + 0.001 * rng.random()}
    elif name == "branin":
        x1, x2 = num.get("x1", 0.0), num.get("x2", 0.0)
        a, b, c, r, s, t = 1, 5.1 / (4 * math.pi ** 2), 5 / math.pi, 6, 10, 1 / (8 * math.pi)
        final = {"loss": a * (x2 - b * x1 ** 2 + c * x1 - r) ** 2 + s * (1 - t) * math.cos(x1) + s}
    elif name == "restoration_proxy":
        lr, width, depth = num.get("lr", 1e-3), num.get("width", 64.0), num.get("depth", 8.0)
        att = 1.0 if params.get("attention") in (True, "yes", "on") else 0.0
        psnr = 30 + 4 * (1 - math.exp(-width / 64)) + 2 * (1 - math.exp(-depth / 6)) + 0.6 * att \
            - 3 * abs(math.log10(max(lr, 1e-9)) + 3.3) + rng.gauss(0, 0.05)
        final = {"psnr": psnr, "ssim": max(0.0, min(1.0, 0.6 + psnr / 100)), "params_m": width * width * depth * 9 / 1e6
                 * (1.3 if att else 1.0), "latency_ms": 0.02 * width * depth * (1.5 if att else 1.0)}
    else:
        raise HPOError(f"unknown analytic objective {name!r} (quadratic, branin, restoration_proxy)")
    if step is None:
        return final
    total = max(1, int(params.get("_steps", 10)))
    frac = 1 - math.exp(-3 * step / total)
    return {k: (v * frac if k in ("psnr", "ssim") else v + (1 - frac) * (abs(v) + 1)) for k, v in final.items()}


ANALYTIC = ("quadratic", "branin", "restoration_proxy")


# ------------------------------------------------------------------ engines
def optuna_available() -> bool:
    return importlib.util.find_spec("optuna") is not None


def ray_available() -> bool:
    return importlib.util.find_spec("ray") is not None and importlib.util.find_spec("ray.tune") is not None


def engines(features: dict | None = None) -> dict:
    f = features or {}
    opt = optuna_available()
    ray = ray_available()
    return {"optuna": {"installed": opt, "enabled": bool(f.get("optuna_hpo", True)), "usable": opt and f.get("optuna_hpo", True),
                       "version": _version("optuna") if opt else ""},
            "builtin": {"installed": True, "usable": True, "samplers": ["random", "grid"]},
            "ray": {"installed": ray, "enabled": bool(f.get("ray_tune", False)), "usable": False,
                    "detail": "Ray Tune adapter is not validated on this machine — studies use the local sequential runner"
                    if ray else "Ray Tune is not installed (optional) — studies use the local sequential runner"}}


def _version(mod: str) -> str:
    try:
        return __import__(mod).__version__
    except Exception:  # pragma: no cover
        return ""


class BuiltinEngine:
    name = "builtin"

    def __init__(self, norm: dict, objectives: list, sampler: str, seed: int, done: list):
        if sampler not in ("auto", "random", "grid"):
            raise HPOError(f"sampler '{sampler}' needs Optuna (pip install optuna) — the builtin engine offers random and grid")
        self.norm, self.objectives = norm, objectives
        self.sampler = "grid" if sampler == "grid" else "random"
        self.rng = random.Random(seed)
        self.seen = {json.dumps(t["params"], sort_keys=True) for t in done}
        self._grid = [p for p in grid_points(norm) if json.dumps(p, sort_keys=True) not in self.seen] if self.sampler == "grid" else []
        self.pending: dict = {}

    def ask(self) -> tuple:
        if self.sampler == "grid":
            if not self._grid:
                return None, None
            p = self._grid.pop(0)
        else:
            for _ in range(50):
                p = sample_random(self.norm, self.rng)
                if json.dumps(p, sort_keys=True) not in self.seen:
                    break
        self.seen.add(json.dumps(p, sort_keys=True))
        handle = secrets.token_hex(4)
        self.pending[handle] = p
        return handle, p

    def tell(self, handle, values: list | None, state: str) -> None:
        self.pending.pop(handle, None)

    def report(self, handle, value: float, step: int) -> None:
        pass

    def should_prune(self, handle) -> bool:
        return False


class OptunaEngine:
    name = "optuna"

    def __init__(self, norm: dict, objectives: list, sampler: str, seed: int, storage_path: Path, study_id: str, pruning: bool):
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self.optuna, self.norm, self.objectives = optuna, norm, objectives
        multi = len(objectives) > 1
        if sampler == "auto":
            sampler = "nsga2" if multi else "tpe"
        if sampler == "grid":
            # Grid = the validated grid points enqueued into the study (Optuna's GridSampler calls study.stop() when the
            # grid is exhausted, which raises in ask-and-tell mode and lost the last trial; it also ignores conditions).
            s = optuna.samplers.RandomSampler(seed=seed)
        elif sampler == "random":
            s = optuna.samplers.RandomSampler(seed=seed)
        elif sampler == "nsga2":
            s = optuna.samplers.NSGAIISampler(seed=seed)
        elif sampler == "cmaes":
            if importlib.util.find_spec("cmaes") is None:
                raise HPOError("the CMA-ES sampler needs the 'cmaes' package (pip install cmaes)")
            s = optuna.samplers.CmaEsSampler(seed=seed)  # pragma: no cover - cmaes is not installed here
        else:
            s = optuna.samplers.TPESampler(seed=seed)
        self.sampler = sampler
        pruner = optuna.pruners.MedianPruner(n_startup_trials=3, n_warmup_steps=1) if pruning and not multi else \
            optuna.pruners.NopPruner()
        self.study = optuna.create_study(study_name=study_id, storage=_storage(storage_path), sampler=s,
                                         pruner=pruner, directions=[o["direction"] for o in objectives], load_if_exists=True)
        self.trials: dict = {}
        self.grid = sampler == "grid"
        if self.grid:
            known = {json.dumps(t.params, sort_keys=True) for t in self.study.get_trials(deepcopy=False)}
            for pt in grid_points(norm):
                if json.dumps(pt, sort_keys=True) not in known:
                    self.study.enqueue_trial(pt)

    def ask(self) -> tuple:
        if self.grid and not self.study.get_trials(deepcopy=False, states=(self.optuna.trial.TrialState.WAITING,)):
            return None, None  # every grid point has been tried
        t = self.study.ask()
        out = {}
        for n in _cond_order(self.norm):
            p = self.norm[n]
            c = p.get("condition")
            if c is not None and (c["param"] not in out or out[c["param"]] != c["equals"]):
                continue
            if p["type"] in ("categorical", "bool"):
                out[n] = t.suggest_categorical(n, p["choices"])
            elif p["type"] == "int":
                out[n] = t.suggest_int(n, p["low"], p["high"], step=p.get("step") or 1, log=p.get("log", False))
            else:
                out[n] = t.suggest_float(n, p["low"], p["high"], step=p.get("step"), log=p.get("log", False))
        self.trials[t.number] = t
        return t.number, out

    def tell(self, handle, values: list | None, state: str) -> None:
        t = self.trials.pop(handle, None)
        if t is None:  # already told (idempotent: an error handler may report the same trial again)
            return
        TS = self.optuna.trial.TrialState
        if state == "COMPLETE":
            self.study.tell(t, values)
        else:
            self.study.tell(t, state=TS.PRUNED if state == "PRUNED" else TS.FAIL)

    def report(self, handle, value: float, step: int) -> None:
        if len(self.objectives) == 1:
            self.trials[handle].report(value, step)

    def should_prune(self, handle) -> bool:
        return len(self.objectives) == 1 and self.trials[handle].should_prune()


_STORAGES: dict = {}


def _storage(path: Path):
    """One Optuna RDB storage (SQLAlchemy engine + connection pool) per database file and process."""
    import optuna
    key = str(path.resolve())
    if key not in _STORAGES:
        path.parent.mkdir(parents=True, exist_ok=True)
        _STORAGES[key] = optuna.storages.RDBStorage(f"sqlite:///{path.as_posix()}")
    return _STORAGES[key]


def make_engine(norm: dict, objectives: list, sampler: str, seed: int, features: dict, storage_path: Path, study_id: str,
                pruning: bool):
    if optuna_available() and features.get("optuna_hpo", True):
        return OptunaEngine(norm, objectives, sampler, seed, storage_path, study_id, pruning)
    return BuiltinEngine(norm, objectives, sampler, seed, [])


# ------------------------------------------------------------------ study store
def studies_dir() -> Path:
    from ..config import data_dir
    d = data_dir() / "workflows" / "studies"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_study(study: dict) -> None:
    from ..memory.store import replace_retry
    p = studies_dir() / f"{study['id']}.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(study, indent=1, default=str), "utf-8")
    replace_retry(tmp, p)


def load_study(study_id: str) -> dict:
    if not re.fullmatch(r"study-[0-9a-f]{8}", study_id or ""):
        raise HPOError("invalid study id")
    p = studies_dir() / f"{study_id}.json"
    if not p.exists():
        raise HPOError("study not found")
    return json.loads(p.read_text("utf-8"))


def list_studies(limit: int = 50) -> list:
    out = []
    for p in sorted(studies_dir().glob("study-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            d = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        out.append({k: d.get(k) for k in ("id", "objectives", "engine", "sampler", "created", "status", "run_id")}
                   | {"n_trials": len(d.get("trials", []))})
    return out


def env_metadata() -> dict:
    import platform
    meta = {"python": platform.python_version(), "platform": platform.platform(terse=True)}
    try:
        from ..gitops import head_info
        meta["git"] = {k: v for k, v in head_info().items() if k in ("short", "dirty", "commit")}
    except Exception:
        meta["git"] = {}
    return meta


# ------------------------------------------------------------------ the study runner
class Stop(Exception):
    """Raised by the cancel/pause check between trials."""


async def run_study(cfg: dict, *, study_id: str = "", run_id: str = "", should_stop=None, on_event=None,
                    reserve_trials=None, objective_runner=None, features: dict | None = None) -> dict:
    """Create or resume a study and run trials sequentially (or with bounded concurrency for CPU objectives).

    cfg: {search_space, objectives, max_trials, sampler, seed, pruning, parallel, objective: {kind, function|script,
          steps, gpu, timeout_s}, runner}
    reserve_trials(n) → how many of n trials the workflow budget still allows (the shared ledger).
    objective_runner(params, seed, report) → (values dict, meta) — injected for sandbox scripts; analytic by default.
    """
    features = features or {}
    emit = on_event or (lambda *_a, **_k: None)
    should_stop = should_stop or (lambda: False)
    v = validate_space(cfg.get("search_space") or {}, cfg.get("objectives") or [], int(cfg.get("max_trials") or 0),
                       cfg.get("sampler") or "auto")
    if not v["valid"]:
        raise HPOError("invalid search space: " + "; ".join(v["errors"]))
    if (cfg.get("runner") or "local") == "ray":
        raise HPOError(engines(features)["ray"]["detail"])
    objs = v["objectives"]
    if len(objs) > 1 and not features.get("multi_objective_hpo", True):
        raise HPOError("multi-objective HPO is switched off (features.multi_objective_hpo)")
    seed = int(cfg.get("seed") or 0)
    ocfg = cfg.get("objective") or {"kind": "analytic", "function": "quadratic"}
    if ocfg.get("kind", "analytic") == "analytic" and ocfg.get("function") not in ANALYTIC:
        raise HPOError(f"unknown analytic objective {ocfg.get('function')!r}")
    if study_id:
        study = load_study(study_id)
    else:
        study = {"id": "study-" + secrets.token_hex(4), "run_id": run_id, "created": time.time(), "objectives": objs,
                 "search_space": v["params"], "sampler": cfg.get("sampler") or "auto", "seed": seed, "objective": ocfg,
                 "max_trials": int(cfg.get("max_trials") or 0), "trials": [], "status": "running", "environment": env_metadata()}
        emit("study_created", study_id=study["id"])
    engine = make_engine(v["params"], objs, study["sampler"], seed, features, studies_dir() / "optuna.db", study["id"],
                         bool(cfg.get("pruning", True)))
    if isinstance(engine, BuiltinEngine):
        engine.seen |= {json.dumps(t["params"], sort_keys=True) for t in study["trials"]}
        if engine.sampler == "grid":
            engine._grid = [p for p in engine._grid if json.dumps(p, sort_keys=True) not in engine.seen]
    study["engine"] = engine.name
    study["sampler_effective"] = engine.sampler
    study["ownership"] = ("Optuna owns suggestions and trial state (optuna.db); this record mirrors finished trials"
                          if engine.name == "optuna" else "this record is the canonical trial store (builtin engine)")
    save_study(study)
    remaining = max(0, study["max_trials"] - len(study["trials"]))
    allowed = reserve_trials(remaining) if reserve_trials else remaining
    if allowed < remaining:
        emit("step_progress", note=f"trial budget: {allowed} of {remaining} remaining trials allowed by the workflow budget")
    parallel = max(1, int(cfg.get("parallel") or 1))
    if ocfg.get("gpu"):
        parallel = 1  # a single consumer GPU: one training trial at a time
    sem = asyncio.Semaphore(parallel)
    lock = asyncio.Lock()
    run_obj = objective_runner or _analytic_runner(ocfg)

    async def one(handle, params):
        async with sem:
            number = len(study["trials"]) + 1
            t = {"number": number, "params": params, "seed": seed + number, "state": "RUNNING", "values": {},
                 "intermediate": [], "started": time.time(), "measurement": SYNTHETIC if ocfg.get("kind", "analytic") == "analytic"
                 else MEASURED}
            emit("trial_started", study_id=study["id"], trial=number, params=params)
            pruned = {"v": False}

            def report(value, step):
                t["intermediate"].append([step, value])
                engine.report(handle, value, step)
                if engine.should_prune(handle):
                    pruned["v"] = True
                    return True
                return False
            try:
                values, meta = await run_obj(params, t["seed"], report)
                t.update(meta or {})
                if pruned["v"]:
                    t["state"] = "PRUNED"
                    engine.tell(handle, None, "PRUNED")
                    emit("trial_pruned", study_id=study["id"], trial=number)
                else:
                    missing = [o["name"] for o in objs if not _finite(values.get(o["name"]))]
                    if missing:
                        raise HPOError(f"objective metric(s) missing or not finite: {', '.join(missing)}")
                    t["values"] = {k: v for k, v in values.items() if _finite(v)}
                    t["state"] = "COMPLETE"
                    engine.tell(handle, [values[o["name"]] for o in objs], "COMPLETE")
                    emit("trial_completed", study_id=study["id"], trial=number, values=t["values"])
            except asyncio.CancelledError:
                t["state"] = "FAIL"
                t["error"] = "cancelled"
                engine.tell(handle, None, "FAIL")
                raise
            except Exception as e:
                t["state"] = "FAIL"
                t["error"] = f"{type(e).__name__}: {e}"[:500]
                engine.tell(handle, None, "FAIL")
                emit("trial_failed", study_id=study["id"], trial=number, error=t["error"])
            finally:
                t["duration_s"] = round(time.time() - t["started"], 3)
                async with lock:
                    study["trials"].append(t)
                    save_study(study)

    stopped = ""
    launched = 0
    tasks: set = set()
    try:
        while launched < allowed:
            if should_stop():
                stopped = "stopped"
                break
            handle, params = engine.ask()
            if handle is None:
                stopped = "search space exhausted"
                break
            launched += 1
            task = asyncio.ensure_future(one(handle, params))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            if len(tasks) >= parallel:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if tasks:
            await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        study["status"] = "cancelled"
        save_study(study)
        raise
    done = len(study["trials"]) >= study["max_trials"] or stopped == "search space exhausted"
    study["status"] = "completed" if done else ("paused" if stopped else "budget_exhausted")
    study["trials"].sort(key=lambda t: t["number"])
    save_study(study)
    return summarize(study)


def _analytic_runner(ocfg: dict):
    steps = int(ocfg.get("steps") or 0)
    delay = float(ocfg.get("delay_s") or 0)

    async def run(params, seed, report):
        if steps:
            primary = None
            for s in range(1, steps + 1):
                vals = analytic(ocfg["function"], {**params, "_steps": steps}, seed, step=s)
                primary = primary or next(iter(vals))
                if delay:
                    await asyncio.sleep(delay)
                if report(vals[primary], s):
                    return vals, {}
        elif delay:
            await asyncio.sleep(delay)
        return analytic(ocfg["function"], params, seed), {}
    return run


def summarize(study: dict) -> dict:
    objs = study["objectives"]
    ok = [t for t in study["trials"] if t["state"] == "COMPLETE"]
    best = rank(study["trials"], objs[0])[:1]
    front = pareto_front(study["trials"], objs) if len(objs) > 1 else best
    return {"study_id": study["id"], "engine": study.get("engine"), "sampler": study.get("sampler_effective"),
            "status": study["status"], "n_trials": len(study["trials"]), "n_complete": len(ok),
            "n_pruned": sum(t["state"] == "PRUNED" for t in study["trials"]),
            "n_failed": sum(t["state"] == "FAIL" for t in study["trials"]), "objectives": objs,
            "best": best[0] if best else None, "pareto": front, "measurement": (ok[0]["measurement"] if ok else ""),
            "ownership": study.get("ownership", ""),
            "caveat": "Best of a finite search under this budget and protocol — not a global optimum and not "
                      "publication-ready before confirmation runs."}
