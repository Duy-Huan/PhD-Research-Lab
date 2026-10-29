"""Fixed datasets of the cpu-ml-v1 qualification suite (6.6.4 B1). Standard library only; byte-identical on every OS.

Two Gaussian classes in `features` dimensions with class separation `separation`, a share `label_noise` of flipped
labels and `rows` rows, from random.Random(seed). Values are written with 6 decimals and LF line endings, so the
sha256 recorded in suite.json identifies the exact data a case uses.

    python generate_data.py <out_dir>        writes every dataset of suite.json and checks its sha256
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def generate(seed: int, rows: int, features: int, separation: float, label_noise: float) -> bytes:
    rng = random.Random(seed)
    lines = [",".join([f"x{i + 1}" for i in range(features)] + ["y"])]
    for _ in range(rows):
        y = rng.random() < 0.5
        centre = separation / 2 if y else -separation / 2
        xs = [rng.gauss(centre, 1.0) for _ in range(features)]
        label = (not y) if rng.random() < label_noise else y
        lines.append(",".join(f"{x:.6f}" for x in xs) + "," + ("1" if label else "0"))
    return ("\n".join(lines) + "\n").encode("ascii")


def datasets(suite: dict) -> dict:
    return {d["id"]: d for case in suite["cases"] for d in case["data"]}


def main(out: Path) -> int:
    suite = json.loads((HERE / "suite.json").read_text("utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    bad = []
    for did, spec in datasets(suite).items():
        raw = generate(**spec["generator"])
        (out / f"{did}.csv").write_bytes(raw)
        if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            bad.append(did)
    print("ok" if not bad else "sha256 mismatch: " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
