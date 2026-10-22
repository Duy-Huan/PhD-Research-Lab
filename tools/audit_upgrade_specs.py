"""Repeatable specification inventory and evidence-path/staleness checker.

This does NOT prove semantic compliance or test success. Feature dispositions are a
human-reviewed map. All source document sections, list items and table rows are retained
so catalogs, examples and engineering instructions are not silently treated as requirements.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root=ROOT):
    mapping = json.loads((root / "docs/audits/upgrade-feature-map.json").read_text("utf-8"))
    expected = set(mapping["documents"].values())
    actual = {p.name for p in (root / "upgrade").glob("*.md")}
    if expected != actual:
        raise ValueError(f"Upgrade inventory changed: unmapped={sorted(actual-expected)} missing={sorted(expected-actual)}")
    documents = []
    for key, name in mapping["documents"].items():
        path = root / "upgrade" / name
        section, fenced = "Preamble", False
        items, sections = [], []
        for line_number, line in enumerate(path.read_text("utf-8-sig").splitlines(), 1):
            if line.strip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if line.startswith("#"):
                section = line.lstrip("# ")
                sections.append({"line": line_number, "heading": section})
            elif re.match(r"^\s*(?:[-*] |\d+\. |\|)", line) and not re.match(r"^\s*\|[-:| ]+\|\s*$", line):
                items.append({"line": line_number, "section": section, "text": line.strip()})
        groups = [r["id"] for r in mapping["features"] if key in r["specs"]]
        if not groups:
            raise ValueError("Document has no reviewed feature groups: " + name)
        documents.append({"key": key, "path": "upgrade/" + name, "sha256": sha(path),
                          "feature_groups": groups, "sections": sections, "inventory_items": items})
    evidence = {}
    for feature in mapping["features"]:
        if not set(feature["specs"]) <= set(mapping["documents"]):
            raise ValueError("Unknown specification in " + feature["id"])
        for path in feature["implementation"] + feature["tests"]:
            if not (root / path).is_file():
                raise ValueError("Missing evidence path: " + path)
            evidence[path] = sha(root / path)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"at": datetime.now(timezone.utc).isoformat(), "git_parent": commit,
            "interpretation": "Source-linked manual feature audit; inventory items include requirements, catalogs, examples and engineering instructions. Path/hash checks do not prove semantic compliance or executed tests.",
            "documents": documents, "features": mapping["features"], "evidence_sha256": evidence,
            "counts": {"documents": len(documents), "sections": sum(len(d["sections"]) for d in documents),
                       "inventory_items": sum(len(d["inventory_items"]) for d in documents),
                       "feature_groups": len(mapping["features"]), "dispositions": dict(Counter(f["status"] for f in mapping["features"]))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check recorded source/spec hashes; does not run feature tests")
    args = parser.parse_args()
    output = ROOT / "artifacts/upgrade-reconciliation"
    report = inventory()
    if args.check:
        previous = json.loads((output / "inventory.json").read_text("utf-8"))
        if previous["evidence_sha256"] != report["evidence_sha256"] or previous["features"] != report["features"] or previous["documents"] != report["documents"]:
            raise SystemExit("Upgrade audit is stale; regenerate after reviewing changed requirements/source")
        print("Upgrade document inventory and evidence hashes match (not a semantic/test acceptance claim)")
        return
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    lines = ["# Upgrade feature reconciliation", "", "This matrix is a source-linked audit, not a stable-release certificate. Full document sections/list/table inventories and input hashes are in [inventory.json](inventory.json). Executed checks are in [validation.md](validation.md).", "", "| Feature | Specifications | Disposition | Implementation | Test evidence | Remaining scope |", "|---|---|---|---|---|---|"]
    for f in report["features"]:
        links = lambda paths: "<br>".join(f"[{p}](../../{p})" for p in paths)
        lines.append("| " + " | ".join([f["id"] + " · " + f["requirement"], ", ".join(f["specs"]), f["status"], links(f["implementation"]), links(f["tests"]), f["remaining"] or "—"]) + " |")
    (output / "feature-matrix.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
