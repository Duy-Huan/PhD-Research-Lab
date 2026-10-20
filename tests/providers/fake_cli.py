"""Fake vendor CLI for the provider contract tests: reads the prompt from stdin, prints JSONL in the vendor's format.

    python fake_cli.py <codex|claude|agy|gemini> [ok|auth|rate|slow|crash]
The answer reports the prompt size and whether ANY vendor API-key variable reached the process (cost-guard check).
"""
import json
import os
import sys
import time

fmt, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "ok")
prompt = sys.stdin.read()
if fmt == "agy":
    prompt = json.loads(prompt.splitlines()[0])["message"]["content"]
keys = [k for k in ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY") if os.environ.get(k)]
answer = f"chars={len(prompt)} keys={','.join(keys) or 'none'} hyp={'HYPE-002' in prompt} restricted={'FAIL-001' in prompt}"


def out(o):
    print(json.dumps(o), flush=True)


if mode == "slow":
    time.sleep(30)
if mode == "crash":
    print("fatal: something broke", file=sys.stderr, flush=True)
    sys.exit(3)
err = {"auth": "Authentication required: please log in", "rate": "429 rate limit exceeded"}.get(mode)
if fmt == "codex":
    out({"type": "thread.started", "thread_id": "th-123456"})
    if err:
        out({"type": "turn.failed", "error": {"message": err}})
        sys.exit(1)
    out({"type": "item.completed", "item": {"type": "agent_message", "text": answer}})
    out({"type": "turn.completed", "usage": {"input_tokens": 10}})
elif fmt == "claude":
    out({"type": "system", "subtype": "init", "session_id": "sess-abcdef", "model": "fake"})
    if err:
        out({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": err})
        sys.exit(1)
    for part in (answer[:10], answer[10:]):
        out({"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": part}}})
    out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__phd-research-lab__research_get_failures", "id": "t1"}]}})
    out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}})
    out({"type": "result", "subtype": "success", "is_error": False, "result": answer, "session_id": "sess-abcdef", "usage": {}})
elif fmt == "agy":
    out({"event": "init", "conversation_id": "conv-1234567"})
    if err:
        out({"event": "result", "result": {"status": "ERROR", "error": {"message": err}}})
        sys.exit(1)
    out({"event": "step_update", "step_update": {"text_delta": answer}})
    out({"event": "result", "result": {"status": "SUCCESS", "response": answer, "conversation_id": "conv-1234567", "usage": {}}})
elif fmt == "gemini":
    out({"type": "init", "session_id": "g-1234567", "model": "fake"})
    if err:
        out({"type": "error", "message": err})
        sys.exit(1)
    out({"type": "message", "role": "assistant", "content": answer})
    out({"type": "result", "status": "success", "response": answer})
