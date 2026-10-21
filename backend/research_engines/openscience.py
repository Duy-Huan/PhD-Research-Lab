"""Optional official Python runtime client; native science remains in OpenScience."""
from __future__ import annotations

import hashlib
import importlib
import ipaddress
import json
import queue
import re
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.research_engines.contracts import EngineDescriptor, EngineEvent, EngineFailure, EngineResult

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
_locks: dict[str, threading.Lock] = {}
_lock = threading.Lock()


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    base_url: str = "http://127.0.0.1:4096"
    token: str = Field(default="", repr=False)
    timeout_s: int = Field(default=600, ge=5, le=7200)
    request_timeout_s: float = Field(default=3, ge=1, le=10)
    max_artifact_mb: int = Field(default=64, ge=1, le=1024)
    max_artifacts: int = Field(default=32, ge=1, le=200)
    allow_execution: bool = False
    policy_confirmed: bool = False
    qualified_tasks: list[str] = Field(default_factory=list)
    model_provider: str = ""
    model_id: str = ""

    @field_validator("token")
    @classmethod
    def single_line_token(cls, value):
        if "\r" in value or "\n" in value:
            raise ValueError("Deployment token must be single-line")
        return value

    @field_validator("qualified_tasks")
    @classmethod
    def known_capabilities(cls, value):
        if any(k not in ("literature", "analysis", "prototype", "review") for k in value):
            raise ValueError("Unknown research task capability")
        return list(dict.fromkeys(value))

    @field_validator("base_url")
    @classmethod
    def loopback(cls, value):
        url = urlsplit(value)
        try:
            local = ipaddress.ip_address(url.hostname or "").is_loopback
            port = url.port
        except ValueError:
            local, port = False, None
        if not local or url.scheme not in ("http", "https") or url.username or url.password or url.query or url.fragment or url.path not in ("", "/") or port == 0:
            raise ValueError("OpenScience must use an explicit loopback HTTP(S) origin")
        return value.rstrip("/")


def settings() -> Settings:
    from backend.core.config import load_config
    return Settings.model_validate(load_config().get("openscience") or {})


def job_path(job_id: str) -> Path:
    from backend.core.config import data_dir
    if not re.fullmatch(r"ej-[0-9a-f]{20}", job_id):
        raise ValueError("Invalid engine job id")
    return data_dir() / "research-engines" / "jobs" / (job_id + ".json")


def read_job(job_id: str) -> dict:
    return json.loads(job_path(job_id).read_text("utf-8"))


def save_job(record: dict) -> None:
    from backend.agent import write_json
    if not re.fullmatch(r"ej-[0-9a-f]{20}", record["id"]):
        raise ValueError("Invalid engine job id")
    # A project switch while observing must never write the old journal into the new project.
    workspace = Path(record["workspace"])
    write_json(workspace.parent.parent / "jobs" / (record["id"] + ".json"), record)


def policy(allow_execution: bool) -> dict:
    rules = {"*": "ask", "external_directory": "deny", "compute": "deny", "modal": "deny", "task": "deny",
             "read": "allow", "skill": "allow", "glob": "allow", "grep": "allow", "list": "allow"}
    rules.update({name: "ask" if allow_execution else "deny" for name in ("bash", "edit", "python", "r", "scientific_capability")})
    return rules


class OpenScienceEngine:
    descriptor = EngineDescriptor(id="openscience", capabilities=["literature", "analysis", "prototype", "review"],
                                  transport="official-runtime-sdk", token_streaming=True, native_sessions=True)

    def __init__(self, client_factory=None):
        self.client_factory = client_factory

    def client(self, cfg: Settings, directory: str | None = None):
        from urllib.request import getproxies, proxy_bypass
        if getproxies() and not proxy_bypass(urlsplit(cfg.base_url).hostname):
            raise EngineFailure("Configure NO_PROXY for the loopback runtime before using the official SDK", "capability")
        try:
            factory = self.client_factory or importlib.import_module("openscience").Client
        except ImportError as e:
            raise EngineFailure("Install the pinned official openscience-runtime source client; see integration guide", "capability") from e
        return factory(cfg.base_url, token=cfg.token, directory=directory, timeout=cfg.request_timeout_s,
                       max_response_bytes=4 * 1024 * 1024, max_event_bytes=1024 * 1024)

    def health(self):
        try:
            cfg = settings()
            if not cfg.enabled:
                return {"ready": False, "state": "DISABLED", "detail": "OpenScience integration is disabled"}
            if not cfg.token or not cfg.policy_confirmed:
                return {"ready": False, "state": "NOT_CONFIGURED", "detail": "Configure deployment token and review isolated runtime/privacy policy"}
            cap = self.client(cfg).capabilities()
            self.check_capabilities(cap)
            return {"ready": True, "state": "READY", "detail": "Runtime protocol compatible; model/tool access is not verified", "version": cap.get("serverVersion")}
        except Exception as e:
            from backend.core.telemetry import redact
            return {"ready": False, "state": "UNAVAILABLE", "detail": redact(str(e))[:240]}

    @staticmethod
    def check_capabilities(cap):
        if cap.get("protocolVersion") != "1.0" or cap.get("idempotentPrompts") is not True or cap.get("runSnapshots") is not True:
            raise EngineFailure("OpenScience runtime protocol/capabilities are incompatible", "capability")

    def http(self, cfg, directory):
        return httpx.Client(base_url=cfg.base_url, headers={"Authorization": "Bearer " + cfg.token},
                            params={"directory": directory}, timeout=cfg.request_timeout_s, follow_redirects=False, trust_env=False)

    @staticmethod
    def public_json(http, path, **kwargs):
        body = bytearray()
        with http.stream("GET", path, **kwargs) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise EngineFailure("Runtime metadata exceeds response limit", "execution")
        return json.loads(body)

    def verify_policy(self, cfg, directory):
        with self.http(cfg, directory) as http:
            effective = self.public_json(http, "/config/").get("permission", {})
            expected = policy(cfg.allow_execution)
            if any(effective.get(k) != v for k, v in expected.items()) or any(v not in ("ask", "deny") for k, v in effective.items() if k not in expected):
                raise EngineFailure("Effective OpenScience permissions differ from the reviewed workspace policy", "capability")

    def execute(self, task, emit, cancelled):
        cfg = settings()
        if not cfg.enabled or not cfg.token or not cfg.policy_confirmed or not task.approved:
            raise EngineFailure("OpenScience requires configuration and an approved research run", "capability")
        if bool(cfg.model_provider) != bool(cfg.model_id):
            raise EngineFailure("Configure both the native model provider and model ID, or clear both to use the runtime default", "capability")
        if task.capability in ("analysis", "prototype") and not cfg.allow_execution:
            raise EngineFailure("Enable reviewed tool execution before delegating analysis/prototypes", "capability")
        if cancelled():
            raise EngineFailure("Task cancelled before dispatch", "cancelled")
        cfg = cfg.model_copy(update={"timeout_s": min(cfg.timeout_s, task.time_limit_s)})
        job_id = "ej-" + hashlib.sha256(task.operation_id.encode()).hexdigest()[:20]
        with _lock:
            lease = _locks.setdefault(str(job_path(job_id)), threading.Lock())
        if not lease.acquire(blocking=False):
            raise EngineFailure("This external operation already has an observer", "indeterminate", job_id=job_id)
        try:
            return self._execute(task, cfg, job_id, emit, cancelled)
        except EngineFailure:
            raise
        except Exception as e:
            status = getattr(e, "status", None)
            kind = "auth" if status in (401, 403) else "quota" if status == 429 else "indeterminate"
            raise EngineFailure(str(e), kind, job_id=job_id) from e
        finally:
            lease.release()

    def _execute(self, task, cfg, job_id, emit, cancelled):
        from backend.core.config import data_dir
        from backend.agent import write_json
        from backend.providers.privacy import sanitize
        root = data_dir().resolve()
        if not task.output_dir.resolve().is_relative_to(root):
            raise EngineFailure("Engine output directory must belong to this research project", "capability")
        workspace = root / "research-engines" / "workspaces" / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        write_json(workspace / "openscience.json", {"permission": policy(cfg.allow_execution)})
        client = self.client(cfg, str(workspace))
        self.check_capabilities(client.capabilities())
        self.verify_policy(cfg, str(workspace))
        record = read_job(job_id) if job_path(job_id).exists() else None
        if record and record.get("question_sha256") != hashlib.sha256(task.question.encode()).hexdigest():
            raise EngineFailure("Task input changed; create a new operation rather than reusing a receipt", "capability", job_id=job_id)
        if record and record["endpoint"] != cfg.base_url:
            raise EngineFailure("Endpoint changed; reconcile the original runtime before dispatching elsewhere", "indeterminate", job_id=job_id)
        if record and record.get("state") in TERMINAL - {"completed"} and task.attempt > record["attempt"]:
            # A new attempt follows an explicit researcher resume. Unknown admission never enters this branch.
            write_json(job_path(job_id).with_name(job_id + f".attempt-{record['attempt']}.json"), record)
            record = None
        if record is None:
            text = sanitize(task.context + "\n\n# Task\n" + task.question)[0]
            text = text.replace(cfg.token, "[REDACTED]")
            record = {"schema_version": "1.0", "id": job_id, "operation_id": task.operation_id, "attempt": task.attempt,
                      "project_id": task.project_id, "endpoint": cfg.base_url, "workspace": str(workspace),
                      "workflow_id": task.workflow_id, "step_id": task.step_id, "output_dir": str(task.output_dir),
                      "question_sha256": hashlib.sha256(task.question.encode()).hexdigest(),
                      "context_sha256": hashlib.sha256(text.encode()).hexdigest(), "message": text,
                      "session_id": "", "native_run_id": "", "request_id": job_id + f":{task.attempt}", "cursor": 0,
                      "state": "preparing", "partial_text": "", "decisions": [], "hypothesis_id": task.hypothesis_id,
                      "experiment_id": task.experiment_id, "model": {"providerID": cfg.model_provider, "modelID": cfg.model_id} if cfg.model_provider and cfg.model_id else None}
            # Paused native decisions continue to consume the single external admission slot.
            with _lock:
                for path in job_path(job_id).parent.glob("ej-*.json"):
                    if ".attempt-" in path.name or path == job_path(job_id):
                        continue
                    other = json.loads(path.read_text("utf-8"))
                    if other.get("state") not in TERMINAL:
                        raise EngineFailure("Another native run is unresolved; settle it before admitting more work", "resource", job_id=other["id"])
                save_job(record)
            session = client.create_session(title=sanitize(task.question)[0].replace(cfg.token, "[REDACTED]")[:100], workspace="project")
            record["session_id"] = session["id"]
            save_job(record)
            self._submit(client, record)
        elif not record.get("native_run_id"):
            raise EngineFailure("Admission is unresolved; use explicit admission recovery with the saved request", "indeterminate", job_id=job_id)
        if record.get("result"):
            return EngineResult.model_validate(record["result"])
        emit(EngineEvent(engine="openscience", type="status", data={"job_id": job_id, "state": "observing", "native_run_id": record["native_run_id"]}))
        self.observe(client, cfg, record, emit, cancelled)
        receipt = client.get_run(record["session_id"], record["native_run_id"])
        record["state"] = receipt["state"]
        save_job(record)
        if receipt["state"] != "completed":
            error = receipt.get("error") or {}
            from backend.providers.cli import classify_error
            message = str(error.get("message") or receipt["state"])
            kind = {"RATE_LIMITED": "quota", "AUTH_EXPIRED": "auth"}.get(classify_error(message), "execution")
            raise EngineFailure(message, kind, job_id=job_id)
        message = client.get_message(record["session_id"], receipt["resultMessageID"])
        from backend.core.telemetry import redact
        text = redact("\n".join(p.get("text", "") for p in message.get("parts", []) if p.get("type") == "text")).replace(cfg.token, "[REDACTED]")
        record["partial_text"] = text[-200000:]
        save_job(record)
        refs = self.collect(cfg, record, receipt["resultMessageID"])
        result = EngineResult(engine="openscience", text=text, artifact_refs=refs, native_session_id=record["session_id"],
                              native_run_id=record["native_run_id"], provenance={"job_id": job_id,
                              "context_sha256": record["context_sha256"], "scientific_review": "pending",
                              "hypothesis_id": record["hypothesis_id"], "experiment_id": record["experiment_id"]})
        record["result"] = result.model_dump(mode="json")
        save_job(record)
        return result

    @staticmethod
    def _submit(client, record):
        record["state"] = "admission_unconfirmed"
        save_job(record)  # persist exact input and identity BEFORE any potentially effectful request
        receipt = client.prompt(record["session_id"], record["message"], request_id=record["request_id"],
                                model=record.get("model"), effort="normal", delegation=False)
        record.update(native_run_id=receipt["runID"], state="accepted")
        save_job(record)

    @staticmethod
    def pending(client, record):
        snapshot = client.snapshot(record["session_id"])
        return [{**p, "kind": kind} for kind, name in (("permission", "permissions"), ("question", "questions")) for p in snapshot.get(name, [])]

    def observe(self, client, cfg, record, emit, cancelled):
        receipt = client.get_run(record["session_id"], record["native_run_id"])
        if receipt["state"] in TERMINAL:
            return
        pending = self.pending(client, record)
        if pending:
            record["state"] = "waiting_decision"
            save_job(record)
            raise EngineFailure("OpenScience needs your permission or answer", "decision", job_id=record["id"], pending=pending)
        inbox, stop, reconnect = queue.Queue(maxsize=256), threading.Event(), threading.Event()
        def push(value):
            while not stop.is_set():
                try:
                    inbox.put(value, timeout=0.2)
                    return
                except queue.Full:
                    pass
        def reader():
            while not stop.is_set():
                reconnect.clear()
                try:
                    with closing(client.events(record["session_id"], after_sequence=record["cursor"], reconnects=0)) as stream:
                        for event in stream:
                            if stop.is_set():
                                break
                            push(event)
                    push(None)
                except Exception as e:
                    push(e)
                while not stop.is_set() and not reconnect.wait(0.2):
                    pass
        thread = threading.Thread(target=reader, daemon=True, name="openscience-events")
        thread.start()
        deadline, disconnects = time.monotonic() + cfg.timeout_s, 0
        carry = ""
        def publish_text(value, sequence, final=False):
            nonlocal carry
            from backend.core.telemetry import redact
            value = (carry + value).replace(cfg.token, "[REDACTED]")
            carry = ""
            if not final:
                # Hold only a suffix matching the deployment credential's prefix, so
                # a credential split across SSE events cannot escape the exact-value mask.
                for size in range(min(len(value), len(cfg.token) - 1), 0, -1):
                    if value.endswith(cfg.token[:size]):
                        value, carry = value[:-size], value[-size:]
                        break
            value = redact(value)
            if value:
                record["partial_text"] = (record["partial_text"] + value)[-200000:]
                emit(EngineEvent(engine="openscience", type="text_delta", sequence=sequence, data={"text": value}))
        try:
            while True:
                if cancelled() or time.monotonic() > deadline:
                    record["state"] = "cancellation_unconfirmed"
                    save_job(record)
                    receipt = client.cancel_run(record["session_id"], record["native_run_id"])
                    record["state"] = receipt["state"] if receipt["state"] in TERMINAL else "cancellation_unconfirmed"
                    save_job(record)
                    raise EngineFailure("External cancellation requested; inspect settlement before resuming", "cancelled" if cancelled() else "timeout", job_id=record["id"])
                try:
                    event = inbox.get(timeout=0.2)
                except queue.Empty:
                    continue
                if cancelled() or time.monotonic() > deadline:
                    continue  # settle cancellation on the next iteration before processing more events
                if event is None or isinstance(event, Exception):
                    snapshot = client.snapshot(record["session_id"])
                    receipt = client.get_run(record["session_id"], record["native_run_id"])
                    if isinstance(event, Exception) and type(event).__name__ not in ("ConnectionError",):
                        record["cursor"] = snapshot["latestSequence"]
                    save_job(record)
                    if receipt["state"] in TERMINAL:
                        return
                    pending = self.pending(client, record)
                    if pending:
                        record["state"] = "waiting_decision"
                        save_job(record)
                        raise EngineFailure("OpenScience needs your permission or answer", "decision", job_id=record["id"], pending=pending)
                    # SDK socket inactivity can precede the server's 30s heartbeat. A successful
                    # snapshot/receipt permits observation to reconnect, never another prompt.
                    if isinstance(event, Exception) and type(event).__name__ == "ConnectionError":
                        if stop.wait(0.2):
                            return
                        reconnect.set()
                        continue
                    disconnects += 1
                    if event is None and disconnects <= 2:
                        reconnect.set()
                        continue
                    raise EngineFailure("Stream ended or cursor needs reconciliation; run retained for observation resume", "indeterminate", job_id=record["id"])
                if event.sequence <= record["cursor"]:
                    continue
                if event.run_id == record["native_run_id"]:
                    part = event.properties.get("part") or {}
                    if event.type == "message.part.updated" and part.get("type") == "text" and part.get("sessionID") == record["session_id"]:
                        delta = event.properties.get("delta")
                        if isinstance(delta, str):
                            publish_text(delta, event.sequence)
                    elif part.get("type") == "tool":
                        emit(EngineEvent(engine="openscience", type="tool", sequence=event.sequence,
                                         data={"name": part.get("tool"), "status": (part.get("state") or {}).get("status")}))
                    if event.type in ("permission.asked", "question.asked"):
                        pending = self.pending(client, record)
                        if pending:
                            record["state"] = "waiting_decision"
                            save_job(record)
                            raise EngineFailure("OpenScience needs your permission or answer", "decision", job_id=record["id"], pending=pending)
                record["cursor"] = event.sequence
                save_job(record)
                if event.run_id == record["native_run_id"] and event.type in ("runtime.completed", "runtime.failed", "runtime.cancelled"):
                    publish_text("", event.sequence, final=True)
                    save_job(record)
                    return
        finally:
            stop.set()
            thread.join(timeout=cfg.request_timeout_s + 0.5)

    def collect(self, cfg, record, result_message_id):
        refs, total = [], 0
        out = Path(record["output_dir"])
        from backend.core.config import data_dir
        if not out.resolve().is_relative_to(data_dir().resolve()):
            raise EngineFailure("Stored output directory is outside this project", "capability")
        out.mkdir(parents=True, exist_ok=True)
        with self.http(cfg, record["workspace"]) as http:
            for artifact in self.public_json(http, "/file/artifact-store", params={"state": "active"}):
                version = artifact.get("current") or {}
                if version.get("sessionID") != record["session_id"]:
                    continue
                aid, vid = artifact.get("id", ""), version.get("id", "")
                if not re.fullmatch(r"art_[A-Za-z0-9_-]+", aid) or not re.fullmatch(r"ver_[A-Za-z0-9_-]+", vid):
                    raise EngineFailure("Invalid native artifact identity", "execution", job_id=record["id"])
                expected = version.get("sha256", "")
                if not re.fullmatch(r"[0-9a-f]{64}", expected):
                    raise EngineFailure("Native artifact has no valid SHA-256", "execution", job_id=record["id"])
                if len(refs) >= cfg.max_artifacts:
                    raise EngineFailure("Artifact count exceeds approved limits", "execution", job_id=record["id"])
                name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(version.get("filename", "output")))[:100]
                target = out / (aid + "-" + vid + "-" + name)
                if target.is_symlink() or not target.resolve().is_relative_to(out.resolve()):
                    raise EngineFailure("Artifact target is outside the output directory", "execution")
                tmp = target.with_suffix(target.suffix + ".partial")
                if tmp.is_symlink():
                    raise EngineFailure("Artifact temporary path is a symlink", "execution")
                digest, size, tail = hashlib.sha256(), 0, b""
                credential = cfg.token.encode() if cfg.token else b""
                try:
                    with http.stream("GET", f"/file/artifact-store/{aid}/raw", params={"versionID": vid}) as stream:
                        stream.raise_for_status()
                        with tmp.open("wb") as dest:
                            for chunk in stream.iter_bytes():
                                if credential and credential in tail + chunk:
                                    raise EngineFailure("Artifact contains a deployment credential; import refused", "execution", job_id=record["id"])
                                tail = (tail + chunk)[-(len(credential) - 1):] if len(credential) > 1 else b""
                                size += len(chunk)
                                total += len(chunk)
                                if total > cfg.max_artifact_mb * 1024 * 1024:
                                    raise EngineFailure("Artifact bytes exceed approved limits", "execution", job_id=record["id"])
                                digest.update(chunk)
                                dest.write(chunk)
                    if digest.hexdigest() != expected or size != version.get("size"):
                        raise EngineFailure("Native artifact checksum/size mismatch", "execution", job_id=record["id"])
                    tmp.replace(target)
                finally:
                    tmp.unlink(missing_ok=True)
                refs.append({"path": str(target), "sha256": expected, "size": size, "native_artifact_id": aid,
                             "native_version_id": vid, "native_message_id": version.get("messageID"),
                             "scientific_review": "pending"})
        return refs


@contextmanager
def command(job_id):
    engine, cfg, record = OpenScienceEngine(), settings(), read_job(job_id)
    if not cfg.enabled or not cfg.token or not cfg.policy_confirmed:
        raise EngineFailure("Enable and configure the reviewed runtime before issuing commands", "capability", job_id=job_id)
    if record["endpoint"] != cfg.base_url:
        raise EngineFailure("Original runtime endpoint changed", "indeterminate", job_id=job_id)
    with _lock:
        lease = _locks.setdefault(str(job_path(job_id)), threading.Lock())
    if not lease.acquire(blocking=False):
        raise EngineFailure("An observer or decision already owns this operation", "indeterminate", job_id=job_id)
    try:
        record = read_job(job_id)
        engine.verify_policy(cfg, record["workspace"])
        yield engine, cfg, record
    except EngineFailure:
        raise
    except Exception as error:
        raise EngineFailure(str(error), "indeterminate", job_id=job_id) from error
    finally:
        lease.release()


def decide(job_id: str, request_id: str, *, reply: str = "reject", answers: list[list[str]] | None = None):
    with command(job_id) as (engine, cfg, record):
        return _decide(engine, cfg, record, request_id, reply, answers)


def _decide(engine, cfg, record, request_id, reply, answers):
    job_id = record["id"]
    client = engine.client(cfg, record["workspace"])
    pending = engine.pending(client, record)
    request = next((p for p in pending if p.get("id") == request_id), None)
    if not request:
        raise EngineFailure("Decision is no longer pending in this runtime", "indeterminate", job_id=job_id)
    if request["kind"] == "permission":
        if reply not in ("once", "reject"):
            raise ValueError("Only once/reject permission decisions are allowed")
        if reply == "once" and policy(cfg.allow_execution).get(request.get("permission")) == "deny":
            raise EngineFailure("This permission exceeds the configured execution policy", "capability", job_id=job_id)
        result = client.reply_permission(record["session_id"], request_id, reply)
    elif answers is not None:
        result = client.reply_question(record["session_id"], request_id, answers)
    else:
        result = client.reject_question(record["session_id"], request_id)
    record["decisions"].append({"request_id": request_id, "reply": reply, "at": time.time(), "receipt": result})
    save_job(record)
    return result


def recover_admission(job_id: str):
    with command(job_id) as (engine, cfg, record):
        if not record.get("native_run_id"):
            if not record.get("session_id"):
                raise EngineFailure("Session creation is unresolved; reconcile the original runtime manually", "indeterminate", job_id=job_id)
            engine._submit(engine.client(cfg, record["workspace"]), record)
        return {"job_id": job_id, "native_run_id": record["native_run_id"]}


def cancel_job(job_id: str):
    with command(job_id) as (engine, cfg, record):
        if not record.get("native_run_id"):
            raise EngineFailure("Admission must be reconciled before a run can be cancelled", "indeterminate", job_id=job_id)
        record["state"] = "cancellation_unconfirmed"
        save_job(record)
        receipt = engine.client(cfg, record["workspace"]).cancel_run(record["session_id"], record["native_run_id"])
        record["state"] = receipt["state"] if receipt["state"] in TERMINAL else "cancellation_unconfirmed"
        save_job(record)
        return {"job_id": job_id, "state": record["state"]}


def inspect_job(job_id: str):
    engine, cfg, record = OpenScienceEngine(), settings(), read_job(job_id)
    if record["endpoint"] != cfg.base_url:
        raise EngineFailure("Reconnect the original runtime to reconcile this job", "indeterminate", job_id=job_id)
    safe = {k: v for k, v in record.items() if k not in ("message", "partial_text")}
    try:
        client = engine.client(cfg, record["workspace"])
        pending = engine.pending(client, record) if record.get("session_id") else []
        receipt = client.get_run(record["session_id"], record["native_run_id"]) if record.get("native_run_id") else None
        # Inspection is read-only: an observer or decision owns journal mutation.
        return {"job": safe, "pending": pending, "receipt": receipt}
    except EngineFailure:
        raise
    except Exception as error:
        from backend.core.telemetry import redact
        detail = redact(str(error))[:700]
        return {"job": safe, "pending": [], "receipt": None,
                "observation_error": detail.replace(cfg.token, "[REDACTED]") if cfg.token else detail}


def require_settled(job_id: str):
    """Changing engines must not hide a live native operation."""
    with command(job_id) as (engine, cfg, record):
        if not record.get("native_run_id"):
            raise EngineFailure("Reconcile uncertain admission before changing engines", "indeterminate", job_id=job_id)
        receipt = engine.client(cfg, record["workspace"]).get_run(record["session_id"], record["native_run_id"])
        if receipt["state"] not in TERMINAL:
            raise EngineFailure("Cancel and settle the original native run before changing engines", "indeterminate", job_id=job_id)
        record["state"] = receipt["state"]
        save_job(record)
