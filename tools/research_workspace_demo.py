"""Isolated UI acceptance server with labelled fixtures, no network discovery and no model inference."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["PHDLAB_DATA_DIR"] = tempfile.mkdtemp(prefix="phdlab-workspace-demo-")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from backend.core import config
from backend.knowledge import corpus, research_store as S
from backend.research_engines import workspaces
from backend.app import app
import backend.app as application
from backend.agent import orchestrator, AIWSError
from pdfgen import make_pdf

application._warm = lambda: None
def refuse_inference(*args, **kwargs):
    raise AIWSError("Visual fixture only: agent execution is disabled")
orchestrator.start = refuse_inference
config.save_config({"memory": {"auto_summarize": False, "embed_engine": "hashing"}, "ranking": {"auto": False},
                    "clearml": {"auto_record": False}, "lifecycle": {"unload_on_exit": False}})
topic = S.save_topic(S.TopicInput(title="MRI denoising · TEST FIXTURE", keywords=["denoising"], objectives="Compare methods with page-grounded evidence"))
S.save_topic(S.TopicInput(title="Edge SoC · TEST FIXTURE"))
records = [{"title": f"TEST FIXTURE {i+1}: MRI denoising method", "authors": ["Fixture Author"], "year": 2024,
            "source": "fixture", "url": f"https://example.org/paper/{i}", "abstract": "Synthetic UI fixture. No scientific result is asserted."} for i in range(6)]
ids = corpus.ingest(topic["id"], records)["added"]
paper = corpus.paper(topic["id"], ids[0])
vid = paper["versions"][0]["id"]
corpus.store_document(topic["id"], ids[0], vid, make_pdf([[(12, "TEST FIXTURE: denoising page evidence. No scientific claim.")]]), {"origin": "test_fixture"})
corpus.index_document(topic["id"], ids[0], vid)
w = workspaces.link(topic["id"], workspaces.WorkspaceInput(engine="openscience"))
path = Path(w["path"]) / "fixture-notes.md"
path.write_text("TEST FIXTURE: saved artifact observed after offline work. Not a verified result.")
os.utime(path, (time.time()-5, time.time()-5))
workspaces.sync(w["id"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8877)
