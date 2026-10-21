"""CLI-agent firewall: allowed / denied roots, path checks, secrets, the audit of tool calls, per-CLI workspace rules,
the web / file MCP tools (public URLs only) and the grants every CLI turn receives."""
import _env  # noqa: F401  (must be first)
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

from backend.agent import mcp_policy
from backend.core import config
from backend.providers import firewall as F, mcp_tools as MT


class Roots(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("fw-" + self._testMethodName[:20])

    def test_allowed_and_denied(self):
        a = F.allowed_roots()
        self.assertEqual(set(a), {"data", "references", "workspace"})
        denied = F.denied_roots()
        self.assertIn((config.ROOT / "backend").resolve(), denied)
        self.assertIn((config.ROOT / "start.py").resolve(), denied)
        self.assertFalse(any(F._inside(a["data"], d) for d in denied))  # the active project stays reachable

    def test_check(self):
        (config.data_dir() / "notes.md").write_text("x", "utf-8")
        self.assertEqual(F.check("notes.md", "data").name, "notes.md")
        self.assertEqual(F.check("", "references"), F.allowed_roots()["references"])
        for path, root, why in (("x", "code", "root must"), ("../x", "data", "without"), ("C:/x", "data", "without"),
                                ("config.json", "data", "credentials"), ("cli-space/a", "data", "credentials")):
            with self.subTest(path), self.assertRaisesRegex(F.FirewallError, why):
                F.check(path, root)
        other = config.create_project("fw-other")["data_dir"]
        _env.fresh_project("fw-third")
        with mock.patch.object(F, "allowed_roots", return_value={"data": Path(config.PROJECTS_ROOT).resolve(),
                                                                 "references": F.allowed_roots()["references"],
                                                                 "workspace": F.allowed_roots()["workspace"]}), \
                mock.patch.object(F, "denied_roots", return_value=[Path(other).resolve()]):
            with self.assertRaisesRegex(F.FirewallError, "another project"):
                F.check(Path(other).name + "/x", "data")
        with mock.patch.object(F, "_norm", side_effect=lambda p: Path("C:/elsewhere") if "zz" in str(p) else Path(p).resolve()):
            with self.assertRaisesRegex(F.FirewallError, "leaves"):
                F.check("zz", "data")

    def test_violation_audit(self):
        self.assertEqual(F.violation(""), "")
        src = str((config.ROOT / "backend" / "app.py")).replace("\\", "/")
        self.assertEqual(F.violation(f"Read {src}"), src)
        self.assertEqual(F.violation(f"cat {F.allowed_roots()['data']}/notes.md"), "")
        self.assertTrue(F.violation(f"type {F.allowed_roots()['data']}/config.json"))
        self.assertEqual(F.violation("C:/Windows/notepad.exe and /tmp/x"), "")  # outside the app: not ours to judge
        self.assertEqual(F.violation("\x00\\\\?\\"), "")

    def test_denied_roots_survive_unreadable_folders(self):
        with mock.patch.object(Path, "iterdir", side_effect=OSError("denied")):
            self.assertEqual(F.denied_roots(), [])


class Workspace(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("fw-ws")
        self.ws = config.data_dir() / "cli-space" / "x" / "sessions" / "s1" / "workspace"
        self.ws.mkdir(parents=True)

    def test_per_cli_rules(self):
        out = F.prepare_workspace("claude_code", self.ws)
        self.assertEqual(out["argv"][0], "--settings")
        rules = json.loads((self.ws / ".claude" / "settings.json").read_text("utf-8"))["permissions"]["deny"]
        self.assertTrue(any("backend/**" in r for r in rules) and "Bash" in rules and "WebFetch" in rules)
        self.assertTrue(any("config.json" in r for r in rules))
        mcp = {"url": "http://127.0.0.1:1/mcp", "token": "tok"}
        F.prepare_workspace("gemini_cli", self.ws, mcp)
        g = json.loads((self.ws / ".gemini" / "settings.json").read_text("utf-8"))
        self.assertEqual(g["mcpServers"]["phd-research-lab"]["httpUrl"], mcp["url"])
        F.prepare_workspace("antigravity", self.ws, mcp)
        self.assertIn("serverUrl", json.loads((self.ws / ".agents" / "mcp_config.json").read_text("utf-8"))["mcpServers"]["phd-research-lab"])
        argv = F.prepare_workspace("codex", self.ws, mcp)["argv"]
        self.assertTrue(any("mcp_servers.phdlab.env" in a and "tok" in a for a in argv))
        self.assertEqual(F.prepare_workspace("feynman", self.ws)["argv"], [])
        self.assertIn("off limits", (self.ws / "FIREWALL.md").read_text("utf-8"))


def _addr(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


class Web(unittest.TestCase):
    def test_public_url(self):
        for url, why in (("ftp://x", "only public"), ("http://localhost:8765", "local"), ("http://a.local", "local"),
                         ("https://", "only public")):
            with self.subTest(url), self.assertRaisesRegex(F.FirewallError, why):
                F.public_url(url)
        with mock.patch("socket.getaddrinfo", return_value=_addr("10.0.0.7")):
            with self.assertRaisesRegex(F.FirewallError, "private"):
                F.public_url("https://intranet.example")
        with mock.patch("socket.getaddrinfo", side_effect=OSError("nx")):
            with self.assertRaisesRegex(F.FirewallError, "resolve"):
                F.public_url("https://nx.example")
        with mock.patch("socket.getaddrinfo", return_value=_addr("93.184.216.34")):
            self.assertEqual(F.public_url("https://example.com/a"), "https://example.com/a")


class Tools(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("fw-tools")

    def res(self, name, args):
        return MT.call(name, args)["structuredContent"]["result"]

    def test_web_tools(self):
        src = [{"id": "S1", "kind": "paper", "title": "T", "url": "https://x", "abstract": "a"}]
        with mock.patch("backend.knowledge.websearch.search", return_value={"sources": src, "errors": []}):
            r = self.res("web_search", {"query": "vision transformers", "kind": "papers", "n": 3})
        self.assertEqual(r["sources"][0]["title"], "T")
        with mock.patch("socket.getaddrinfo", return_value=_addr("93.184.216.34")), \
                mock.patch("backend.knowledge.websearch.read_page", return_value="page text"):
            self.assertEqual(self.res("web_fetch", {"url": "https://example.com"})["text"], "page text")
        with self.assertRaises(F.FirewallError):
            MT.call("web_fetch", {"url": "http://127.0.0.1:8765/api/config"})

    def test_file_tools(self):
        d = config.data_dir()
        (d / "notes").mkdir()
        (d / "notes" / "a.md").write_text("hello", "utf-8")
        from pdfgen import make_pdf
        (config.refs_dir() / "p.pdf").write_bytes(make_pdf([[(12, "pruning paper")]]))
        names = [e["name"] for e in self.res("files_list", {"root": "data"})["entries"]]
        self.assertIn("notes", names)
        self.assertNotIn("config.json", names)
        self.assertEqual(self.res("files_read", {"root": "data", "path": "notes/a.md", "max_chars": 200})["text"], "hello")
        self.assertIn("pruning", self.res("files_read", {"root": "references", "path": "p.pdf"})["text"])
        with self.assertRaises(F.FirewallError):
            MT.call("files_list", {"root": "data", "path": "notes/a.md"})
        with self.assertRaises(F.FirewallError):
            MT.call("files_read", {"root": "data", "path": "notes"})

    def test_grants_cover_read_tools_only(self):
        g = mcp_policy.grant_for_cli("run:x")
        self.assertTrue(g["mcp_url"].endswith("/mcp"))
        self.assertIn("web_search", g["mcp_tools"])
        self.assertNotIn("research_record_decision", g["mcp_tools"])
        self.assertEqual(mcp_policy.lookup(g["mcp_token"])["tools"], sorted(g["mcp_tools"]))
        mcp_policy.revoke(g["mcp_token"])
        self.assertEqual(mcp_policy.propose("tìm trên internet bài mới nhất", ["web_search"])[0]["tool"], "web_search")


class Launch(unittest.TestCase):
    """The connector applies the firewall before the process starts and stops it on a denied path."""

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("fw-launch")

    def test_tool_call_on_app_source_stops_the_agent(self):
        from backend.providers import cli as C, cli_space as W
        conn = C.CONNECTORS["claude_code"]
        src = str((config.ROOT / "backend" / "app.py")).replace("\\", "/")
        script = ("import json,sys,time\n"
                  "print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','name':'Read',"
                  f"'input':{{'file_path':'{src}'}}}}]}}}}),flush=True)\ntime.sleep(20)\n")
        sess = W.open_session("claude_code", "fw-test-1", "review")
        with mock.patch.object(conn, "health", return_value={"state": "CONNECTED", "detail": ""}), \
                mock.patch.object(conn, "argv", return_value=[sys.executable, "-c", script]):
            evs = list(conn.stream_message("hi", {"cwd": sess["cwd"], "mcp_url": "http://127.0.0.1:1/mcp", "mcp_token": "t"}))
        err = [e for e in evs if e["type"] == "error"]
        self.assertTrue(err and "firewall" in err[0]["message"], evs)
        self.assertTrue((Path(sess["cwd"]) / ".claude" / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
