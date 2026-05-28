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
    keywords = sorted(set(
        (p.get("concept") or {}).get("label") or (p.get("value") or "")
        for p in (it.get("properties") or [])
        if p.get("type", {}).get("code") == "keyword"
        if (p.get("concept") or {}).get("label") or (p.get("value") or "")
    ))
    node_map[pid] = {
        "id":       pid,
        "label":    it.get("label", pid),
        "category": it.get("category", ""),
        "source":   it.get("source.label") or "user-created",
        "keywords": keywords,
    }

# ── Build step → parent workflow map ─────────────────────────────────────────
# Steps are nested in composedOf; they are NOT top-level items.
# Any relation pointing TO a step should be redirected to the parent workflow.
step_to_workflow = {}

def register_steps(steps, wf_pid):
    for step in steps:
        s_pid = step.get("persistentId")
        if s_pid:
            step_to_workflow[s_pid] = wf_pid
        register_steps(step.get("composedOf") or [], wf_pid)

for it in items:
    if it.get("category") == "workflow":
        wf_pid = it.get("persistentId")
        if wf_pid:
            register_steps(it.get("composedOf") or [], wf_pid)

print(f"  Step persistentIds mapped to workflows: {len(step_to_workflow)}")

# ── Extract edges (deduplicate inverse pairs) ─────────────────────────────────
INVERSE = {
    "is-related-to":    "relates-to",
    "is-documented-by": "documents",
    "is-extended-by":   "extends",
    "is-mentioned-in":  "mentions",
}
REL_LABEL = {
    "relates-to": "Relates to",
    "documents":  "Documents",
    "extends":    "Extends",
    "mentions":   "Mentions",
}

edges = []
seen  = set()

def collect_edges(src, related_items):
    """Add canonical edges from src → tgt, redirecting step targets to their workflow."""
    for r in related_items:
        tgt  = r.get("persistentId")
        code = r.get("relation", {}).get("code", "")
        if not tgt or not code:
            continue
        if code in INVERSE:
            continue
        # Redirect step target → parent workflow
        tgt = step_to_workflow.get(tgt, tgt)
        # Skip if target not a known node (dangling reference)
        if tgt not in node_map:
            continue
        # Skip self-loops (workflow relating to itself via a step)
        if tgt == src:
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
    # Step relations: walk recursively, attribute all to the parent workflow
    def walk_steps(steps):
        for step in steps:
            collect_edges(src, step.get("relatedItems") or [])
            walk_steps(step.get("composedOf") or [])
    walk_steps(it.get("composedOf") or [])

# ── Compute node degree ───────────────────────────────────────────────────────
degree = collections.Counter()
for e in edges:
    degree[e["from"]] += 1
    degree[e["to"]]   += 1

# ── All nodes, degree 0 for isolated ones ────────────────────────────────────
nodes = []
for pid, n in node_map.items():
    n["degree"] = degree[pid]   # 0 if no edges
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
