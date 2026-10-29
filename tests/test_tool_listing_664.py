"""FQC-TOOL-LISTING-664 (agent/PLAN_6.6.4_L3.md A12): the tool registry listing builds its index once.

Found by the 6.6.4 gate: /api/tools took about 1.3 s while the other AI tools requests took about 5 ms, so the AI tools
settings list painted late and the browser audit read a half-rendered page. listing() and search() resolved every tool
against a freshly rebuilt index (59 rebuilds, mostly pydantic schema generation of the mission capabilities)."""
import time
import unittest
from unittest.mock import patch

import _env
from backend.tools import registry as R


class ToolListing(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        R.REGISTRY.listing()  # warm imports and availability probes

    def count_builds(self, fn):
        real = R.Registry._all
        calls = []

        def counted(registry):
            calls.append(1)
            return real(registry)
        with patch.object(R.Registry, "_all", counted):
            result = fn()
        return result, len(calls)

    def test_listing_and_search_build_the_index_once(self):
        listed, builds = self.count_builds(R.REGISTRY.listing)
        self.assertEqual(builds, 1)
        self.assertGreater(listed["count"], 40)
        found, builds = self.count_builds(lambda: R.REGISTRY.search("library citations"))
        self.assertEqual(builds, 1)
        self.assertEqual(found[0]["id"], "library.search")

    def test_the_listing_matches_resolving_each_tool(self):
        listed = R.REGISTRY.listing()
        for entry in listed["tools"]:
            spec = R.REGISTRY.resolve(entry["id"])
            self.assertEqual((entry["id"], entry["version"]), (spec.id, spec.version))

    def test_filters_narrow_the_listing(self):
        native = R.REGISTRY.listing(kind="native")
        self.assertTrue(native["tools"] and all(t["kind"] == "native" for t in native["tools"]))
        library = R.REGISTRY.listing(capability="library")
        self.assertEqual(sorted(t["id"] for t in library["tools"]), ["library.passages", "library.search"])

    def test_an_unknown_tool_is_still_not_found_with_suggestions(self):
        from backend.tools.spec import ToolError
        with self.assertRaises(ToolError) as e:
            R.REGISTRY.resolve("library.serch")
        self.assertEqual(e.exception.code, "not_found")
        self.assertIn("library.search", e.exception.hint)

    def test_listing_is_fast(self):
        t0 = time.perf_counter()
        for _ in range(5):
            R.REGISTRY.listing()
        self.assertLess((time.perf_counter() - t0) / 5, 0.3)  # was about 1.3 s per listing


if __name__ == "__main__":
    unittest.main()
