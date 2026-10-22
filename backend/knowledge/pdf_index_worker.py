"""Bound the existing local PDF parser in a disposable process (no model calls)."""
import json
import sys
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.knowledge.library import pdf_pages
    pages, total = pdf_pages(Path(sys.argv[1]), max_pages=120)
    remaining, bounded = 2_000_000, []
    for text in pages:
        piece = text[:min(100000, remaining)]
        bounded.append(piece)
        remaining -= len(piece)
        if remaining <= 0:
            break
    sys.stdout.buffer.write(json.dumps({"pages": bounded, "total_pages": total}).encode("utf-8"))
