"""Deterministic stdio protocol peer; never calls a provider."""
import json
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "ok"


def emit(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    obj = json.loads(line)
    method, ident = obj.get("method"), obj.get("id")
    if method == "initialize":
        if mode == "eof":
            break
        if mode == "noise":
            print("not-json", flush=True)
            emit({"method": "status", "params": {}})
        if mode == "startup_fail":
            emit({"id": ident, "error": {"message": "unsupported initialize"}})
        else:
            emit({"id": ident, "result": {}})
    elif method in ("thread/start", "thread/resume"):
        emit({"id": ident, "result": {"thread": {"id": obj["params"].get("threadId", "thread-new-123456")}}})
    elif method == "turn/start":
        emit({"id": ident, "result": {"turn": {"id": "turn1"}}})
        if mode == "approval":
            emit({"id": 100, "method": "item/commandExecution/requestApproval", "params": {}})
        else:
            emit({"method": "item/agentMessage/delta", "params": {"delta": "hello"}})
            if mode in ("tools", "forbidden"):
                tool = {"type": "commandExecution", "command": "cat C:/private/.env" if mode == "forbidden" else "echo test"}
                for event in ("item/started", "item/completed"):
                    emit({"method": event, "params": {"item": tool}})
            if mode == "server_error":
                emit({"method": "error", "params": {"error": "fixture turn error", "willRetry": False}})
            emit({"method": "turn/completed", "params": {"turn": {"status": "failed" if mode == "turn_fail" else "interrupted" if mode == "interrupted" else "completed"}}})
    elif method == "model/list":
        if mode == "catalog_error":
            emit({"id": ident, "error": {"message": "catalog denied"}})
        else:
            emit({"id": ident, "result": {"data": [{"model": "catalog-model"}, {"model": "catalog-model"}, {}]}})
