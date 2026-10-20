"""stdio ↔ HTTP bridge for MCP clients that only launch stdio servers (e.g. Claude Desktop).

claude_desktop_config.json:
  {"mcpServers": {"phd-research-lab": {"command": "python", "args": ["C:/path/to/PhD-Research-Lab/mcp_stdio_bridge.py"]}}}
The PhD Research Lab app must be running (run.bat). Uses only the Python standard library.
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("PHDLAB_MCP_URL", "http://127.0.0.1:8765/mcp")
TOKEN = os.environ.get("PHDLAB_MCP_TOKEN", "")  # v3.4: set when the app requires an MCP token (Configuration → MCP)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        req = urllib.request.Request(URL, data=json.dumps(msg).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3700) as r:
                body = r.read().decode()
        except Exception as e:
            if msg.get("id") is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32000, "message": f"PhD Research Lab not reachable at {URL}: {e}"}}), flush=True)
            continue
        if body.strip() and msg.get("id") is not None:
            print(body.strip(), flush=True)


if __name__ == "__main__":
    main()
