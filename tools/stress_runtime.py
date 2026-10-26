"""Bounded, reproducible application stress on temporary data. No real inference or cloud jobs.

Run with the project's Python. Reports distinguish actual HTTP/subprocess I/O from scripted model output.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
import traceback
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def distribution(values):
    values = sorted(values)
    return {"count": len(values), "p50_ms": round(statistics.median(values), 3),
            "p95_ms": round(values[min(len(values) - 1, int(len(values) * .95))], 3),
            "max_ms": round(values[-1], 3)}


def check(value, message):
    if not value:
        raise AssertionError(message)


def gateway_stress(workers, rounds):
    from backend.providers import gateway as G, cli as C
    from providers.fakes import fake
    total = workers * rounds
    with mock.patch.dict(C.CONNECTORS, {"codex": fake("codex")}):
        request = G.prepare("stress fixture only", "codex", memory=False)
    rid, latencies = request["id"], []
    record = G.get(rid)
    record["status"] = "running"
    def consumer(delay):
        time.sleep(delay)
        cursor, values = 0, []
        end = time.monotonic() + 90
        while len(values) < total and time.monotonic() < end:
            batch = G.wait_events(rid, cursor, .2)
            values.extend(e["text"] for e in batch["events"])
            cursor = batch["next"]
        check(len(values) == total, "Lost events or a subscriber failed to wake")
        return values
    def producer(index):
        for n in range(rounds):
            start = time.perf_counter()
            G._publish(record, {"type": "text_delta", "text": f"{index}:{n}"})
            latencies.append((time.perf_counter() - start) * 1000)
    with ThreadPoolExecutor(max_workers=workers + 3) as pool:
        subscribers = [pool.submit(consumer, delay) for delay in (0, .05, .15)]
        writers = [pool.submit(producer, i) for i in range(workers)]
        for future in writers:
            future.result(timeout=90)
        with G._changed:
            record["status"] = "completed"
            G._changed.notify_all()
        received = [future.result(timeout=90) for future in subscribers]
    expected = {f"{i}:{j}" for i in range(workers) for j in range(rounds)}
    check(set(received[0]) == expected, "Duplicate/missing producer identities")
    check(all(events == received[0] for events in received), "Subscribers observed different event ordering")
    check(len(record["events"]) <= G.EVENT_WINDOW, "Unbounded hot event window")
    G._persist(record)
    G.REQS.pop(rid)
    cursor, cold = 0, []
    while cursor < total:
        batch = G.events(rid, cursor)
        cold.extend(e["text"] for e in batch["events"])
        check(batch["next"] > cursor, "Cold durable replay stopped making progress")
        cursor = batch["next"]
    check(cold == received[0], "Cold replay differs from live delivery")
    return {"events": total, "subscribers": 3, "durable_replay_verified": True,
            "hot_window": len(record["events"]), "publish_latency": distribution(latencies)}


def state_stress(workers, rounds):
    from backend.agent import sessions
    session = sessions.create("Concurrent writers")
    def writer(i):
        return [sessions.add_message(session["id"], "user", f"{i}:{j}")["id"] for j in range(rounds)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        ids = [m for batch in pool.map(writer, range(workers)) for m in batch]
    messages = sessions.get(session["id"])["messages"]
    check(len(messages) == workers * rounds, "Lost concurrent session update")
    check(len(set(ids)) == len(ids), "Duplicate message identity")
    check({m["content"] for m in messages} == {f"{i}:{j}" for i in range(workers) for j in range(rounds)}, "Wrong stored content")
    return {"writers": workers, "messages": len(messages), "unique_ids": len(set(ids))}


def guard_stress(workers, rounds):
    from backend.execution import guard
    guard.reset()
    lock, state = threading.Lock(), {"active": 0, "peak": 0, "completed": 0}
    def worker(i):
        for n in range(rounds):
            holder = f"stress-{i}-{n}"
            guard.acquire("cpu", holder, timeout=60)
            try:
                with lock:
                    state["active"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                time.sleep(.001)
                with lock:
                    state["active"] -= 1
                    state["completed"] += 1
            finally:
                guard.release_all(holder)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(worker, range(workers)))
    check(state["peak"] == 1, "CPU slot oversubscribed")
    check(state["completed"] == workers * rounds, "A waiter starved")
    check(not guard.snapshot()["cpu"]["held_by"], "Resource lease leaked")
    return state


def process_stress(workers):
    from backend.providers import cli as C
    from providers.fakes import fake
    from backend.execution import guard
    original_popen, processes = C.subprocess.Popen, []
    def tracked_popen(*args, **kwargs):
        proc = original_popen(*args, **kwargs)
        processes.append(proc)
        return proc
    def worker(i):
        connector = fake("codex", "slow" if i % 3 == 0 else "ok")
        events = list(connector.stream_message("fixture", {"request_id": f"stress-{i}",
                      "timeout_s": .3 if i % 3 == 0 else 10}))
        if i % 3:
            check(any(e["type"] == "request_completed" and e.get("exit_code") == 0 for e in events), "Fixture process failed")
        else:
            check(any(e["type"] == "error" for e in events), "Timeout did not report failure")
        return events
    with mock.patch.object(C.subprocess, "Popen", side_effect=tracked_popen):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            events = list(pool.map(worker, range(workers)))
    check(not C._procs, "Managed CLI process registry leaked")
    # Windows taskkill helpers can still be returning from the watchdog after the
    # provider has exited. Observe the documented 5s kill budget before calling it a leak.
    cleanup_started, cleanup_deadline = time.monotonic(), time.monotonic() + 6
    while any(proc.poll() is None for proc in processes) and time.monotonic() < cleanup_deadline:
        time.sleep(.02)
    check(all(proc.poll() is not None for proc in processes),
          "An owned OS process survived the cleanup deadline: " + str([proc.args for proc in processes if proc.poll() is None]))
    # PID checks and tree cleanup are also exercised by the regression process-stop suite.
    check(not guard.snapshot()["cli"]["held_by"], "CLI lease leaked")
    return {"real_subprocesses": workers, "forced_timeouts": len(range(0, workers, 3)),
            "remaining_registered_processes": len(C._procs), "remaining_owned_os_processes": sum(proc.poll() is None for proc in processes),
            "cleanup_settlement_ms": round((time.monotonic() - cleanup_started) * 1000, 3),
            "events": sum(map(len, events))}


def http_stress(workers, rounds):
    import httpx
    import uvicorn
    from backend.app import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True, name="stress-http-server")
    thread.start()
    try:
        end = time.monotonic() + 15
        while not server.started and thread.is_alive() and time.monotonic() < end:
            time.sleep(.01)
        check(server.started, "HTTP server did not start")
        port = server.servers[0].sockets[0].getsockname()[1]
        def worker(i):
            times = []
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15) as client:
                for j in range(rounds):
                    start = time.perf_counter()
                    response = client.get("/api/version" if j % 2 else "/api/config")
                    check(response.status_code == 200, "HTTP load returned an error")
                    check(response.json().get("version"), "Invalid HTTP payload under load")
                    times.append((time.perf_counter() - start) * 1000)
            return times
        with ThreadPoolExecutor(max_workers=workers) as pool:
            times = [t for batch in pool.map(worker, range(workers)) for t in batch]
        from backend.core import bus
        count, clients = 100, min(workers, 8)
        connected, delivery = [threading.Event() for _ in range(clients)], []
        def sse_client(index):
            cursor, received = bus.last(), []
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15) as client:
                for connection in range(2 if index == 0 else 1):
                    with client.stream("GET", "/api/events/stream", params={"after": cursor, "timeout": 20}) as response:
                        check(response.status_code == 200, "SSE connection failed")
                        for line in response.iter_lines():
                            if not line.startswith("data:"):
                                continue
                            event = json.loads(line[5:])
                            if event.get("type") == "hello":
                                connected[index].set()
                            if event.get("type") != "stress.sample":
                                continue
                            received.append(event["sample"])
                            cursor = event["seq"]
                            delivery.append(max(0, (time.time() - event["ts"]) * 1000))
                            if len(received) == count or (index == 0 and connection == 0 and len(received) == count // 2):
                                break
            check(received == list(range(count)), "SSE loss, duplication or order mismatch after reconnect")
        with ThreadPoolExecutor(max_workers=clients) as pool:
            subscribers = [pool.submit(sse_client, i) for i in range(clients)]
            check(all(event.wait(10) for event in connected), "SSE subscribers failed to connect")
            for number in range(count):
                bus.publish("stress.sample", sample=number)
            for future in subscribers:
                future.result(timeout=30)
        return {"transport": "actual loopback HTTP", "clients": workers, "latency": distribution(times), "errors": 0,
                "sse_clients": clients, "sse_deliveries": len(delivery), "sse_reconnect_verified": True,
                "sse_delivery_latency": distribution(delivery),
                "lifespan": "off; startup/recovery is covered by regression, this phase isolates HTTP admission"}
    finally:
        server.should_exit = True
        thread.join(15)
        check(not thread.is_alive(), "HTTP server failed to shut down")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--out", default="artifacts/full-validation/stress.json")
    args = parser.parse_args()
    if not 2 <= args.workers <= 32 or not 1 <= args.rounds <= 10:
        parser.error("workers must be 2..32; rounds must be 1..10")
    report = {"schema_version": "1.0", "workers": args.workers, "rounds": args.rounds,
              "real_model_calls": 0, "cloud_jobs": 0, "phases": [], "passed": True}
    try:
        import psutil
        process = psutil.Process()
        report["rss_before_mb"] = round(process.memory_info().rss / 2 ** 20, 2)
    except ImportError:
        process = None
    with tempfile.TemporaryDirectory(prefix="phdlab-stress-") as data:
        os.environ["PHDLAB_DATA_DIR"] = data
        os.environ["JUPYTER_DATA_DIR"] = str(Path(data) / "_jupyter")
        import _env
        from backend.core import config
        config.save_config({"gateway": {"codex_app_server": False}, "memory": {"embed_engine": "hashing"}})
        for iteration in range(args.rounds):
            _env.fresh_project(f"stress-{iteration}")
            for name, run in (("gateway-streaming", lambda: gateway_stress(args.workers, 200)),
                              ("concurrent-state", lambda: state_stress(args.workers, 20)),
                              ("resource-contention", lambda: guard_stress(args.workers, 20)),
                              ("subprocess-timeout-cleanup", lambda: process_stress(args.workers)),
                              ("http-load", lambda: http_stress(args.workers, 30))):
                start = time.monotonic()
                result = {"round": iteration + 1, "name": name}
                try:
                    result.update(run(), passed=True)
                except Exception:
                    result.update(passed=False, error=traceback.format_exc())
                    report["passed"] = False
                result["elapsed_s"] = round(time.monotonic() - start, 3)
                report["phases"].append(result)
                print(json.dumps(result), flush=True)
    if process:
        report["rss_after_mb"] = round(process.memory_info().rss / 2 ** 20, 2)
    target = ROOT / args.out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), "utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
