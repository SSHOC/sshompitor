#!/usr/bin/env python3
"""
build_graph_data.py

Extracts the item-relation network from the latest snapshot and writes
  graph.json                                   nodes + edges + meta, for network_graph.html
  data/processed/broken_relations_<ts>.json    relations whose target is not in the snapshot,
                                               shown in the metadata dashboard

Run from the repo root:
    python scripts/build_graph_data.py
"""

import json
import pathlib
import collections
from datetime import datetime, timezone

DATA = pathlib.Path("data")
OUT  = pathlib.Path("graph.json")
PROCESSED = DATA / "processed"

# ── Load latest snapshot ─────────────────────────────────────────────────────
snap_files = sorted(DATA.glob("full_items_*.json"), key=lambda p: p.stat().st_mtime)
if not snap_files:
    raise SystemExit("No full_items_*.json found in data/")

snap_path = snap_files[-1]
ts_str = snap_path.stem.split("_")[-1]
with open(snap_path, encoding="utf-8") as fh:
    items = json.load(fh)

print(f"Loaded {len(items)} items from {snap_path.name}")

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
        "label":    it.get("label") or pid,
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

# ── Extract edges ─────────────────────────────────────────────────────────────
# The Marketplace stores most relations on both items ("A mentions B" and
# "B is-mentioned-in A"), but not always. Inverse codes are therefore flipped
# into their forward form rather than skipped, and duplicates removed.
INVERSE = {
    "is-related-to":    "relates-to",
    "is-documented-by": "documents",
    "is-extended-by":   "extends",
    "is-mentioned-in":  "mentions",
}
# Undirected: "A relates-to B" and "B relates-to A" are the same edge.
SYMMETRIC = {"relates-to"}
REL_LABEL = {
    "relates-to": "Relates to",
    "documents":  "Documents",
    "extends":    "Extends",
    "mentions":   "Mentions",
}

edges  = {}   # canonical key -> edge
broken = {}   # (src, target, code) -> record

def collect_edges(src, related_items, via_step):
    """Add canonical edges for src's relations, redirecting step targets to their workflow."""
    for r in related_items:
        tgt_raw = r.get("persistentId")
        code    = (r.get("relation") or {}).get("code", "")
        if not tgt_raw or not code:
            continue
        tgt = step_to_workflow.get(tgt_raw, tgt_raw)
        if tgt not in node_map:
            # Target is not a published item: report it, don't draw it
            broken.setdefault((src, tgt_raw, code), {
                "source_id":       src,
                "source_label":    node_map[src]["label"],
                "source_category": node_map[src]["category"],
                "relation":        code,
                "relation_label":  (r.get("relation") or {}).get("label") or code,
                "target_id":       tgt_raw,
                "target_label":    r.get("label"),
                "target_category": r.get("category"),
                "via_step":        via_step,
            })
            continue
        # Skip self-loops (workflow relating to itself via a step)
        if tgt == src:
            continue
        a, b = src, tgt
        if code in INVERSE:            # "A is-mentioned-in B" == "B mentions A"
            code = INVERSE[code]
            a, b = b, a
        key = (*sorted((a, b)), code) if code in SYMMETRIC else (a, b, code)
        if key in edges:
            continue
        edges[key] = {
            "from":  a,
            "to":    b,
            "label": REL_LABEL.get(code, code),
            "code":  code,
        }

for it in items:
    src = it.get("persistentId")
    if not src:
        continue
    # Item-level relations
    collect_edges(src, it.get("relatedItems") or [], False)
    # Step relations: walk recursively, attribute all to the parent workflow
    def walk_steps(steps):
        for step in steps:
            collect_edges(src, step.get("relatedItems") or [], True)
            walk_steps(step.get("composedOf") or [])
    walk_steps(it.get("composedOf") or [])

edges = list(edges.values())

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
meta = {
    "snapshot":    snap_path.name,
    "snapshot_ts": int(ts_str) if ts_str.isdigit() else None,
    "generated":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"meta": meta, "nodes": nodes, "edges": edges}, fh,
              ensure_ascii=False, separators=(",", ":"))

PROCESSED.mkdir(parents=True, exist_ok=True)
broken_path = PROCESSED / f"broken_relations_{ts_str}.json"
broken_list = sorted(broken.values(), key=lambda b: (b["target_id"], b["source_id"], b["relation"]))
with open(broken_path, "w", encoding="utf-8") as fh:
    json.dump(broken_list, fh, ensure_ascii=False, indent=2)

print(f"Wrote {OUT}")
print(f"  Nodes : {len(nodes)}")
print(f"  Edges : {len(edges)}")
cats = collections.Counter(n["category"] for n in nodes)
rels = collections.Counter(e["code"] for e in edges)
print(f"  Categories : {dict(cats)}")
print(f"  Relations  : {dict(rels)}")
print(f"Wrote {broken_path} ({len(broken_list)} relations to items not in the snapshot)")
