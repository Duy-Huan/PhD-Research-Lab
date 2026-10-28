"""FQC-COVERAGE-662: engine routing policy (deterministic first, breakers, health, no metered fallback) and the
bounded JSON-schema validator that guards every tool specification, input and output."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import _env
from backend.intelligence import smart_router as R
from backend.knowledge import research_store as S
from backend.tools import schema as V


class Routing(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"route-{self._testMethodName[:30]}", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Routing"))["id"]

    def route(self, **kw):
        return R.preview_route(R.RoutePreviewRequest(topic_id=self.tid, **kw))

    def test_deterministic_and_quota_paths_never_call_a_model(self):
        self.assertEqual(self.route(capability="paper.discover")["llm_calls"], 0)
        paused = self.route(capability="paper.compare", simulate_quota_exhausted=True)
        self.assertEqual((paused["status"], paused["metered_api_fallback"]), ("quota_limited", "disabled"))
        with self.assertRaisesRegex(ValueError, "Unknown capability"):
            self.route(capability="wire.money")

    def test_candidates_are_checked_for_compatibility_breakers_and_health(self):
        with S.db() as c:
            until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            c.execute("INSERT INTO provider_breakers VALUES(?,?,?)", ("phdlab", until, "{}"))
            c.execute("INSERT INTO provider_breakers VALUES(?,?,?)", ("paperorchestra",
                      (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "{}"))
        out = self.route(capability="paper.compare", preferred_engine="codex", fallback_engines=["phdlab", "app"])
        reasons = {c["engine"]: c for c in out["evaluated_candidates"]}
        self.assertEqual(reasons["codex"]["reason"], "Incompatible capability")
        self.assertTrue(reasons["phdlab"]["reason"].startswith("Circuit breaker open"))
        self.assertEqual((out["selected_engine"], out["llm_calls"]), ("app", 1))

        healthy = Mock(health=Mock(return_value={"ready": True, "detail": ""}))
        with patch.object(R.registry, "get", return_value=healthy):
            out = R.preview_route(R.RoutePreviewRequest(topic_id=self.tid, capability="paperorchestra.outline"), persist=False)
        self.assertEqual(out["selected_engine"], "paperorchestra", "an expired breaker no longer blocks")
        with patch.object(R.registry, "get", side_effect=RuntimeError("engine missing")):
            out = self.route(capability="paperorchestra.outline", preferred_engine="paperorchestra")
        self.assertEqual((out["status"], out["evaluated_candidates"][0]["reason"]), ("blocked_no_healthy_engine", "engine missing"))
        with patch.object(R.registry, "get", return_value=Mock(health=Mock(return_value={"ready": False}))):
            out = self.route(capability="paperorchestra.outline", preferred_engine="paperorchestra")
        self.assertEqual(out["evaluated_candidates"][0]["reason"], "Engine not ready")
        with S.db() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM routing_decisions").fetchone()[0], 3, "previews with persist=False are not recorded")


class Schema(unittest.TestCase):
    def test_schema_structure_problems_are_reported(self):
        deep = {"type": "object"}
        for _ in range(V.MAX_DEPTH + 2):
            deep = {"type": "object", "properties": {"x": deep}}
        self.assertIn("nesting exceeds", " ".join(V.schema_errors(deep)))
        self.assertEqual(V.schema_errors([]), ["$: schema must be an object"])
        errors = V.schema_errors({"type": ["string", "decimal"], "pattern": "(", "oneOf": [], "required": "a",
                                  "items": {"type": "nope"}, "additionalProperties": {"type": "bad"},
                                  "anyOf": [{"type": "worse"}], "$defs": {"d": {"type": "odd"}}, "$ref": "http://x"})
        joined = "\n".join(errors)
        for expected in ("unsupported keyword oneOf", "unknown type 'decimal'", "invalid pattern", "$[]: unknown type",
                         "$.*: unknown type", "$|0: unknown type", "$.$defs.d: unknown type", "only local #/$defs",
                         "required must be a list"):
            self.assertIn(expected, joined)
        self.assertEqual(V.schema_errors({"type": "integer", "$ref": "#/$defs/x"}), [])

    def test_values_are_validated_with_json_paths(self):
        schema = {"type": "object", "required": ["n", "s"], "additionalProperties": False,
                  "$defs": {"pos": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 10}},
                  "properties": {"n": {"$ref": "#/$defs/pos"}, "s": {"type": "string", "minLength": 2, "maxLength": 3, "pattern": "^a"},
                                 "k": {"const": 1}, "e": {"enum": ["x"]}, "i": {"type": "integer", "minimum": 1, "maximum": 2},
                                 "l": {"type": "array", "minItems": 1, "maxItems": 1, "items": {"type": "boolean"}},
                                 "u": {"anyOf": [{"type": "string"}, {"type": "null"}]}, "r": {"$ref": "#/$defs/missing"},
                                 "m": {"type": "object", "additionalProperties": {"type": "integer"}}}}
        self.assertEqual(V.validate({"n": 5, "s": "ab", "u": None, "m": {"a": 1}}, schema), [])
        errors = V.validate({"n": 0, "s": "bcdef", "k": 2, "e": "y", "i": True, "l": [], "u": 3, "r": 1, "z": 1, "m": {"a": "x"}}, schema)
        joined = "\n".join(errors)
        for expected in ("$.n: violates exclusiveMinimum 0", "$.s: longer than 3", "$.s: does not match pattern ^a",
                         "$.k: must equal 1", "$.e: must be one of", "$.i: expected integer, got bool", "$.l: fewer than 1 items",
                         "$.u: matches none of anyOf", "$.r: unresolved reference", "$.z: unexpected property", "$.m.a: expected integer"):
            self.assertIn(expected, joined)
        more = "\n".join(V.validate({"n": 10, "s": "a", "i": 3, "l": [1, 2]}, schema))
        for expected in ("violates exclusiveMaximum 10", "shorter than 2", "violates maximum 2", "more than 1 items",
                         "$.l[0]: expected boolean"):
            self.assertIn(expected, more)
        self.assertIn("$.s: required", V.validate({"n": 1}, schema))
        self.assertIn("violates minimum 1", "\n".join(V.validate({"n": 1, "s": "ab", "i": 0}, schema)))
        nested = []
        for _ in range(V.MAX_DEPTH + 2):
            nested = [nested]
        self.assertIn("nesting exceeds", " ".join(V.validate(nested, {"type": "array", "items": {"$ref": "#/$defs/a"},
                                                                       "$defs": {"a": {"type": "array", "items": {"$ref": "#/$defs/a"}}}})))


if __name__ == "__main__":
    unittest.main()
