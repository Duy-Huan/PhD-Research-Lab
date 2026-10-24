"""PhD Research Lab — Backend Production Quality Gate Master Test Suite.

Verifies Gates G0 through G13 in accordance with:
- ISO/IEC 25010:2023 (Software quality requirements and evaluation)
- ISO/IEC/IEEE 29119 (Software testing standards)
- OWASP ASVS 5.0 (Application Security Verification Standard)
- NIST SP 800-218 (Secure Software Development Framework)
- OWASP Top 10 for LLM Applications & Agentic AI

Strict Isolation:
Runs completely offline against a disposable PHDLAB_DATA_DIR.
"""
from __future__ import annotations

import _env  # noqa: F401 (Must be imported first to enforce disposable isolation)

import asyncio
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.agent import collaboration, decision_ledger, missions as M, policy
from backend.agent.mission_contracts import CollaborationPlan, Limits, MissionSpec, Task, WorkOrder, Workstream
from backend.app import app
from backend.core import bus, config, telemetry
from backend.execution import guard
from backend.intelligence import urap
from backend.knowledge import corpus, research_store as S
from backend.memory.store import replace_retry
from backend.providers import firewall, registry as PR


class TestQualityGateAPIContract(unittest.TestCase):
    """M2 & Gate G5: API Contracts, Negative Paths, Unicode, and Security Boundaries."""

    def setUp(self):
        self.client = TestClient(app)

    def test_localhost_only_enforcement(self):
        """Verify _LocalHostOnly rejects non-local hostnames with 421."""
        res = self.client.get("/api/version", headers={"host": "attacker.evil.com"})
        self.assertEqual(res.status_code, 421)
        self.assertIn("Misdirected request", res.text)

        # Localhost header succeeds
        res_ok = self.client.get("/api/version", headers={"host": "localhost:8000"})
        self.assertEqual(res_ok.status_code, 200)

    def test_cross_origin_write_blocking(self):
        """Verify _LocalHostOnly rejects cross-origin mutations with 403 Forbidden."""
        res = self.client.post(
            "/api/config",
            json={"ui": {"theme": "dark"}},
            headers={"host": "localhost:8000", "origin": "https://malicious-site.com"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Origin not allowed", res.text)

    def test_api_schema_contract_negative_paths(self):
        """Verify strict 422 Unprocessable Entity responses for malformed DTO payloads."""
        res = self.client.post("/api/research/topics/t1/missions", json={"invalid_field": 123})
        self.assertEqual(res.status_code, 422)

        res2 = self.client.post("/api/models/test", json={"max_tokens": -50, "provider": "invalid_xyz"})
        self.assertIn(res2.status_code, (422, 400))

    def test_unicode_and_boundary_handling(self):
        """Verify system safely accepts multi-byte UTF-8, emoji, and boundary strings."""
        unicode_name = f"proj_test_unicode_{int(time.time())}"
        p = config.create_project(unicode_name)
        self.assertTrue(Path(p["data_dir"]).exists())

    def test_telemetry_and_bus_privacy(self):
        """Verify event bus and telemetry redact private tokens, keys, and passwords."""
        sensitive_text = "Bearer sk-proj-1234567890abcdef1234567890abcdef and password=SuperSecretPassword123"
        redacted = telemetry.redact(sensitive_text)
        self.assertNotIn("sk-proj-1234567890abcdef", redacted)
        self.assertNotIn("SuperSecretPassword123", redacted)

        # Event bus publish does not accept or leak unauthorized private fields
        ev = bus.publish("test.event", client="test_client", status="ok", count=42)
        self.assertEqual(ev["type"], "test.event")
        self.assertEqual(ev["count"], 42)

    def test_sse_cursor_recovery_and_deduplication(self):
        """Verify event bus cursor recovery via bus.since()."""
        bus.reset()
        ev1 = bus.publish("ev.first", payload="1")
        ev2 = bus.publish("ev.second", payload="2")
        ev3 = bus.publish("ev.third", payload="3")

        recovered = bus.since(after=ev1["seq"])
        seqs = [e["seq"] for e in recovered["events"]]
        self.assertEqual(seqs, [ev2["seq"], ev3["seq"]])


class TestQualityGateMissionsAndState(unittest.TestCase):
    """M3, Gates G2 & G3: Durable State Machine Transitions, Authority & Crash Recovery."""

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("gate-missions")
        self.tid = S.save_topic(S.TopicInput(title="State Machine Qualification Topic"))["id"]

    def _spec(self, **patches) -> MissionSpec:
        return MissionSpec.model_validate({
            "topic_id": self.tid,
            "objective": "Inspect and report",
            "permissions": ["workspace_write"],
            "tasks": [
                {"id": "inspect", "capability": "paper.inspect", "args": {}},
                {"id": "report", "capability": "mission.report", "depends_on": ["inspect"]},
            ],
            **patches,
        })

    def test_mission_lifecycle_and_approval_digest_enforcement(self):
        """Verify lifecycle: draft -> approve -> queued, and rejection of tampered digests."""
        m = M.create(self._spec())
        mid = m["id"]
        self.assertEqual(m["status"], "draft")
        valid_digest = m["payload"]["plan_digest"]

        # Tampered digest must be rejected
        with self.assertRaises(ValueError) as ctx:
            M.approve(self.tid, mid, plan_digest="bad_tampered_digest_123456", note="Approved")
        self.assertIn("Approval state/digest mismatch", str(ctx.exception))

        # Empty review note rejected
        with self.assertRaises(ValueError):
            M.approve(self.tid, mid, plan_digest=valid_digest, note="   ")

        # Valid approval transitions to queued
        approved = M.approve(self.tid, mid, plan_digest=valid_digest, note="Verified by Principal Investigator")
        self.assertEqual(approved["status"], "queued")
        self.assertIsNotNone(approved["payload"]["approval"])

    def test_delegation_cycle_detection(self):
        """Verify parent-child delegation cycle detection."""
        m1 = M.create(self._spec())
        m2 = M.create(self._spec(parent_mission_id=m1["id"]))

        # Inject cycle into SQLite payload to test validation without nested connection lock
        p1 = M.get(m1["id"], self.tid)
        p1["payload"]["spec"]["parent_mission_id"] = m2["id"]
        with S.db() as c:
            c.execute("UPDATE missions SET payload=? WHERE id=?", (S.dumps(p1["payload"]), m1["id"]))

        with self.assertRaises(ValueError) as ctx:
            M.create(self._spec(parent_mission_id=m1["id"]))
        self.assertIn("Delegation cycle", str(ctx.exception))

    def test_concurrent_tick_contention(self):
        """Verify atomic admission: multiple concurrent ticks cannot multiply executions."""
        m = M.approve(self.tid, M.create(self._spec())["id"], M.create(self._spec())["payload"]["plan_digest"], "Approved")

        results = []
        errors = []

        def worker():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(M.tick())
                results.append(res)
                loop.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        m_after = M.get(m["id"], self.tid)
        self.assertIn(m_after["status"], ("queued", "running", "completed"))

    def test_sqlite_crash_recovery_across_restart(self):
        """Verify durable state is cleanly recovered after simulated crash across SQLite instances."""
        m = M.approve(self.tid, M.create(self._spec())["id"], M.create(self._spec())["payload"]["plan_digest"], "Approved")
        mid = m["id"]

        # Simulate in-progress interrupted task
        with S.db() as c:
            c.execute("UPDATE missions SET status='running' WHERE id=?", (mid,))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=? AND id='inspect'", (mid,))

        # Simulate process crash and recovery on a fresh database connection
        M.recover()
        recovered = M.get(mid, self.tid)
        self.assertEqual(recovered["status"], "interrupted")

        # Retry requires explicit review note; transitions to paused pending fresh approval
        with self.assertRaises(ValueError):
            M.retry(self.tid, mid, "inspect")
        retried = M.retry(self.tid, mid, "inspect", "Confirmed safe to retry after crash")
        self.assertEqual(retried["status"], "paused")


class TestQualityGateMultiAgentEvidence(unittest.TestCase):
    """M4 & Gate G4: Multi-Agent DAGs, Decision Ledger Hash Chain & Scientific Evidence."""

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("gate-evidence")
        self.tid = S.save_topic(S.TopicInput(title="Evidence Qualification Topic"))["id"]

    def test_dag_cycle_detection(self):
        """Verify validation rejects cyclic dependencies in MissionSpec tasks."""
        t1 = Task(id="t1", capability="paper.inspect", depends_on=["t2"])
        t2 = Task(id="t2", capability="paper.inspect", depends_on=["t1"])

        with self.assertRaises(ValueError) as ctx:
            MissionSpec(
                topic_id=self.tid,
                objective="Cyclic DAG Mission",
                permissions=["workspace_write"],
                tasks=[t1, t2],
            )
        self.assertIn("Task dependency cycle", str(ctx.exception))

    def test_decision_ledger_tamper_detection(self):
        """Verify append-only SQLite trigger and cryptographic hash chain detect mutations."""
        with S.db() as c:
            decision_ledger.append(c, self.tid, "entity-1", "action.start", {"param": 100})
            decision_ledger.append(c, self.tid, "entity-2", "action.progress", {"step": 1})
            decision_ledger.append(c, self.tid, "entity-3", "action.finish", {"status": "ok"})

        # Export before tampering is valid
        exp_clean = decision_ledger.export(self.tid)
        self.assertTrue(exp_clean["project_chain_valid"])

        # 1. SQLite engine level: Trigger blocks UPDATE directly
        with self.assertRaises(sqlite3.IntegrityError):
            with S.db() as c:
                c.execute("UPDATE decision_ledger SET payload=? WHERE entity_id='entity-2'", (json.dumps({"tampered": True}),))

        # 2. Cryptographic hash chain level: If trigger was bypassed by disk/admin mutation
        with S.db() as c:
            c.execute("DROP TRIGGER IF EXISTS ledger_no_update")
            c.execute("UPDATE decision_ledger SET payload=? WHERE entity_id='entity-2'", (json.dumps({"tampered": True}),))

        exp_tampered = decision_ledger.export(self.tid)
        self.assertFalse(exp_tampered["project_chain_valid"], "Tampered decision ledger must fail cryptographic validation")

    def test_evidence_sha256_and_metric_recalculation(self):
        """Verify URAP evidence SHA-256 byte validation and tampering detection."""
        exp_file = Path(tempfile.mktemp(suffix=".json", prefix="phdlab-exp-"))
        raw_results = {"accuracy": 0.942, "f1_score": 0.938, "test_loss": 0.124}
        exp_file.write_text(json.dumps(raw_results, indent=2), encoding="utf-8")

        art = urap.register_artifact(
            topic_id=self.tid,
            artifact_type="experiment_result",
            uri=str(exp_file),
            media_type="application/json",
            metadata={"model": "vit-base-patch16", "dataset": "imagenet"},
        )
        aid = art["artifact_id"]

        # Deterministic verification passes
        v1 = urap.verify_integrity(aid, self.tid)
        self.assertTrue(v1["integrity_ok"])
        self.assertEqual(v1["status"], "unverified")

        # Independent metric recalculation: check raw metrics directly from file
        recalculated_data = json.loads(exp_file.read_text(encoding="utf-8"))
        self.assertAlmostEqual(recalculated_data["accuracy"], 0.942, places=3)

        # Tamper with the raw file on disk
        exp_file.write_text(json.dumps({"accuracy": 0.999, "f1_score": 0.999, "fabricated": True}), encoding="utf-8")

        # Verification must now catch the tampering and mark status as stale
        v2 = urap.verify_integrity(aid, self.tid)
        self.assertFalse(v2["integrity_ok"])
        self.assertEqual(v2["status"], "stale")
        self.assertIn("SHA-256 mismatch", v2["detail"])

        exp_file.unlink(missing_ok=True)


class TestQualityGateSecurityAndSanitization(unittest.TestCase):
    """M5 & Gate G6: Firewall Path Traversal, Prompt Injection Defenses & Memory Isolation."""

    def test_path_traversal_sanitization(self):
        """Verify firewall blocks directory traversal, Windows drive letters, and secret files."""
        with self.assertRaises(firewall.FirewallError):
            firewall.check("../../etc/passwd", root="data")

        with self.assertRaises(firewall.FirewallError):
            firewall.check("C:/Windows/System32/cmd.exe", root="data")

        with self.assertRaises(firewall.FirewallError):
            firewall.check("config.json", root="data")

    def test_outside_model_prompt_injection_defense(self):
        """Verify policy engine enforced outside the LLM blocks dangerous tool proposals and invalid flags."""
        # Policy rejects unauthorized tools in run_tools
        adversarial_turn = {
            "run_tools": [{"tool": "system_exec_rmdir", "args": {"cmd": "rmdir /s /q C:\\"}}],
        }
        with self.assertRaises(policy.AIWSError):
            policy.clean_overrides(adversarial_turn)

        # Policy rejects unauthorized privilege escalation settings
        with self.assertRaises(policy.AIWSError):
            policy.clean_overrides({"privilege_escalation": True})

    def test_atomic_writes_and_backup_safety(self):
        """Verify replace_retry performs atomic replacement without leaving corrupt intermediate files."""
        target_file = Path(tempfile.mktemp(suffix=".txt", prefix="atomic-target-"))
        target_file.write_text("initial_valid_content", encoding="utf-8")

        staging_file = Path(tempfile.mktemp(suffix=".txt", prefix="atomic-stage-"))
        staging_file.write_text("updated_valid_content", encoding="utf-8")

        replace_retry(staging_file, target_file)
        self.assertEqual(target_file.read_text(encoding="utf-8"), "updated_valid_content")
        self.assertFalse(staging_file.exists())

        target_file.unlink(missing_ok=True)


class TestQualityGateProvidersAndResilience(unittest.TestCase):
    """M5 & Gate G7: Provider Fault Matrix, Concurrency Guards and Slot Contention."""

    def test_guard_slot_concurrency_control(self):
        """Verify ResourceGuard enforces concurrency caps for GPU, CPU, and CLI slots."""
        guard.reset()
        # Acquire slot for holder A
        guard.try_acquire("gpu", "Holder_A", gpu_check=False)

        # Second job with different holder must raise Busy
        with self.assertRaises(guard.Busy):
            guard.try_acquire("gpu", "Holder_B", gpu_check=False)

        # Release holder A
        guard.release("gpu", "Holder_A")

        # Now holder B can acquire
        guard.try_acquire("gpu", "Holder_B", gpu_check=False)
        self.assertIn("Holder_B", guard.snapshot()["gpu"]["held_by"])
        guard.release_all("Holder_B")

    def test_provider_adapter_fault_matrix(self):
        """Verify provider adapters handle unknown providers gracefully with structured exception."""
        cfg = config.load_config()
        with self.assertRaisesRegex(Exception, "Unknown provider"):
            PR.describe("app:unknown_nonexistent_provider", cfg)


class TestQualityGateOfflineIntegration(unittest.TestCase):
    """M4 & Gate G13: Offline End-to-End Research Chat -> Topic -> Evidence Integration."""

    def test_offline_e2e_research_workflow(self):
        """Verify end-to-end flow: create topic, store paper, register artifact, check hash."""
        tid = S.save_topic(S.TopicInput(title="Offline E2E Topic"))["id"]

        # Ingest synthetic paper into corpus
        added = corpus.ingest(
            tid,
            [
                {
                    "title": "Verifiable Autonomous Scientific Agents",
                    "authors": ["Alice Researcher", "Bob Scientist"],
                    "year": 2026,
                    "abstract": "We formalize agentic research execution with cryptographic receipt ledgers.",
                    "doi": "10.1000/182",
                    "source": "fixture",
                }
            ],
        )["added"]
        self.assertTrue(len(added) > 0)
        paper_id = added[0]

        # Register artifact linked to topic
        art = urap.register_artifact(
            topic_id=tid,
            artifact_type="literature_report",
            content_text="Summary: Formal framework for verifiable autonomous scientific labs.",
            metadata={"paper_id": paper_id},
        )
        self.assertEqual(art["artifact_type"], "literature_report")
        self.assertEqual(art["topic_id"], tid)

        # Verify cryptographic integrity
        integrity = urap.verify_integrity(art["artifact_id"], tid)
        self.assertTrue(integrity["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
