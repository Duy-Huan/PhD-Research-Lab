"""v4.1 model lifecycle: load → task → unload / keep loaded / unload when idle, for local models, CLI sessions, the MCP
sandbox container and the cloud connection pool. LM Studio / Ollama / Docker are faked; the bookkeeping is real."""
import _env  # noqa: F401  (must be first)
import asyncio
import threading
import time
import unittest
from unittest import mock

from backend.core import config
from backend.providers import lifecycle as LC

LA = "backend.providers.local."


def st_ollama(loaded=()):
    return {"online": True, "models": [], "loaded": [{"id": m, "size": 5 * 2 ** 30, "size_vram": 4 * 2 ** 30} for m in loaded]}


def st_lm(loaded=()):
    return {"online": True, "models": [{"id": m, "quantization": "Q4_K_M"} for m in loaded], "loaded": list(loaded)}


class Fakes:
    """Patch LM Studio / Ollama with recording async fakes."""

    def __init__(self, ollama=(), lm=()):
        self.ollama, self.lm = list(ollama), list(lm)
        self.calls = []

    def __enter__(self):
        async def ost(_):
            return st_ollama(self.ollama)

        async def lst(_):
            return st_lm(self.lm)

        async def oun(_, m):
            self.calls.append(("ollama_unload", m))
            if m in self.ollama:
                self.ollama.remove(m)
            return {"ok": True}

        async def oload(_, m, keep_alive="30m"):
            self.calls.append(("ollama_load", m, keep_alive))
            return {"ok": True}

        async def lload(_, m, context_length=None):
            self.calls.append(("lm_load", m))
            self.lm.append(m)
            return {"ok": True, "method": "rest"}

        async def lun(_, m=""):
            self.calls.append(("lm_unload", m))
            if m in self.lm:
                self.lm.remove(m)
            return {"ok": True}
        self.p = [mock.patch(LA + "ollama_status", ost), mock.patch(LA + "lmstudio_status", lst),
                  mock.patch(LA + "ollama_unload", oun), mock.patch(LA + "ollama_load", oload),
                  mock.patch(LA + "lmstudio_load", lload), mock.patch(LA + "lmstudio_unload", lun),
                  mock.patch("backend.execution.resources.gpus", return_value=[{"name": "RTX 3060", "vram_used_mb": 9000,
                                                                     "vram_total_mb": 12288, "util_pct": 3, "temp_c": 50}])]
        for x in self.p:
            x.start()
        return self

    def __exit__(self, *a):
        for x in self.p:
            x.stop()


def run(coro):
    return asyncio.run(coro)


class Base(unittest.TestCase):
    def setUp(self):
        LC.reset()
        config.save_config({"lifecycle": {"enabled": True, "local_background": "unload_after_task", "local_interactive": "idle_unload",
                                          "cli": "idle_unload", "mcp": "idle_unload", "cloud": "idle_unload",
                                          "unload_grace_s": 15, "local_idle_min": 10, "respect_manual_loads": True,
                                          "single_model_vram": True}})

    def tearDown(self):
        LC.reset()


class Policies(Base):

    def test_policy_and_deadlines(self):
        cfg = config.load_config()
        self.assertEqual(LC.policy_for("local", "background", cfg), "unload_after_task")
        self.assertEqual(LC.policy_for("local", "interactive", cfg), "idle_unload")
        self.assertEqual(LC.policy_for("cli", cfg=cfg), "idle_unload")
        self.assertEqual(LC._deadline("local", "unload_after_task", cfg, 100.0), 115.0)
        self.assertEqual(LC._deadline("local", "idle_unload", cfg, 100.0), 700.0)
        self.assertIsNone(LC._deadline("local", "keep_loaded", cfg, 100.0))

    def test_invalid_policy_values_fall_back_to_defaults(self):
        config.save_config({"lifecycle": {"cli": "forever"}})
        self.assertEqual(config.load_config()["lifecycle"]["cli"], "idle_unload")

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            run(LC.acquire("gpu", "x", "y"))

    def test_disabled_is_a_no_op(self):
        config.save_config({"lifecycle": {"enabled": False}})

        async def go():
            async with LC.lease("local", "ollama", "m") as r:
                self.assertIsNone(r)
            await LC.release(None)
        run(go())
        self.assertEqual(LC._res, {})

    def test_public_record(self):
        r = LC.Resource("k", "local", "ollama", "m", release_at=time.time() + 30)
        p = r.public()
        self.assertEqual(p["kind"], "local")
        self.assertTrue(25 <= p["release_in_s"] <= 30)
        self.assertIsNone(LC.Resource("k", "cli", "c", "s").public()["release_in_s"])


class LocalModels(Base):
    def test_background_task_unloads_after_grace(self):
        with Fakes() as f:
            async def go():
                async with LC.lease("local", "ollama", "qwen2.5:7b", "background") as r:
                    self.assertEqual(r.owner, "lifecycle")
                    self.assertEqual(r.leases, 1)
                    self.assertEqual(LC.local_busy(), ["local:ollama:qwen2.5:7b"])
                res = LC._res["local:ollama:qwen2.5:7b"]
                self.assertEqual(res.policy, "unload_after_task")
                self.assertAlmostEqual(res.release_at - time.time(), 15, delta=2)
                self.assertNotIn(("ollama_load", "qwen2.5:7b", "-1"), f.calls)  # no pin for unload_after_task
                self.assertEqual(await LC.release_due(), [])  # not yet due
                out = await LC.release_due(time.time() + 16)
                self.assertTrue(out[0]["ok"])
            run(go())
        self.assertIn(("ollama_unload", "qwen2.5:7b"), f.calls)
        self.assertEqual(LC._res, {})
        self.assertEqual(LC.HISTORY[0]["action"], "released")

    def test_interactive_idle_and_pin(self):
        with Fakes() as f:
            async def go():
                async with LC.lease("local", "ollama", "llama3", "interactive"):
                    pass
            run(go())
        r = LC._res["local:ollama:llama3"]
        self.assertEqual(r.policy, "idle_unload")
        self.assertAlmostEqual(r.release_at - time.time(), 600, delta=3)
        self.assertIn(("ollama_load", "llama3", "-1"), f.calls)  # Ollama's own 5 min keep_alive must not decide

    def test_keep_loaded_never_released(self):
        config.save_config({"lifecycle": {"local_background": "keep_loaded"}})
        with Fakes():
            run(LC.release(run(LC.acquire("local", "ollama", "m", "background"))))
        self.assertIsNone(LC._res["local:ollama:m"].release_at)
        self.assertIsNone(LC.next_deadline())

    def test_manual_load_is_respected(self):
        with Fakes(ollama=["mine:7b"]) as f:
            async def go():
                async with LC.lease("local", "ollama", "mine:7b", "background") as r:
                    self.assertEqual(r.owner, "external")
            run(go())
            self.assertIsNone(LC._res["local:ollama:mine:7b"].release_at)
            self.assertEqual(run(LC.release_due(time.time() + 10 ** 6)), [])
        self.assertNotIn(("ollama_unload", "mine:7b"), f.calls)

    def test_manual_load_not_respected_when_switched_off(self):
        config.save_config({"lifecycle": {"respect_manual_loads": False}})
        with Fakes(ollama=["mine"]):
            r = run(LC.acquire("local", "ollama", "mine", "background"))
            self.assertEqual(r.owner, "lifecycle")
            run(LC.release(r, "background"))
        self.assertIsNotNone(LC._res["local:ollama:mine"].release_at)

    def test_single_model_in_vram(self):
        config.save_config({"lifecycle": {"local_background": "keep_loaded"}})
        with Fakes() as f:
            async def go():
                await LC.release(await LC.acquire("local", "ollama", "a", "background"), "background")
                await LC.release(await LC.acquire("local", "ollama", "b", "background"), "background")
            run(go())
        self.assertIn(("ollama_unload", "a"), f.calls)
        self.assertNotIn("local:ollama:a", LC._res)

    def test_lmstudio_explicit_load_and_unload(self):
        with Fakes() as f:
            async def go():
                async with LC.lease("local", "local", "qwen-coder", "background"):
                    pass
                await LC.release_due(time.time() + 20)
            run(go())
        self.assertIn(("lm_load", "qwen-coder"), f.calls)
        self.assertIn(("lm_unload", "qwen-coder"), f.calls)

    def test_lmstudio_load_failure_falls_back_to_jit(self):
        async def boom(*a, **k):
            raise RuntimeError("no REST")
        with Fakes():
            with mock.patch(LA + "lmstudio_load", boom):
                r = run(LC.acquire("local", "local", "x"))
        self.assertIn("just-in-time", r.note)

    def test_prepare_failure_never_breaks_the_task(self):
        async def boom(*a, **k):
            raise RuntimeError("down")
        with mock.patch.object(LC, "resident_local", boom):
            r = run(LC.acquire("local", "ollama", "m"))
        self.assertIn("prepare failed", r.note)
        self.assertEqual(r.state, "in_use")

    def test_pin_failure_is_noted(self):
        async def boom(*a, **k):
            raise RuntimeError("pin")
        with Fakes():
            with mock.patch(LA + "ollama_load", boom):
                run(LC.release(run(LC.acquire("local", "ollama", "m", "interactive")), "interactive"))
        self.assertIn("could not pin", LC._res["local:ollama:m"].note)

    def test_concurrent_leases_share_one_load(self):
        with Fakes() as f:
            async def go():
                a = await LC.acquire("local", "local", "m")
                b = await LC.acquire("local", "local", "m")
                self.assertIs(a, b)
                self.assertEqual(a.leases, 2)
                await LC.release(a)
                self.assertEqual(a.state, "in_use")
                self.assertIsNone(a.release_at)
                await LC.release(b)
                self.assertEqual(a.state, "idle")
            run(go())
        self.assertEqual([c for c in f.calls if c[0] == "lm_load"], [("lm_load", "m")])

    def test_second_lease_waits_for_the_load(self):
        r = LC.Resource("local:ollama:w", "local", "ollama", "w")
        LC._res[r.key] = r
        threading.Timer(0.2, r.ready.set).start()
        t0 = time.time()
        got = run(LC.acquire("local", "ollama", "w"))
        self.assertIs(got, r)
        self.assertGreaterEqual(time.time() - t0, 0.15)

    def test_release_now_refuses_a_busy_resource_and_reports_errors(self):
        r = LC.Resource("local:ollama:z", "local", "ollama", "z", leases=1)
        LC._res[r.key] = r
        self.assertFalse(run(LC._release_now(r, "t"))["ok"])

        async def boom(*a):
            raise RuntimeError("ollama down")
        r.leases = 0
        with mock.patch(LA + "ollama_unload", boom):
            out = run(LC._release_now(r, "t"))
        self.assertFalse(out["ok"])
        self.assertIn("ollama down", out["detail"])

    def test_resident_probe_cache_and_errors(self):
        async def boom(_):
            raise RuntimeError("x")
        with mock.patch(LA + "ollama_status", boom), mock.patch(LA + "lmstudio_status", boom):
            out = run(LC.resident_local(max_age=0))
        self.assertEqual(out["ollama"], {})
        self.assertIs(run(LC.resident_local()), out)  # cached
        self.assertEqual(LC._norm("Qwen:latest"), "qwen")
        self.assertIsNone(LC._mb(None))


class Manual(Base):
    def test_unload_resident_busy_force_and_errors(self):
        with Fakes(ollama=["a", "b"], lm=["c"]) as f:
            busy = run(LC.acquire("local", "ollama", "a"))
            out = run(LC.unload("ollama"))
            self.assertEqual(out["skipped_in_use"], ["a"])
            self.assertEqual(out["unloaded"], ["b"])
            out = run(LC.unload("ollama", "a", force=True))
            self.assertEqual(out["unloaded"], ["a"])
            self.assertNotIn(busy.key, LC._res)
            out = run(LC.unload("local", "not-loaded"))  # an explicit model is tried even when not listed
            self.assertEqual(out["unloaded"], ["not-loaded"])
            all_ = run(LC.unload_all_local())
            self.assertEqual(all_["unloaded"], ["lmstudio:c"])

            async def boom(*a):
                raise RuntimeError("busy")
            with mock.patch(LA + "lmstudio_unload", boom):
                out = run(LC.unload("local", "q"))
            self.assertTrue(out["errors"])
        self.assertIn(("lm_unload", "c"), f.calls)

    def test_free_vram_for_gpu(self):
        busy = LC.Resource("local:ollama:a", "local", "ollama", "a", leases=1)
        LC._res[busy.key] = busy
        self.assertFalse(LC.free_vram_for_gpu()["ok"])
        busy.leases = 0
        with mock.patch("backend.execution.resources.unload_local_models", return_value={"unloaded": ["ollama:a"], "errors": []}) as u:
            out = LC.free_vram_for_gpu()
        self.assertTrue(out["ok"])
        u.assert_called_once()
        self.assertEqual(LC._res, {})


class CliMcpCloud(Base):
    def test_cli_sessions_follow_the_policy(self):
        LC.cli_remember("gs-00000001", "codex", "th-1")
        self.assertEqual(LC.cli_resume("gs-00000001", "codex"), "th-1")
        LC.cli_remember("gs-00000001", "codex", "")  # nothing to remember
        config.save_config({"lifecycle": {"cli": "unload_after_task"}})
        self.assertEqual(LC.cli_resume("gs-00000001", "codex"), "")
        LC.cli_remember("gs-00000002", "codex", "th-2")
        self.assertNotIn(("gs-00000002", "codex"), LC.CLI_SESSIONS)
        r = LC.Resource("cli:codex:gs-00000001", "cli", "codex", "gs-00000001")
        LC._res[r.key] = r
        self.assertIn("forgotten", run(LC._release_now(r, "t"))["detail"])
        self.assertNotIn(("gs-00000001", "codex"), LC.CLI_SESSIONS)

    def test_mcp_container(self):
        with mock.patch("backend.execution.sandbox.container_state", return_value={"running": True}):
            r = run(LC.acquire("mcp", "docker", "phdlab-x"))
        self.assertEqual(r.owner, "external")
        with mock.patch("backend.execution.sandbox.container_state", side_effect=RuntimeError("no docker")):
            self.assertFalse(LC._container_running())
        from backend.execution import sandbox
        job = mock.Mock(status="running")
        with mock.patch.dict(sandbox.JOBS, {"j": job}):
            self.assertIn("still running", LC._stop_container())
        with mock.patch("backend.execution.sandbox.container_state", return_value={"running": False}):
            self.assertEqual(LC._stop_container(), "already stopped")
        with mock.patch("backend.execution.sandbox.container_state", return_value={"running": True}), \
                mock.patch("backend.execution.sandbox.container_action") as act:
            self.assertEqual(LC._stop_container(), "container stopped")
            act.assert_called_once_with("stop")
            r2 = LC.Resource("mcp:docker:y", "mcp", "docker", "y")
            LC._res[r2.key] = r2
            self.assertEqual(run(LC._release_now(r2, "t"))["detail"], "container stopped")

    def test_sandbox_lease_modes(self):
        with mock.patch("backend.execution.sandbox.effective_mode", return_value="local"):
            with LC.sandbox_lease() as r:
                self.assertIsNone(r)
        with mock.patch("backend.execution.sandbox.effective_mode", side_effect=RuntimeError):
            with LC.sandbox_lease() as r:
                self.assertIsNone(r)
        with mock.patch("backend.execution.sandbox.effective_mode", return_value="docker"), \
                mock.patch("backend.execution.sandbox.container_name", return_value="phdlab-t"), \
                mock.patch("backend.execution.sandbox.container_state", return_value={"running": False}):
            with LC.sandbox_lease() as r:
                self.assertEqual(r.key, "mcp:docker:phdlab-t")
        self.assertEqual(LC._res["mcp:docker:phdlab-t"].leases, 0)

    def test_lease_sync_inside_a_running_loop_and_errors(self):
        async def inside():
            with LC.lease_sync("cli", "codex", "gs-00000009") as r:
                return r.leases
        self.assertEqual(run(inside()), 1)

        async def bad():
            raise KeyError("x")

        async def outer():
            return LC._run(bad())
        with self.assertRaises(KeyError):
            run(outer())

    def test_http_client_pooling(self):
        async def go():
            async with LC.http_client(5) as a:   # not the app loop → fresh client
                pass
            self.assertTrue(a.is_closed)
            LC._main["loop"] = asyncio.get_running_loop()
            async with LC.http_client(5) as b:
                pass
            async with LC.http_client(5) as c:
                pass
            self.assertIs(b, c)
            self.assertFalse(b.is_closed)
            self.assertIn("cloud:http:pool", LC._res)
            st = await LC.status()
            self.assertTrue(st["cloud"]["pool_open"])
            await LC.release_due(time.time() + 10 ** 6)
            self.assertFalse(b.is_closed)  # Cloud transport stays warm; only local weights are unloaded.
            config.save_config({"lifecycle": {"cloud": "unload_after_task"}})
            async with LC.http_client(5) as d:
                pass
            self.assertIs(d, b)  # Legacy cloud-unload setting cannot force a reconnect per turn.
            self.assertEqual(await LC._close_pool(), "connection pool closed")
            self.assertTrue(b.is_closed)
        with Fakes():
            run(go())

    def test_close_pool_of_another_loop(self):
        loop = asyncio.new_event_loop()
        th = threading.Thread(target=loop.run_forever, daemon=True)
        th.start()
        import httpx
        c = httpx.AsyncClient()
        LC._pool.update(client=c, loop=loop)
        self.assertEqual(run(LC._close_pool()), "connection pool closed")
        time.sleep(0.2)
        loop.call_soon_threadsafe(loop.stop)
        th.join(2)
        loop.close()
        LC._pool.update(client=httpx.AsyncClient(), loop=loop)  # closed loop: just dropped
        self.assertEqual(run(LC._close_pool()), "connection pool closed")


class StatusAndReaper(Base):
    def test_status_shows_residency_and_owners(self):
        with Fakes(ollama=["mine"], lm=["lm-a"]):
            run(LC.acquire("local", "local", "lm-a"))
            st = run(LC.status())
        models = {m["model"]: m for m in st["local"]["models"]}
        self.assertEqual(models["mine"]["owner"], "external")
        self.assertFalse(models["mine"]["managed"])
        self.assertEqual(models["lm-a"]["leases"], 1)
        self.assertEqual(models["mine"]["vram_mb"], 4096)
        self.assertEqual(st["gpu"]["name"], "RTX 3060")
        self.assertEqual(st["busy_local"], ["local:local:lm-a"])
        self.assertIn("unload_after_task", st["policies"])

    def test_reaper_applies_deadlines_then_stops(self):
        r = LC.Resource("cli:codex:gs-0000000a", "cli", "codex", "gs-0000000a", release_at=time.time() - 1)
        LC._res[r.key] = r

        async def go():
            stop = asyncio.Event()
            t = asyncio.create_task(LC.reaper(stop))
            await asyncio.sleep(0.4)
            self.assertNotIn(r.key, LC._res)
            LC._res["cli:codex:later"] = LC.Resource("cli:codex:later", "cli", "codex", "later", release_at=time.time() + 60)
            await asyncio.sleep(0.05)
            stop.set()
            await asyncio.wait_for(t, 3)
        run(go())


if __name__ == "__main__":
    unittest.main()
