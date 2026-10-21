"""Whitelisted UI contributions. Descriptors never execute third-party JavaScript."""
QUICK = {
    "find": ("Paper Explorer", "papers"), "library": ("Curated library", "library"),
    "topic": ("Topic Manager", "topics"), "workspace": ("Engine workspaces", "workspaces"),
    "sync": ("Workspace synchronization", "workspaces"), "artifacts": ("Artifacts and provenance", "artifacts"),
    "jobs": ("Research jobs", "jobs"), "downloads": ("Download jobs", "jobs"),
    "project": ("Project and topics", "topics"), "settings": ("Settings", "settings"),
}


def catalog() -> list:
    return [{"name": name, "plugin_id": "phdlab.research", "capability_id": "ui." + name, "title": title,
             "description": "Deterministic action · 0 LLM calls", "aliases": [], "category": "quick_action",
             "kind": "quick_action", "mode": "ui", "route_or_component_key": view, "permissions": [], "availability": "available"}
            for name, (title, view) in QUICK.items()]
