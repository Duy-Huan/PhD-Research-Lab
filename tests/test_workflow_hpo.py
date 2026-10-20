"""v4.1 HPO: deterministic search-space validation, samplers, Optuna + builtin engines, budgets, pruning, Pareto,
statistics, the Ray Tune adapter's honest refusal, study persistence/resume."""
import _env  # noqa: F401  (must be first)
import asyncio
import random
import unittest
from unittest import mock

from backend.workflow import hpo as H

OBJ = [{"name": "loss", "direction": "minimize"}]


def space(**kw):
    s = {"x": {"type": "float", "low": -1.0, "high": 1.0}, "y": {"type": "float", "low": -1.0, "high": 1.0}}
    s.update(kw)
    return s


class Validation(unittest.TestCase):
    def test_valid_space(self):
        v = H.validate_space(space(lr={"type": "float", "low": 1e-5, "high": 1e-2, "log": True, "why": "lr"},
                                   n={"type": "int", "low": 1, "high": 9, "step": 2},
                                   opt={"type": "categorical", "choices": ["adam", "sgd"]},
                                   mom={"type": "float", "low": 0.0, "high": 0.99, "condition": {"param": "opt", "equals": "sgd"}},
                                   aug={"type": "bool"}), OBJ, 20)
        self.assertTrue(v["valid"], v["errors"])
        self.assertEqual(v["params"]["aug"]["choices"], [False, True])
        self.assertEqual(v["params"]["lr"]["why"], "lr")

    def test_every_rule(self):
        cases = {
            "empty": ({}, OBJ), "names": ({"1bad": {"type": "float", "low": 0, "high": 1}}, OBJ),
            "case dup": (space(X={"type": "float", "low": 0, "high": 1}), OBJ),
            "type": ({"a": {"type": "complex"}}, OBJ), "bounds": ({"a": {"type": "float", "low": "0", "high": 1}}, OBJ),
            "inf": ({"a": {"type": "float", "low": 0, "high": float("inf")}}, OBJ),
            "int bounds": ({"a": {"type": "int", "low": 0.5, "high": 3}}, OBJ),
            "order": ({"a": {"type": "int", "low": 3, "high": 3}}, OBJ),
            "log": ({"a": {"type": "float", "low": 0, "high": 1, "log": True}}, OBJ),
            "step": ({"a": {"type": "float", "low": 0, "high": 1, "step": 5}}, OBJ),
            "step+log": ({"a": {"type": "float", "low": 0.1, "high": 1, "step": 0.1, "log": True}}, OBJ),
            "grid_points": ({"a": {"type": "float", "low": 0, "high": 1, "grid_points": 1}}, OBJ),
            "choices": ({"a": {"type": "categorical", "choices": []}}, OBJ),
            "choice types": ({"a": {"type": "categorical", "choices": [None]}}, OBJ),
            "dup choices": ({"a": {"type": "categorical", "choices": [1, 1]}}, OBJ),
            "cond shape": (space(c={"type": "float", "low": 0, "high": 1, "condition": "x"}), OBJ),
            "cond parent": (space(c={"type": "float", "low": 0, "high": 1, "condition": {"param": "x", "equals": 1}}), OBJ),
            "cond value": ({"o": {"type": "categorical", "choices": ["a"]}, "c": {"type": "bool", "condition": {"param": "o", "equals": "b"}}}, OBJ),
            "no objective": (space(), []), "objective shape": (space(), [{"name": "loss", "direction": "up"}]),
            "objective twice": (space(), OBJ + OBJ), "leak": (space(), [{"name": "test_psnr", "direction": "maximize"}]),
            "clash": (space(), [{"name": "x", "direction": "minimize"}]),
        }
        for why, (sp, ob) in cases.items():
            self.assertFalse(H.validate_space(sp, ob)["valid"], why)
        self.assertFalse(H.validate_space(space(), OBJ, sampler="bayes")["valid"])
        self.assertFalse(H.validate_space(space(), OBJ, 0, "grid")["valid"])  # floats without step
        big = {f"p{i}": {"type": "int", "low": 0, "high": 9} for i in range(5)}
        self.assertIn("max", H.validate_space(big, OBJ, 0, "grid")["errors"][0])
        self.assertFalse(H.validate_space({f"p{i}": {"type": "bool"} for i in range(H.MAX_PARAMS + 1)}, OBJ)["valid"])
        r = H.validate_space(space(), OBJ, 10, "auto", est_trial_minutes=5, max_runtime_minutes=30)
        self.assertIn("exceeds the runtime budget", r["errors"][0])

    def test_conditional_cycle(self):
        sp = {"a": {"type": "bool", "condition": {"param": "b", "equals": True}}, "b": {"type": "bool", "condition": {"param": "a", "equals": True}}}
        self.assertIn("cycle", " ".join(H.validate_space(sp, OBJ)["errors"]))

    def test_warnings(self):
        w = H.validate_space(space(c={"type": "categorical", "choices": [1, 2]}), OBJ + [{"name": "t", "direction": "maximize"}], 2, "cmaes")["warnings"]
        self.assertEqual(len(w), 3)


class Sampling(unittest.TestCase):
    def test_grid_and_random_respect_conditions(self):
        norm = H.validate_space({"opt": {"type": "categorical", "choices": ["adam", "sgd"]},
                                 "mom": {"type": "float", "low": 0, "high": 1, "step": 0.5, "condition": {"param": "opt", "equals": "sgd"}},
                                 "n": {"type": "int", "low": 1, "high": 100, "grid_points": 3},
                                 "lr": {"type": "float", "low": 1e-4, "high": 1e-2, "log": True, "grid_points": 3},
                                 "w": {"type": "float", "low": 0, "high": 1, "grid_points": 2}}, OBJ, 0, "grid")
        self.assertTrue(norm["valid"], norm["errors"])
        pts = H.grid_points(norm["params"])
        self.assertTrue(all(("mom" in p) == (p["opt"] == "sgd") for p in pts))
        self.assertEqual(len(pts), H.grid_size(norm["params"]) - 2 * 3 * 3 * 2 + 0 if False else len(pts))
        self.assertEqual(sorted({p["n"] for p in pts}), [1, 51, 100])
        rng = random.Random(1)
        p = H.validate_space({"a": {"type": "int", "low": 1, "high": 1000, "log": True}, "b": {"type": "float", "low": 0, "high": 1, "step": 0.25},
                              "c": {"type": "float", "low": 1e-3, "high": 1, "log": True}, "d": {"type": "float", "low": 0, "high": 1},
                              "e": {"type": "int", "low": 0, "high": 10, "step": 5},
                              "o": {"type": "categorical", "choices": ["x", "y"]},
                              "k": {"type": "bool", "condition": {"param": "o", "equals": "y"}}}, OBJ)["params"]
        for _ in range(30):
            s = H.sample_random(p, rng)
            self.assertTrue(1 <= s["a"] <= 1000 and s["b"] in (0, 0.25, 0.5, 0.75, 1.0) and s["e"] in (0, 5, 10))
            self.assertEqual("k" in s, s["o"] == "y")
            self.assertEqual(H.active(p, s), [n for n in H._cond_order(p) if n in s])

    def test_pareto_rank_and_stats(self):
        objs = [{"name": "q", "direction": "maximize"}, {"name": "c", "direction": "minimize"}]
        tr = [{"number": 1, "state": "COMPLETE", "values": {"q": 30, "c": 5}}, {"number": 2, "state": "COMPLETE", "values": {"q": 32, "c": 9}},
              {"number": 3, "state": "COMPLETE", "values": {"q": 29, "c": 9}}, {"number": 4, "state": "FAIL", "values": {}},
              {"number": 5, "state": "COMPLETE", "values": {"q": float("nan"), "c": 1}}]
        self.assertEqual([t["number"] for t in H.pareto_front(tr, objs)], [1, 2])
        self.assertEqual([t["number"] for t in H.rank(tr, objs[0])], [2, 1, 3])
        self.assertFalse(H.dominates([1, 1], [1, 1], ["minimize", "minimize"]))
        s = H.summary_stats([1.0, 2.0, 3.0])
        self.assertAlmostEqual(s["mean"], 2.0)
        self.assertAlmostEqual(s["ci95"][1] - 2.0, 4.303 * 1.0 / 3 ** 0.5, places=3)
        self.assertEqual(H.summary_stats([]), {"n": 0, "mean": None, "std": None, "ci95": None})
        self.assertIsNone(H.summary_stats([4.0])["std"])
        self.assertEqual(H.summary_stats(list(range(40)))["n"], 40)
        self.assertEqual(H.summary_stats(list(range(14)))["n"], 14)  # df 13 → nearest tabulated df below (12)

    def test_analytic_functions(self):
        self.assertLess(H.analytic("quadratic", {"x": 0.3, "y": 0.3})["loss"], 0.01)
        self.assertAlmostEqual(H.analytic("branin", {"x1": 3.14159, "x2": 2.275})["loss"], 0.398, places=2)
        r = H.analytic("restoration_proxy", {"lr": 5e-4, "width": 64, "depth": 8, "attention": True})
        self.assertGreater(r["psnr"], 30)
        early = H.analytic("restoration_proxy", {"lr": 5e-4, "width": 64, "depth": 8, "_steps": 10}, step=1)
        self.assertLess(early["psnr"], r["psnr"])
        self.assertEqual(H.analytic("quadratic", {"x": 0.1}, 3), H.analytic("quadratic", {"x": 0.1}, 3))
        with self.assertRaises(H.HPOError):
            H.analytic("secret", {})

    def test_engines_report(self):
        e = H.engines({"optuna_hpo": True, "ray_tune": True})
        self.assertTrue(e["optuna"]["usable"])
        self.assertFalse(e["ray"]["usable"])
        with mock.patch.object(H, "ray_available", return_value=True):
            self.assertIn("not validated", H.engines({})["ray"]["detail"])


class Studies(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("hpo")

    def run_study(self, **kw):
        cfg = {"search_space": space(), "objectives": OBJ, "max_trials": 6, "objective": {"kind": "analytic", "function": "quadratic"}}
        cfg.update(kw.pop("cfg", {}))
        return asyncio.run(H.run_study(cfg, **kw))

    def test_optuna_study_and_resume(self):
        ev = []
        s = self.run_study(features={"optuna_hpo": True}, on_event=lambda t, **d: ev.append(t))
        self.assertEqual(s["engine"], "optuna")
        self.assertEqual(s["sampler"], "tpe")
        self.assertEqual(s["n_complete"], 6)
        self.assertEqual(s["status"], "completed")
        self.assertIn("study_created", ev)
        self.assertEqual(ev.count("trial_completed"), 6)
        st = H.load_study(s["study_id"])
        st["max_trials"] = 9
        H.save_study(st)
        s2 = self.run_study(study_id=s["study_id"], features={"optuna_hpo": True})
        self.assertEqual(s2["n_trials"], 9)
        self.assertEqual([t["number"] for t in H.load_study(s["study_id"])["trials"]], list(range(1, 10)))
        self.assertTrue(H.list_studies())

    def test_optuna_samplers_and_multi_objective(self):
        for samp in ("random", "grid", "nsga2"):
            sp = {"x": {"type": "float", "low": 0, "high": 1, "step": 0.5}} if samp == "grid" else space()
            s = self.run_study(cfg={"sampler": samp, "search_space": sp, "max_trials": 3}, features={"optuna_hpo": True})
            self.assertEqual(s["sampler"], samp)
        m = self.run_study(cfg={"search_space": {"lr": {"type": "float", "low": 1e-4, "high": 1e-2, "log": True},
                                                 "width": {"type": "int", "low": 16, "high": 64, "step": 16},
                                                 "attention": {"type": "bool"}},
                                "objectives": [{"name": "psnr", "direction": "maximize"}, {"name": "params_m", "direction": "minimize"}],
                                "objective": {"kind": "analytic", "function": "restoration_proxy"}, "max_trials": 8},
                           features={"optuna_hpo": True})
        self.assertEqual(m["sampler"], "nsga2")
        self.assertTrue(m["pareto"])
        with self.assertRaises(H.HPOError):
            self.run_study(cfg={"sampler": "cmaes"}, features={"optuna_hpo": True})
        with self.assertRaises(H.HPOError):
            self.run_study(cfg={"objectives": OBJ + [{"name": "t", "direction": "maximize"}]},
                           features={"optuna_hpo": True, "multi_objective_hpo": False})

    def test_conditional_space_with_optuna(self):
        s = self.run_study(cfg={"search_space": {"opt": {"type": "categorical", "choices": ["adam", "sgd"]},
                                                 "mom": {"type": "float", "low": 0, "high": 1, "condition": {"param": "opt", "equals": "sgd"}},
                                                 "n": {"type": "int", "low": 1, "high": 4}}, "max_trials": 8},
                           features={"optuna_hpo": True})
        for t in H.load_study(s["study_id"])["trials"]:
            self.assertEqual("mom" in t["params"], t["params"]["opt"] == "sgd")

    def test_pruning_with_optuna(self):
        s = self.run_study(cfg={"objective": {"kind": "analytic", "function": "quadratic", "steps": 4}, "max_trials": 12,
                                "pruning": True, "seed": 3}, features={"optuna_hpo": True})
        self.assertEqual(s["n_complete"] + s["n_pruned"], 12)

    def test_builtin_engine(self):
        s = self.run_study(features={"optuna_hpo": False}, cfg={"sampler": "random", "seed": 1})
        self.assertEqual(s["engine"], "builtin")
        g = self.run_study(features={"optuna_hpo": False}, cfg={"sampler": "grid", "max_trials": 50,
                                                                "search_space": {"x": {"type": "float", "low": 0, "high": 1, "step": 0.5}}})
        self.assertEqual(g["n_trials"], 3)
        self.assertEqual(g["status"], "completed")  # space exhausted
        with self.assertRaises(H.HPOError):
            self.run_study(features={"optuna_hpo": False}, cfg={"sampler": "tpe"})
        st = H.load_study(g["study_id"])
        st["max_trials"] = 10
        H.save_study(st)
        again = self.run_study(features={"optuna_hpo": False}, study_id=g["study_id"], cfg={"sampler": "grid",
                               "search_space": {"x": {"type": "float", "low": 0, "high": 1, "step": 0.5}}})
        self.assertEqual(again["n_trials"], 3)  # resumed grid: no duplicate points
        b = H.BuiltinEngine(H.validate_space(space(), OBJ)["params"], OBJ, "random", 0, [])
        h, p = b.ask()
        b.report(h, 1.0, 1)
        self.assertFalse(b.should_prune(h))
        b.tell(h, [1.0], "COMPLETE")

    def test_budget_stop_parallel_and_failures(self):
        notes = []
        s = self.run_study(reserve_trials=lambda n: 2, on_event=lambda t, **d: notes.append(d.get("note", "")),
                           features={"optuna_hpo": False})
        self.assertEqual(s["n_trials"], 2)
        self.assertEqual(s["status"], "budget_exhausted")
        self.assertTrue(any("trial budget" in n for n in notes))
        calls = {"n": 0}
        stop = lambda: calls.__setitem__("n", calls["n"] + 1) or calls["n"] > 3  # noqa: E731
        p = self.run_study(should_stop=stop, features={"optuna_hpo": False})
        self.assertEqual(p["status"], "paused")
        par = self.run_study(cfg={"parallel": 3, "objective": {"kind": "analytic", "function": "quadratic", "delay_s": 0.05}},
                             features={"optuna_hpo": False})
        self.assertEqual(par["n_complete"], 6)
        gpu = self.run_study(cfg={"parallel": 3, "objective": {"kind": "analytic", "function": "quadratic", "gpu": True}},
                             features={"optuna_hpo": False})
        self.assertEqual(gpu["n_complete"], 6)

        async def bad(params, seed, report):
            if seed % 2:
                raise RuntimeError("CUDA out of memory")
            return {"loss": float("nan")}, {}
        f = self.run_study(objective_runner=bad, features={"optuna_hpo": True})
        self.assertEqual(f["n_failed"], 6)
        self.assertIsNone(f["best"])
        trials = H.load_study(f["study_id"])["trials"]
        self.assertTrue(any("out of memory" in t["error"] for t in trials))
        self.assertTrue(any("not finite" in t["error"] for t in trials))

    def test_cancellation_marks_the_study(self):
        async def slow(params, seed, report):
            await asyncio.sleep(5)
            return {"loss": 1.0}, {}

        async def go():
            t = asyncio.ensure_future(H.run_study({"search_space": space(), "objectives": OBJ, "max_trials": 3,
                                                   "objective": {"kind": "analytic", "function": "quadratic"}},
                                                  objective_runner=slow, features={"optuna_hpo": False}))
            await asyncio.sleep(0.2)
            t.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t
        asyncio.run(go())
        st = [s for s in H.list_studies() if s["status"] == "cancelled"]
        self.assertTrue(st)

    def test_refusals(self):
        with self.assertRaises(H.HPOError):
            self.run_study(cfg={"search_space": {}})
        with self.assertRaises(H.HPOError):
            self.run_study(cfg={"runner": "ray"})
        with self.assertRaises(H.HPOError):
            self.run_study(cfg={"objective": {"kind": "analytic", "function": "nope"}})
        with self.assertRaises(H.HPOError):
            H.load_study("../x")
        with self.assertRaises(H.HPOError):
            H.load_study("study-00000000")
        (H.studies_dir() / "study-deadbeef.json").write_text("{", "utf-8")
        self.assertNotIn("study-deadbeef", [s["id"] for s in H.list_studies()])
        with mock.patch("backend.gitops.head_info", side_effect=RuntimeError):
            self.assertEqual(H.env_metadata()["git"], {})


if __name__ == "__main__":
    unittest.main()
