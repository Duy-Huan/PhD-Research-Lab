"""v4.1 M1 workflow contracts: validation against the server-side allowlist, references and conditions (no eval)."""
import _env  # noqa: F401  (must be first)
import copy
import unittest

from backend.workflow import schema as S, steps as ST


def wf(**kw):
    d = {"id": "demo", "name": "Demo", "version": 1, "execution_mode": "assisted",
         "inputs": {"q": {"type": "string", "required": True}},
         "steps": [{"id": "ctx", "type": "research.context", "params": {"query": {"$ref": "inputs.q"}}},
                   {"id": "ok", "type": "human.approval", "depends_on": ["ctx"], "params": {"show": {"$ref": "steps.ctx.output.context"}}}],
         "outputs": {"c": "steps.ctx.output.context"}}
    d.update(kw)
    return d


def errs(d, **kw):
    return S.validate(d, ST.REGISTRY, **kw)[1]


class Validate(unittest.TestCase):
    def test_valid_definition_is_normalised(self):
        d, e = S.validate(wf(), ST.REGISTRY, {"max_trials_cap": 200}, {"optuna_hpo": True})
        self.assertEqual(e, [])
        self.assertEqual(d["budgets"]["max_trials"], S.DEFAULT_BUDGETS["max_trials"])
        self.assertEqual(d["approvals"], S.DEFAULT_APPROVALS)
        self.assertEqual(d["steps"][0]["retry"], {"max": 0})
        self.assertEqual(d["steps"][1]["label"], "ok")

    def test_header_errors(self):
        self.assertEqual(S.validate([], ST.REGISTRY), ({}, ["definition must be an object"]))
        e = errs(wf(id="Bad Id", version=0, execution_mode="yolo", failure_policy="pray", inputs=[], steps=[]))
        joined = " | ".join(e)
        for frag in ("id:", "version", "execution_mode", "failure_policy", "inputs must be", "at least one step"):
            self.assertIn(frag, joined)
        self.assertTrue(errs(wf(version="x")))
        self.assertTrue(errs(wf(inputs={"Bad": {"type": "string"}})))

    def test_budgets_caps_and_bounded_mode(self):
        e = errs(wf(budgets={"max_trials": 500, "nope": 1, "max_runtime_minutes": -1}), caps={"max_trials_cap": 200})
        self.assertTrue(any("hard cap" in x for x in e))
        self.assertTrue(any("unknown budget" in x for x in e))
        self.assertTrue(any("non-negative" in x for x in e))
        e = errs(wf(execution_mode="bounded", budgets={"max_trials": 0}))
        self.assertTrue(any("bounded automation needs" in x for x in e))
        self.assertTrue(any("approvals" in x for x in errs(wf(approvals={"before_training": "maybe"}))))
        self.assertEqual(errs(wf(approvals={"before_training": "not_required"})), [])

    def test_step_errors(self):
        base = wf()
        bad = copy.deepcopy(base)
        bad["steps"] += [
            "not-a-step",
            {"id": "ctx", "type": "research.context", "params": {"query": "x"}},          # duplicate id
            {"id": "x1", "type": "shell.exec"},                                             # not on the allowlist
            {"id": "x2", "type": "research.context", "mode": "turbo", "params": {"query": 3}},
            {"id": "x3", "type": "research.context", "params": {}},                           # required param
            {"id": "x4", "type": "research.context", "params": {"query": "q", "evil": 1}},  # unknown param
            {"id": "x5", "type": "research.context", "params": "nope", "retry": {"max": "z"}},
            {"id": "x6", "type": "research.context", "params": {"query": "q"}, "depends_on": ["ghost", "x6"]},
            {"id": "x7", "type": "research.context", "params": {"query": "q"}, "when": "yes"},
            {"id": "x8", "type": "research.context", "params": {"query": "q"}, "when": {"ref": "bad ref", "op": "zz"}},
            {"id": "x9", "type": "research.context", "params": {"query": "q"}, "when": {"all": []}}]
        e = " | ".join(errs(bad))
        for frag in ("must be an object", "duplicate id", "allowlist", "mode must be", "params.query must be string",
                     "is required", "unknown params", "params must be an object", "retry.max", "is not another step",
                     "condition must be an object", "valid 'ref'", "op must be", "non-empty list"):
            self.assertIn(frag, e)
        self.assertTrue(errs(wf(steps=[{"id": f"s{i}", "type": "research.state"} for i in range(S.MAX_STEPS + 1)])))

    def test_allowed_tools_features_and_custom_mode(self):
        self.assertTrue(errs(wf(allowed_tools=["research.state"])))
        self.assertTrue(errs(wf(allowed_tools=["no.such"])))
        hp = wf(steps=[{"id": "v", "type": "hpo.validate_search_space", "params": {"search_space": {}, "objectives": []}}], outputs={})
        self.assertTrue(errs(hp, features={"optuna_hpo": False}))
        self.assertEqual(errs(hp, features={"optuna_hpo": True}), [])
        cu = wf(execution_mode="custom")
        self.assertTrue(any("custom workflow sets the mode" in x for x in errs(cu)))
        cu["steps"][0]["mode"] = "automatic"
        self.assertEqual(errs(cu), [])

    def test_cycles_and_references(self):
        c = wf(steps=[{"id": "a", "type": "research.state", "depends_on": ["b"]}, {"id": "b", "type": "research.state", "depends_on": ["a"]}],
               outputs={})
        self.assertEqual(errs(c), ["steps: dependency cycle"])
        r = wf(steps=[{"id": "a", "type": "research.context", "params": {"query": {"$ref": "inputs.nope"}}},
                      {"id": "b", "type": "research.context", "params": {"query": {"$ref": "steps.c.output.x"}}},
                      {"id": "c", "type": "research.context", "params": {"query": {"$ref": "steps.a.weird"}}},
                      {"id": "d", "type": "research.context", "params": {"query": {"$ref": "bad ref"}}}],
               outputs={"x": "inputs.q", "y": "steps.zz.output", "z": 5})
        e = " | ".join(errs(r))
        for frag in ("unknown input", "upstream step", "invalid reference", "outputs.x", "outputs.y", "outputs.z"):
            self.assertIn(frag, e)
        self.assertTrue(errs(wf(outputs=[])))

    def test_inputs(self):
        d = S.validate(wf(inputs={"q": {"type": "string", "required": True}, "n": {"type": "integer", "default": 3},
                              "o": {"type": "object"}}), ST.REGISTRY)[0]
        self.assertEqual(S.check_inputs(d, {"q": "x"}), ({"q": "x", "n": 3}, []))
        self.assertTrue(S.check_inputs(d, {})[1])
        self.assertTrue(S.check_inputs(d, {"q": 1})[1])
        self.assertTrue(S.check_inputs(d, {"q": "x", "zz": 1})[1])


class Language(unittest.TestCase):
    scope = {"inputs": {"a": {"b": [10, 20]}, "flag": True}, "steps": {"s": {"status": "SUCCEEDED", "output": {"v": 3, "ok": None}}},
             "last": {"best": {"x": 1}}}

    def test_resolve(self):
        self.assertEqual(S.resolve_ref("inputs.a.b.1", self.scope), 20)
        self.assertIsNone(S.resolve_ref("inputs.a.b.9", self.scope))
        self.assertIsNone(S.resolve_ref("steps.s.output.v.deeper", self.scope))
        with self.assertRaises(S.WorkflowError):
            S.resolve_ref("__import__('os')", self.scope)
        self.assertEqual(S.resolve({"x": [{"$ref": "steps.s.output.v"}, 1], "y": {"$ref": "inputs.flag"}}, self.scope),
                         {"x": [3, 1], "y": True})
        self.assertEqual(sorted(S.refs_in({"a": [{"$ref": "x"}, {"b": {"$ref": "y"}}]})), ["x", "y"])

    def test_conditions(self):
        E = lambda c: S.evaluate(c, self.scope)  # noqa: E731
        self.assertTrue(E(None))
        self.assertTrue(E({"ref": "steps.s.output.v", "op": "gt", "value": 2}))
        self.assertTrue(E({"ref": "steps.s.output.v", "op": "le", "value": 3}))
        self.assertFalse(E({"ref": "steps.s.output.v", "op": "lt", "value": 3}))
        self.assertTrue(E({"ref": "steps.s.output.v", "op": "ge", "value": 3}))
        self.assertFalse(E({"ref": "steps.s.status", "op": "gt", "value": 1}))  # non-numeric comparison is false
        self.assertTrue(E({"ref": "steps.s.status", "op": "eq", "value": "SUCCEEDED"}))
        self.assertTrue(E({"ref": "steps.s.status", "op": "ne", "value": "FAILED"}))
        self.assertTrue(E({"ref": "steps.s.status", "op": "in", "value": ["SUCCEEDED"]}))
        self.assertFalse(E({"ref": "steps.s.status", "op": "in", "value": "SUCCEEDED"}))
        self.assertTrue(E({"ref": "inputs.flag", "op": "truthy"}))
        self.assertTrue(E({"ref": "steps.s.output.ok", "op": "falsy"}))
        self.assertFalse(E({"ref": "steps.s.output.ok", "op": "exists"}))
        self.assertTrue(E({"ref": "last.best", "op": "exists"}))
        self.assertTrue(E({"all": [{"ref": "inputs.flag", "op": "truthy"}, {"not": {"ref": "steps.s.output.ok", "op": "truthy"}}]}))
        self.assertTrue(E({"any": [{"ref": "inputs.flag", "op": "falsy"}, {"ref": "inputs.flag", "op": "truthy"}]}))
        self.assertEqual(sorted(S.cond_refs({"all": [{"ref": "a", "op": "truthy"}, {"not": {"ref": "b", "op": "truthy"}}]})), ["a", "b"])
        self.assertEqual(S.cond_refs(None), [])
        e = []
        S.check_cond({"not": {"ref": "inputs.x", "op": "nope"}}, "w", e)
        S.check_cond({"any": [{"ref": "inputs.a", "op": "eq"}]}, "w", e)
        self.assertEqual(len(e), 1)

    def test_default_step_modes(self):
        self.assertEqual(S.default_step_mode("bounded", "execution", "high"), "automatic")
        self.assertEqual(S.default_step_mode("manual", "execution", "high"), "manual")
        self.assertEqual(S.default_step_mode("manual", "deterministic", "low"), "assisted")
        self.assertEqual(S.default_step_mode("assisted", "execution", "high"), "manual")
        self.assertEqual(S.default_step_mode("assisted", "agent", "low"), "assisted")
        self.assertEqual(S.default_step_mode("assisted", "deterministic", "low"), "automatic")


if __name__ == "__main__":
    unittest.main()
