#!/usr/bin/env python3

"Takes the full_items_<ts>.json file with the latest timestamp and expands the properties field into separate columns, out putting to full_items_expanded_<ts>.json."
import json, pathlib, pandas as pd
import importlib
from sshmarketplacelib import  eval as eva, helper as hel
importlib.reload(hel)
util = hel.Util()


OUT_DIR = pathlib.Path("data/processed")
IN_FILE_PATTERN = "full_items_{}.json"
IN_DIR = pathlib.Path("data")
OUT_FILE_PATTERN = "full_items_expanded_{}.json"
def process_props(ts: int):
    in_path = IN_DIR / IN_FILE_PATTERN.format(ts)
    out_path = OUT_DIR / OUT_FILE_PATTERN.format(ts)
    df = pd.read_json(in_path, orient="records")
    # 1) Per-row dict of code -> count (handles JSON strings or lists)
    df['prop_counts'] = df['properties'].apply(lambda v: hel.properties_to_dict(v, as_counts=False))
    #create output file with timestamp
    df.to_json(out_path, orient="records", indent=2)
    print(f"✅ wrote {out_path}")

#now apply for the latest file
existing_files = list(IN_DIR.glob("full_items_*.json"))
if not existing_files:
    print("No input files found.")
else:
    latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
    ts_str = latest_file.stem.split("_")[-1]
    process_props(ts_str)   

    
