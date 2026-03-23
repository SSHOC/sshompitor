#!/usr/bin/env python3
"""
build_graph_data.py

Extracts the item-relation network from the latest snapshot and writes
graph.json (nodes + edges) for network_graph.html.

Run from the repo root:
    python scripts/build_graph_data.py
"""

import json
import pathlib
import collections

DATA = pathlib.Path("data")
OUT  = pathlib.Path("graph.json")

# ── Load latest snapshot ─────────────────────────────────────────────────────
snap_files = sorted(DATA.glob("full_items_*.json"), key=lambda p: p.stat().st_mtime)
if not snap_files:
    raise SystemExit("No full_items_*.json found in data/")

with open(snap_files[-1], encoding="utf-8") as fh:
    items = json.load(fh)

print(f"Loaded {len(items)} items from {snap_files[-1].name}")

# ── Build node lookup ─────────────────────────────────────────────────────────
node_map = {}
for it in items:
    pid = it.get("persistentId")
    if not pid:
        continue
    node_map[pid] = {
        "id":       pid,
        "label":    it.get("label", pid),
        "category": it.get("category", ""),
        "source":   it.get("source.label") or "user-created",
    }

# ── Extract edges (deduplicate inverse pairs) ─────────────────────────────────
# For each bidirectional pair we keep only one canonical direction.
INVERSE = {
    "is-related-to":    "relates-to",
    "is-documented-by": "documents",
    "is-extended-by":   "extends",
    "is-mentioned-in":  "mentions",
}
# Human-readable label for canonical relation codes
REL_LABEL = {
    "relates-to": "Relates to",
    "documents":  "Documents",
    "extends":    "Extends",
    "mentions":   "Mentions",
}

edges = []
seen  = set()

def collect_edges(src, related_items):
    """Add canonical edges from src to each item in related_items."""
    for r in related_items:
        tgt  = r.get("persistentId")
        code = r.get("relation", {}).get("code", "")
        if not tgt or not code:
            continue
        if code in INVERSE:
            continue
        key = (src, tgt, code)
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "from":  src,
            "to":    tgt,
            "label": REL_LABEL.get(code, code),
            "code":  code,
        })

for it in items:
    src = it.get("persistentId")
    if not src:
        continue
    # Item-level relations
    collect_edges(src, it.get("relatedItems", []))
    # Step-level relations: attribute to parent workflow
    for step in (it.get("composedOf") or []):
        collect_edges(src, step.get("relatedItems") or [])
        # Sub-steps (nested composedOf)
        for substep in (step.get("composedOf") or []):
            collect_edges(src, substep.get("relatedItems") or [])

# ── Compute node degree ───────────────────────────────────────────────────────
degree = collections.Counter()
for e in edges:
    degree[e["from"]] += 1
    degree[e["to"]]   += 1

# ── Filter to nodes that appear in at least one edge ────────────────────────
active_ids = set(degree.keys())
nodes = []
for pid, n in node_map.items():
    if pid in active_ids:
        n["degree"] = degree[pid]
        nodes.append(n)

# ── Write output ──────────────────────────────────────────────────────────────
out_data = {"nodes": nodes, "edges": edges}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out_data, fh, ensure_ascii=False, separators=(",", ":"))

print(f"Wrote {OUT}")
print(f"  Nodes : {len(nodes)}")
print(f"  Edges : {len(edges)}")
cats = collections.Counter(n["category"] for n in nodes)
rels = collections.Counter(e["code"] for e in edges)
print(f"  Categories : {dict(cats)}")
print(f"  Relations  : {dict(rels)}")
