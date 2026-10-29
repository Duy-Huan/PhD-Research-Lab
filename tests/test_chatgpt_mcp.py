"""FQC-CHATGPT-MCP-662: ChatGPT (chatgpt.com Developer Mode connector) as an MCP client, with all six owner-approved layers.

1 container execution of compute tools, 2 OAuth 2.1 + PKCE S256 with one owner approval in the local app, 3 OpenAI egress
IP allowlist (https://openai.com/chatgpt-connectors.json, best effort per OpenAI), 4 per-client rate limit and auth-failure
lockout, 5 public gateway only while enabled + kill switch, 6 audit and alerts. The gateway is a separate app that serves
only /mcp, /oauth/* and /.well-known/*. Network, tunnel and Docker are MOCKED; OAuth, tokens, MCP and runtime are real.
"""
import base64
import hashlib
import json
import secrets
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import _env

try:
    from backend.tools import chatgpt_gateway as G
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing

PUBLIC = "https://lab-example.trycloudflare.com"
OPENAI_IP = "23.102.140.115"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"chatgpt-{self._testMethodName[:30]}")
        G.reset_for_tests()
        G.set_public_url(PUBLIC)
        G.set_ranges(["23.102.140.112/28", "2603:1030::/32"])
        G.STATE["enabled"] = True  # the real enable() also starts uvicorn and cloudflared (covered separately)
        from fastapi.testclient import TestClient
        self.client = TestClient(G.app, base_url=PUBLIC, client=("127.0.0.1", 50000))
        self.addCleanup(self.client.close)

    def h(self, ip=OPENAI_IP, **extra):
        return {"CF-Connecting-IP": ip, **extra}

    def connect(self):
        """Full DCR + authorization code + PKCE flow, approved once by the owner in the local app."""
        reg = self.client.post("/oauth/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT",
                                                         "token_endpoint_auth_method": "none"}, headers=self.h())
        self.assertEqual(reg.status_code, 201, reg.text)
        client_id = reg.json()["client_id"]
        verifier, challenge = pkce()
        q = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": "st-1",
             "code_challenge": challenge, "code_challenge_method": "S256", "resource": PUBLIC}
        page = self.client.get("/oauth/authorize", params=q, headers={"CF-Connecting-IP": "198.51.100.7"},
                               follow_redirects=False)
        self.assertEqual(page.status_code, 200)
        pending = G.pending_requests()
        self.assertEqual(len(pending), 1)
        rid = pending[0]["id"]
        self.assertEqual(self.client.get(f"/oauth/authorize/wait/{rid}", follow_redirects=False).status_code, 202,
                         "no code before the owner approves")
        G.approve(rid)
        done = self.client.get(f"/oauth/authorize/wait/{rid}", follow_redirects=False)
        self.assertEqual(done.status_code, 302)
        loc = urlsplit(done.headers["location"])
        args = parse_qs(loc.query)
        self.assertEqual(f"{loc.scheme}://{loc.netloc}{loc.path}", REDIRECT)
        self.assertEqual(args["state"], ["st-1"])
        self.assertEqual(args["iss"], [PUBLIC])
        tok = self.client.post("/oauth/token", data={"grant_type": "authorization_code", "code": args["code"][0],
                                                      "redirect_uri": REDIRECT, "client_id": client_id,
                                                      "code_verifier": verifier, "resource": PUBLIC}, headers=self.h())
        self.assertEqual(tok.status_code, 200, tok.text)
        return client_id, tok.json(), args["code"][0], verifier

    def mcp(self, token, method, params=None, ip=OPENAI_IP):
        return self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                                headers=self.h(ip, Authorization=f"Bearer {token}"))


class OAuth(Base):
    def test_discovery_metadata_meets_chatgpt_requirements(self):
        prm = self.client.get("/.well-known/oauth-protected-resource").json()
        self.assertEqual(prm["resource"], PUBLIC)
        self.assertEqual(prm["authorization_servers"], [PUBLIC])
        asm = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(asm["issuer"], PUBLIC)
        self.assertIn("S256", asm["code_challenge_methods_supported"])
        self.assertTrue(asm["authorization_response_iss_parameter_supported"])
        self.assertEqual(asm["registration_endpoint"], PUBLIC + "/oauth/register")
        self.assertEqual(asm["token_endpoint_auth_methods_supported"], ["none"])

    def test_owner_approved_flow_issues_audience_bound_tokens(self):
        _, tok, code, verifier = self.connect()
        self.assertEqual(tok["token_type"], "Bearer")
        self.assertLessEqual(tok["expires_in"], 3600)
        listed = self.mcp(tok["access_token"], "tools/list").json()["result"]["tools"]
        self.assertEqual(sorted(t["name"] for t in listed),
                         ["phdlab_tools_call", "phdlab_tools_describe", "phdlab_tools_job", "phdlab_tools_search"],
                         "ChatGPT reaches tools only through the runtime (isolation, provenance)")
        again = self.client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code,
                                                        "redirect_uri": REDIRECT, "code_verifier": verifier, "resource": PUBLIC},
                                 headers=self.h())
        self.assertEqual(again.json()["error"], "invalid_grant", "codes are single use")

    def test_pkce_redirect_and_resource_are_enforced(self):
        reg = self.client.post("/oauth/register", json={"redirect_uris": ["https://evil.example/cb"]}, headers=self.h())
        self.assertEqual(reg.status_code, 400, "only ChatGPT redirect URIs")
        client_id = self.client.post("/oauth/register", json={"redirect_uris": [REDIRECT]}, headers=self.h()).json()["client_id"]
        verifier, challenge = pkce()
        bad = self.client.get("/oauth/authorize", params={"response_type": "code", "client_id": client_id,
                                                           "redirect_uri": REDIRECT, "code_challenge": challenge,
                                                           "code_challenge_method": "plain", "resource": PUBLIC})
        self.assertEqual(bad.status_code, 400, "S256 only")
        G.reset_pending()
        self.client.get("/oauth/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
                                                     "code_challenge": challenge, "code_challenge_method": "S256",
                                                     "resource": PUBLIC, "state": "s"})
        rid = G.pending_requests()[0]["id"]
        G.approve(rid)
        code = parse_qs(urlsplit(self.client.get(f"/oauth/authorize/wait/{rid}", follow_redirects=False)
                                 .headers["location"]).query)["code"][0]
        wrong = self.client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code,
                                                        "redirect_uri": REDIRECT, "code_verifier": "x" * 50, "resource": PUBLIC},
                                 headers=self.h())
        self.assertEqual(wrong.json()["error"], "invalid_grant")

    def test_denied_request_never_yields_a_code(self):
        client_id = self.client.post("/oauth/register", json={"redirect_uris": [REDIRECT]}, headers=self.h()).json()["client_id"]
        _, challenge = pkce()
        self.client.get("/oauth/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
                                                     "code_challenge": challenge, "code_challenge_method": "S256",
                                                     "resource": PUBLIC, "state": "s"})
        rid = G.pending_requests()[0]["id"]
        G.deny(rid)
        out = self.client.get(f"/oauth/authorize/wait/{rid}", follow_redirects=False)
        self.assertEqual(parse_qs(urlsplit(out.headers["location"]).query)["error"], ["access_denied"])

    def test_refresh_rotates_and_kill_switch_revokes_everything(self):
        client_id, tok, _, _ = self.connect()
        new = self.client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                                      "client_id": client_id, "resource": PUBLIC}, headers=self.h()).json()
        self.assertNotEqual(new["access_token"], tok["access_token"])
        reuse = self.client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                                        "client_id": client_id, "resource": PUBLIC}, headers=self.h())
        self.assertEqual(reuse.json()["error"], "invalid_grant", "rotated refresh tokens are single use")
        self.assertEqual(self.mcp(new["access_token"], "ping").status_code, 200)
        G.kill_switch()
        self.assertEqual(self.mcp(new["access_token"], "ping").status_code, 404, "gateway off after the kill switch")
        G.STATE["enabled"] = True
        self.assertEqual(self.mcp(new["access_token"], "ping").status_code, 401, "and every token was revoked")


class Boundary(Base):
    def test_only_mcp_and_oauth_paths_are_served(self):
        for path in ("/api/config", "/", "/api/tools", "/docs"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_missing_or_foreign_token_gets_a_challenge(self):
        r = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers=self.h())
        self.assertEqual(r.status_code, 401)
        self.assertIn('resource_metadata="' + PUBLIC + '/.well-known/oauth-protected-resource"', r.headers["www-authenticate"])
        self.assertEqual(self.mcp("phg_not_a_chatgpt_token", "ping").status_code, 401)

    def test_ip_allowlist_applies_to_server_to_server_calls_not_the_owner_browser(self):
        _, tok, _, _ = self.connect()  # the authorize step came from a non-OpenAI browser IP
        self.assertEqual(self.mcp(tok["access_token"], "ping", ip="203.0.113.9").status_code, 403)
        self.assertEqual(self.mcp(tok["access_token"], "ping").status_code, 200)
        G.set_ranges(None)  # list unavailable: fail closed for /mcp
        self.assertEqual(self.mcp(tok["access_token"], "ping").status_code, 403)

    def test_rate_limit_and_auth_failure_lockout(self):
        _, tok, _, _ = self.connect()
        G.set_rate_limit(per_minute=5)
        codes = [self.mcp(tok["access_token"], "ping").status_code for _ in range(7)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5:], [429, 429])
        G.set_rate_limit(per_minute=1000)
        for _ in range(10):
            self.mcp("wrong-token", "ping", ip="23.102.140.120")
        self.assertEqual(self.mcp(tok["access_token"], "ping", ip="23.102.140.120").status_code, 429,
                         "an address with repeated bad tokens is locked out")

    def test_audit_records_decisions_and_alerts(self):
        _, tok, _, _ = self.connect()
        self.mcp(tok["access_token"], "ping", ip="203.0.113.9")
        events = G.audit_tail(50)
        self.assertTrue(any(e.get("decision") == "deny_ip" and e.get("ip") == "203.0.113.9" for e in events))
        self.assertNotIn(tok["access_token"], json.dumps(events), "tokens are never logged")
        self.assertTrue(any(a["kind"] == "deny_ip" for a in G.status()["alerts"]))


class Isolation(Base):
    def install(self, perms=("compute",)):
        from backend.tools import registry as R
        folder = R.tools_root() / "stats_mean" / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({"id": "stats_mean", "kind": "python", "description": "mean",
                                                      "permissions": list(perms), "execution": {"entry": "tool.py"},
                                                      "input_schema": {"type": "object"}}))
        (folder / "tool.py").write_text("import json,sys\nprint(json.dumps({'ok': 1}))\n")

    def test_chatgpt_compute_runs_in_a_container_and_host_execution_is_refused(self):
        from backend.tools import adapters, profiles, registry as R
        from backend.tools.runtime import Runtime
        self.install()
        g = profiles.client_grant("chatgpt", "mcp:chatgpt:s")
        self.assertEqual(g.isolation, "container")
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        seen = []

        def fake_container(spec, args, ctx):
            seen.append(spec)
            return {"ok": 1}
        with patch.object(adapters.Container, "execute", side_effect=fake_container), \
                patch.object(adapters.Python, "execute", side_effect=AssertionError("host python execution")):
            job = rt.run("stats_mean", {}, g)
        self.assertEqual(job["status"], "succeeded", job.get("error"))
        self.assertEqual(seen[0].kind, "container")
        self.assertEqual(seen[0].execution["command"], ["python", "-I", "/tool/tool.py"])
        denied = rt.run("sandbox_run_code", {"code": "print(1)"}, g)
        self.assertEqual(denied["status"], "denied", "host-executing native tools are refused under container isolation")
        self.assertEqual(rt.run("research_get_current_state", {}, g)["status"], "succeeded", "in-app read tools stay usable")


class LocalControls(Base):
    def test_owner_approves_through_the_local_api_and_ranges_refresh_daily(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        client_id = self.client.post("/oauth/register", json={"redirect_uris": [REDIRECT]}, headers=self.h()).json()["client_id"]
        _, challenge = pkce()
        self.client.get("/oauth/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
                                                     "code_challenge": challenge, "code_challenge_method": "S256",
                                                     "resource": PUBLIC, "state": "s"})
        with TestClient(app, headers={"X-PhDLab-Client": "ui"}) as local:
            pending = local.get("/api/tools/clients/chatgpt").json()["pending"]
            self.assertEqual(len(pending), 1)
            ok = local.post("/api/tools/clients/chatgpt/approve", json={"request_id": pending[0]["id"]})
            self.assertEqual(ok.json()["status"], "approved")
            self.assertEqual(local.post("/api/tools/clients/chatgpt/approve", json={"request_id": "nope"}).status_code, 400)
        calls = []
        stop = __import__("threading").Event()
        with patch.object(G, "refresh_ranges", side_effect=lambda: calls.append(1) or (stop.set() if len(calls) >= 2 else None)):
            G.ranges_loop(stop, interval_s=0.01)
        self.assertEqual(len(calls), 2)


class Tunnel(Base):
    def test_cloudflared_url_parsing_and_kill_switch_stops_everything(self):
        self.assertEqual(G.parse_tunnel_url("INF |  https://abc-def.trycloudflare.com  |"), "https://abc-def.trycloudflare.com")
        self.assertIsNone(G.parse_tunnel_url("no url here"))

        class Proc:
            killed = False

            def poll(self):
                return None if not self.killed else 0

            def kill(self):
                self.killed = True

            def wait(self, timeout=None):
                return 0
        proc = Proc()
        G.STATE["tunnel"] = proc
        G.STATE["enabled"] = True
        out = G.kill_switch()
        self.assertTrue(proc.killed)
        self.assertFalse(G.status()["enabled"])
        self.assertTrue(out["tokens_revoked"])


if __name__ == "__main__":
    unittest.main()
