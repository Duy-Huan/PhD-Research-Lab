"""Live MCP Inference Client Test Suite.

PhD Lab acts as an MCP Client (backend.providers.mcp_agent._complete),
communicating with a test-owned live HTTP server that exposes an MCP
inference tool powered by the real local LM Studio phi-4 model.
"""
import asyncio
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

from tests.live_e2e.conftest_or_setup import (
    LMSTUDIO_BASE_URL,
    LOCAL_MODEL,
    check_lmstudio_health,
    configure_live_phi4,
    log_llm_call,
)
from backend.core import config as C
from backend.providers import mcp_agent


class LiveMCPInferenceHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet test output

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        req = json.loads(raw.decode("utf-8"))
        method = req.get("method")
        rid = req.get("id")

        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return

        if method == "initialize":
            res = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-live-mcp-server", "version": "1.0"}
            }
        elif method == "tools/list":
            res = {
                "tools": [{
                    "name": "phi4_inference",
                    "description": "Live local Phi-4 inference tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "system": {"type": "string"},
                            "messages": {"type": "array"},
                            "model": {"type": "string"},
                            "max_tokens": {"type": "integer"},
                            "temperature": {"type": "number"}
                        },
                        "required": ["system", "messages"]
                    }
                }]
            }
        elif method == "tools/call":
            args = req.get("params", {}).get("arguments", {})
            user_msg = "Hello"
            for m in args.get("messages", []):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
            
            # Forward live request to LM Studio Phi-4
            phi4_payload = {
                "model": LOCAL_MODEL,
                "messages": [
                    {"role": "system", "content": args.get("system", "")},
                    {"role": "user", "content": user_msg}
                ],
                "max_tokens": args.get("max_tokens", 80),
                "temperature": args.get("temperature", 0.1)
            }
            if "qwen3.5" in LOCAL_MODEL:
                phi4_payload.update(chat_template_kwargs={"enable_thinking": False}, reasoning_effort="none")
            try:
                lms_req = Request(
                    f"{LMSTUDIO_BASE_URL}/chat/completions",
                    data=json.dumps(phi4_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urlopen(lms_req, timeout=30) as resp:
                    lms_data = json.loads(resp.read().decode("utf-8"))
                    text = lms_data["choices"][0]["message"]["content"]
            except Exception as e:
                text = f"Fallback error: {e}"

            res = {
                "content": [{"type": "text", "text": text.strip()}]
            }
        else:
            res = {"error": f"Unknown method: {method}"}

        out = json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class TestLiveMCPInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        health = check_lmstudio_health()
        if not health["online"] or not health["has_phi4"]:
            raise unittest.SkipTest(f"LM Studio phi-4 not available at {LMSTUDIO_BASE_URL}: {health}")
        configure_live_phi4()

        # Start live in-process test MCP server on ephemeral loopback port
        cls.server = HTTPServer(("127.0.0.1", 0), LiveMCPInferenceHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_live_mcp_client_inference_with_phi4(self):
        """PhD Lab connects to live MCP HTTP endpoint and executes tool-based Phi-4 inference."""
        cfg = C.load_config()
        cfg["mcp_agent"] = {
            "enabled": True,
            "url": f"http://127.0.0.1:{self.port}/mcp",
            "tool": "phi4_inference",
            "timeout_s": 30
        }
        
        user_prompt = "Reply with exactly: LIVE_MCP_PHI4_VERIFIED"
        t0 = time.perf_counter()
        result = asyncio.run(mcp_agent._complete(
            cfg=cfg,
            system="You are an MCP inference agent.",
            messages=[{"role": "user", "content": user_prompt}],
            model=LOCAL_MODEL,
            max_tokens=50,
            temperature=0.0
        ))
        latency = time.perf_counter() - t0
        log_llm_call("mcp_agent", user_prompt, result, latency, model=LOCAL_MODEL, engine="mcp")

        self.assertIsInstance(result, str)
        self.assertTrue(len(result.strip()) > 0)
        self.assertIn("LIVE_MCP_PHI4_VERIFIED", result)


if __name__ == "__main__":
    unittest.main()
