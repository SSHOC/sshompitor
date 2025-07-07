#!/usr/bin/env python3
"""
Fetches all SSHOC Marketplace items and writes two files:

• data/full_items.json  – entire merged dataframe as JSON records
• data/full_items.parquet  – same data in Parquet (smaller + faster)

The enclosing timestamp key is not needed when we write a
timestamped filename in the workflow (e.g. full_items_<ts>.json).
"""

import time, json, pathlib, pandas as pd
from sshmarketplacelib import MPData

OUT_DIR = pathlib.Path("data")
OUT_DIR.mkdir(exist_ok=True)

mp = MPData()

dfs = {
    "toolsandservices":    mp.getMPItems("toolsandservices",    False),
    "publications":        mp.getMPItems("publications",        False),
    "trainingmaterials":   mp.getMPItems("trainingmaterials",   False),
    "workflows":           mp.getMPItems("workflows",           False),
    "datasets":            mp.getMPItems("datasets",            False),
}

df_all = pd.concat(dfs.values(), ignore_index=True)
ts = int(time.time())

# JSON snapshot (records is friendliest for later pandas reload)
json_path = OUT_DIR / f"full_items_{ts}.json"
df_all.to_json(json_path, orient="records", indent=2)

# Optional Parquet snapshot
parquet_path = OUT_DIR / f"full_items_{ts}.parquet"
df_all.to_parquet(parquet_path)

print(f"✅ wrote {json_path} and {parquet_path}")
