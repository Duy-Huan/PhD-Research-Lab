import _env  # noqa: F401  (must be first)
import unittest

from backend.gateway import events as E


class Normalizers(unittest.TestCase):
    def test_codex(self):
        self.assertEqual(E.codex({"type": "thread.started", "thread_id": "t1"})[0]["session_id"], "t1")
        m = E.codex({"type": "item.completed", "item": {"type": "agent_message", "text": "hi"}})[0]
        self.assertEqual((m["type"], m["text"]), ("text_delta", "hi"))
        self.assertEqual(E.codex({"type": "turn.failed", "error": {"message": "boom"}})[0]["type"], "error")

    def test_claude(self):
        self.assertEqual(E.claude({"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": "a"}}})[0]["text"], "a")
        self.assertEqual(E.claude({"type": "stream_event", "event": {"delta": {"type": "input_json_delta"}}}), [])
        self.assertEqual(E.claude({"type": "result", "subtype": "success", "result": "done", "is_error": False})[0]["final_text"], "done")
        self.assertEqual(E.claude({"type": "result", "subtype": "error_max_turns", "is_error": True})[0]["type"], "error")
        self.assertEqual(E.claude({"type": "system", "subtype": "api_retry", "attempt": 2, "error": "rate_limit"})[0]["state"], "retry")

    def test_agy(self):
        self.assertEqual(E.agy({"event": "step_update", "step_update": {"text_delta": "x"}})[0]["text"], "x")
        tool = E.agy({"event": "step_update", "step_update": {"step_type": "tool", "tool_name": "run_command", "state": "DONE",
                                                               "tool_info": {"error": {"message": "denied"}}}})[0]
        self.assertEqual((tool["type"], tool["is_error"]), ("tool_result", True))
        self.assertEqual(E.agy({"event": "result", "result": {"status": "CANCELED"}})[0]["type"], "error")

    def test_gemini(self):
        self.assertEqual(E.gemini({"type": "message", "role": "assistant", "content": "y"})[0]["text"], "y")
        self.assertEqual(E.gemini({"type": "message", "role": "user", "content": "q"}), [])
        self.assertEqual(E.gemini({"type": "tool_use", "tool_name": "read_file"})[0]["type"], "tool_call")

    def test_unknown_events_are_reported_not_guessed(self):
        for f in E.NORMALIZERS.values():
            out = f({"type": "brand_new", "event": "brand_new"})
            self.assertEqual(out[0]["type"], "status")
            self.assertEqual(out[0]["raw_type"], "brand_new")
        with self.assertRaises(ValueError):
            E.ev("vendor_specific")


if __name__ == "__main__":
    unittest.main()
