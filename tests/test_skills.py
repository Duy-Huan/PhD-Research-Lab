"""Skills: parsing, layers (built-in → user → project), aliases, "/" matching, the researcher's own skills."""
import _env  # noqa: F401  (must be first)
import unittest

from backend.agent import AIWSError, skills
from backend.core import config

GOOD = "---\nname: tomtat\ntitle: Tóm tắt\ndescription: tóm tắt bài\nusage: [file]\ncategory: research\nagent: reviewer\n" \
       "mode: chat\nrisk: 0\naliases: [tt, sum]\n---\nTóm tắt theo mẫu.\n"


class Parse(unittest.TestCase):
    def test_valid_skill(self):
        s = skills.parse(GOOD, "user")
        self.assertEqual((s["name"], s["agent"], s["mode"], s["risk"], s["origin"]), ("tomtat", "reviewer", "chat", 0, "user"))
        self.assertEqual(s["aliases"], ["tt", "sum"])
        self.assertEqual(s["usage"], "[file]")  # a usage hint in brackets stays text
        self.assertEqual(s["instructions"], "Tóm tắt theo mẫu.")

    def test_comments_booleans_and_defaults(self):
        s = skills.parse("---\n# a comment\nname: ab\nflag: true # trailing\n\n---\n", "builtin")
        self.assertEqual((s["title"], s["category"], s["mode"], s["provider"]), ("ab", "research", "chat", "app"))

    def test_invalid_skills_are_refused(self):
        bad = {
            "no front matter": "name: x",
            "bad line": "---\nname ab\n---\n",
            "bad name": "---\nname: A!\n---\n",
            "bad agent": "---\nname: ab\nagent: coder\n---\n",
            "bad risk": "---\nname: ab\nrisk: 7\n---\n",
            "text risk": "---\nname: ab\nrisk: high\n---\n",
            "bad pipeline": "---\nname: ab\nmode: run\npipeline: nope\n---\n",
        }
        for why, text in bad.items():
            with self.subTest(why), self.assertRaises(AIWSError):
                skills.parse(text)


class Registry(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("skills-" + self._testMethodName[:20])
        self.addCleanup(lambda: [f.unlink() for f in (config.GLOBAL_DIR / "skills").glob("*.md")]
                        if (config.GLOBAL_DIR / "skills").exists() else None)

    def test_builtins_cover_the_research_workflow(self):
        names = {s["name"] for s in skills.catalog()}
        for n in ("help", "status", "outline", "lit", "deepresearch", "gap", "hypothesis", "plan", "idea", "code", "run",
                  "results", "write", "latex", "review", "verify", "remember", "compare"):
            self.assertIn(n, names)
        self.assertEqual(skills.errors(), [])
        cats = [s["category"] for s in skills.catalog()]
        self.assertEqual(cats, sorted(cats, key=list(skills.CATEGORIES).index))
        self.assertNotIn("instructions", skills.catalog()[0])

    def test_match_aliases_and_unknown(self):
        s, arg = skills.match("/lit  vision transformers ")
        self.assertEqual((s["name"], arg), ("lit", "vision transformers"))
        self.assertEqual(skills.match("/literature x")[0]["name"], "lit")
        self.assertEqual(skills.match("/help")[1], "")
        self.assertIsNone(skills.match("hello /lit"))
        with self.assertRaisesRegex(AIWSError, "Unknown command /nope"):
            skills.match("/nope")

    def test_user_and_project_skills_override_and_delete(self):
        s = skills.save_user(GOOD, "user")
        self.assertEqual(s["origin"], "user")
        self.assertEqual(skills.get("tt")["name"], "tomtat")
        proj = GOOD.replace("Tóm tắt theo mẫu.", "Project version.")
        self.assertEqual(skills.save_user(proj, "project")["instructions"], "Project version.")  # project wins
        self.assertEqual(skills.delete_user("tomtat")["deleted"], "tomtat")  # project file first
        self.assertEqual(skills.get("tomtat")["origin"], "user")
        skills.delete_user("tomtat")
        with self.assertRaises(AIWSError):
            skills.get("tomtat")
        with self.assertRaisesRegex(AIWSError, "built-in"):
            skills.delete_user("lit")
        with self.assertRaises(AIWSError):
            skills.save_user(GOOD, "global")

    def test_a_broken_file_is_reported_not_fatal(self):
        d = config.data_dir() / "skills"
        d.mkdir(parents=True, exist_ok=True)
        (d / "broken.md").write_text("no front matter", "utf-8")
        self.assertIn("lit", skills.load())
        self.assertTrue(any(e["file"] == "broken.md" for e in skills.errors()))


if __name__ == "__main__":
    unittest.main()
