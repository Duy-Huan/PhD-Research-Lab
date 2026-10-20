"""Interface language consistency (EN/VI): every UI string the code passes through the translator has a Vietnamese entry,
the dictionary has no conflicting duplicates, and the navigation/settings labels are translated."""
import _env  # noqa: F401  (must be first)
import re
import unittest
from pathlib import Path

FRONT = _env.ROOT / "frontend"
SRC = (FRONT / "i18n.js").read_text("utf-8")
VI_BODY = SRC[SRC.index("const VI = {"):SRC.index("const PATTERNS = [")]
PAIRS = [(m.group(2), m.group(4)) for m in re.finditer(r"""(['"])((?:\\.|(?!\1).)+?)\1\s*:\s*(['"])((?:\\.|(?!\3).)*?)\3""", VI_BODY)]
KEYS = {k.replace("\\'", "'") for k, _ in PAIRS}
PATTERNS = []
for m in re.finditer(r"^\s*\[/(.+?)/[gimsu]*,", SRC[SRC.index("const PATTERNS = ["):], re.M):
    try:
        PATTERNS.append(re.compile(m.group(1).replace("\\/", "/")))
    except re.error:
        pass
CALL = re.compile(r"""\b(?:T|I18N\.tr|toast|confirm|alert|prompt)\(\s*(['"])((?:\\.|(?!\1).)*?)\1""")
VN = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)


def covered(s: str) -> bool:
    k = s.strip()
    if k in KEYS or any(p.search(k) for p in PATTERNS):
        return True
    m = re.match(r'^([^\w"“(]+)(.*?)([\s:：…]*)$', k)  # leading symbols/emoji and trailing ':' are kept as they are
    return bool(m and m.group(2) in KEYS)


class Translations(unittest.TestCase):
    def test_every_translated_literal_has_a_vietnamese_entry(self):
        missing = []
        for f in [FRONT / "index.html"] + sorted((FRONT / "app").glob("*.js")):
            for m in CALL.finditer(f.read_text("utf-8")):
                s = m.group(2).replace("\\'", "'")
                if "${" in s or VN.search(s) or not re.search(r"[A-Za-z]{3,}", s) or re.fullmatch(r"[\w.\-/:#@]+", s):
                    continue
                if not covered(s):
                    missing.append(f"{f.name}: {s[:90]}")
        self.assertEqual(missing, [], "add these strings to the VI dictionary in frontend/i18n.js")

    def test_no_conflicting_duplicates(self):
        seen, clash = {}, []
        for k, v in PAIRS:
            if k in seen and seen[k] != v:
                clash.append(f"{k!r}: {seen[k]!r} vs {v!r}")
            seen[k] = v
        self.assertEqual(clash, [])

    def test_navigation_and_settings_are_translated(self):
        vi = dict(PAIRS)
        for k in ("Control Center", "Experiment Design", "Workspace & Runs", "Papers & Writer", "Context", "Docker & System",
                  "Guide", "Settings", "Research project", "Cloud AI providers", "Local AI", "Agent engines", "Internet search",
                  "Language & appearance", "More settings", "Runs", "Default project"):
            self.assertIn(k, vi, k)
            self.assertNotEqual(vi[k], k, f"{k} is not translated")

    def test_one_term_for_experiment(self):
        values = " ".join(v for _, v in PAIRS)
        self.assertNotIn("thực nghiệm", values.lower(), "use 'thí nghiệm' (the tool is named 'Thiết kế thí nghiệm')")

    def test_user_data_is_never_translated(self):
        skip = re.search(r"const SKIP = '([^']+)'", SRC).group(1)
        for sel in ("#proj-tag", "textarea", ".md", "code", "pre"):
            self.assertIn(sel, skip)


if __name__ == "__main__":
    unittest.main()
