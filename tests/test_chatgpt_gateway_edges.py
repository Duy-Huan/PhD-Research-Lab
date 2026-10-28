"""FQC-COVERAGE-662 (ChatGPT connector edges): range refresh success/failure, malformed OAuth/MCP requests,
token grant errors, denied authorization, batch MCP, and the enable/kill lifecycle with a fake cloudflared.

Reuses the FQC-CHATGPT-MCP-662 fixture (real OAuth, tokens and MCP; network and tunnel replaced)."""
import io
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import test_chatgpt_mcp as T  # module import: its own test classes are not collected twice

G = T.G


class Edges(T.Base):
    def test_range_refresh_keeps_the_previous_list_on_failure(self):
        payload = {"creationTime": "2026-10-26", "prefixes": [{"ipv4Prefix": "1.2.3.0/24"}, {"ipv6Prefix": "2001:db8::/32"}, {}]}
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(G.refresh_ranges(), {"ok": True, "count": 2, "creationTime": "2026-10-26"})
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            out = G.refresh_ranges()
        self.assertEqual((out["ok"], out["count"]), (False, 2))
        self.assertEqual(G.audit_tail()[-1]["decision"], "ranges_refresh_failed")
        self.assertFalse(G._ip_allowed("not-an-ip"))
        G.set_ranges([])
        self.assertFalse(G._ip_allowed(T.OPENAI_IP), "no published ranges means fail closed")

    def test_malformed_oauth_requests_are_refused(self):
        bad_json = self.client.post("/oauth/register", content=b"{", headers={**self.h(), "Content-Type": "application/json"})
        self.assertEqual(bad_json.json()["error"], "invalid_client_metadata")
        secret = self.client.post("/oauth/register", json={"redirect_uris": [T.REDIRECT], "token_endpoint_auth_method": "client_secret_post"},
                                  headers=self.h())
        self.assertEqual(secret.json()["error"], "invalid_client_metadata")
        self.assertEqual(self.client.post("/oauth/register", json={}, headers=self.h("8.8.8.8")).status_code, 403)
        self.assertEqual(self.client.get("/oauth/authorize/wait/none", follow_redirects=False).status_code, 404)
        self.assertEqual(self.client.post("/oauth/token", data={"grant_type": "password"}, headers=self.h()).json()["error"],
                         "unsupported_grant_type")
        self.assertEqual(self.client.post("/oauth/token", data={"grant_type": "authorization_code", "resource": "https://evil"},
                                          headers=self.h()).json()["error"], "invalid_target")
        self.assertEqual(self.client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "x"},
                                          headers=self.h()).json()["error"], "invalid_grant")
        self.assertEqual(self.client.post("/oauth/token", data={}, headers=self.h("8.8.8.8")).status_code, 403)
        self.assertEqual(self.client.get("/anything/else").status_code, 404)

    def test_denied_authorization_redirects_with_access_denied(self):
        reg = self.client.post("/oauth/register", json={"redirect_uris": [T.REDIRECT]}, headers=self.h()).json()
        _, challenge = T.pkce()
        self.client.get("/oauth/authorize", params={"response_type": "code", "client_id": reg["client_id"], "redirect_uri": T.REDIRECT,
                                                    "state": "s", "code_challenge": challenge, "code_challenge_method": "S256",
                                                    "resource": T.PUBLIC})
        rid = G.pending_requests()[0]["id"]
        G.deny(rid)
        done = self.client.get(f"/oauth/authorize/wait/{rid}", follow_redirects=False)
        self.assertEqual(parse_qs(urlsplit(done.headers["location"]).query)["error"], ["access_denied"])

    def test_mcp_batches_parse_errors_and_invalid_payloads(self):
        _, tokens, _, _ = self.connect()
        auth = self.h(Authorization="Bearer " + tokens["access_token"])
        batch = self.client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                               {"jsonrpc": "2.0", "method": "notifications/initialized"}, "junk"], headers=auth)
        self.assertEqual(len(batch.json()), 1)
        note = self.client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=auth)
        self.assertEqual(note.status_code, 202)
        parse = self.client.post("/mcp", content=b"{", headers={**auth, "Content-Type": "application/json"})
        self.assertEqual(parse.json()["error"]["code"], -32700)
        self.assertEqual(self.client.post("/mcp", json=5, headers=auth).json()["error"]["code"], -32600)
        self.assertEqual(self.client.post("/mcp", json={}, headers=self.h("8.8.8.8")).status_code, 403)

    def test_enable_needs_cloudflared_reports_the_tunnel_and_kill_switch_stops_it(self):
        G.STATE["enabled"] = False
        with patch.object(G.shutil, "which", return_value=None), self.assertRaisesRegex(ValueError, "Install cloudflared"):
            G.enable()
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = io.StringIO("starting\nINF |  https://abc-def.trycloudflare.com  |\n")
        server = MagicMock()
        with patch.object(G.shutil, "which", return_value="cloudflared"), patch.object(G, "refresh_ranges"), \
                patch.object(G.subprocess, "Popen", return_value=proc), patch("uvicorn.Server", return_value=server), \
                patch.object(G, "ranges_loop"):
            out = G.enable(port=8999)
            self.assertEqual(G.STATE["public_url"], "https://abc-def.trycloudflare.com")
            self.assertTrue(out["enabled"])
            self.assertTrue(G.enable()["enabled"], "enabling twice returns the running gateway")
        stop = G.STATE["stop"]
        killed = G.kill_switch()
        self.assertEqual(killed, {"enabled": False, "tokens_revoked": True})
        proc.kill.assert_called_once()
        self.assertTrue(server.should_exit)
        self.assertTrue(stop.is_set())
        quiet = MagicMock()
        quiet.poll.return_value = 1
        quiet.stdout = io.StringIO("")
        with patch.object(G.shutil, "which", return_value="cloudflared"), patch.object(G, "refresh_ranges"), \
                patch.object(G.subprocess, "Popen", return_value=quiet), patch("uvicorn.Server", return_value=MagicMock()):
            with self.assertRaisesRegex(ValueError, "did not report a public URL"):
                G.enable(port=8999)
        quiet.kill.assert_called_once()

    def test_ranges_loop_refreshes_until_stopped(self):
        stop = threading.Event()
        calls = []
        with patch.object(G, "refresh_ranges", side_effect=lambda: calls.append(1) or stop.set()):
            G.ranges_loop(stop, interval_s=0.01)
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
