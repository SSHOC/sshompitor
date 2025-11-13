#!/usr/bin/env python3

"Takes the dataframe from the latest full_items_expanded_<ts>.json file and checks for items missing recommended metadata fields, outputting a dataframe."
import json, pathlib, pandas as pd
import importlib
import sys
# Ensure repo root is on sys.path so sibling package `sshmarketplacelib` can be imported
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sshmarketplacelib import eval as eva, helper as hel
importlib.reload(hel) #debug reload

OUT_DIR = pathlib.Path("data/processed")
OUT_FILE_PATTERN = "full_items_MDcheck_{}.json"



#read the latest full_items_expanded_<ts>.json file
IN_DIR = pathlib.Path("data/processed")
existing_files = list(IN_DIR.glob("full_items_expanded_*.json"))
if not existing_files:
    print("No input files found.")
else:
    latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
    ts_str = latest_file.stem.split("_")[-1]
    in_path = IN_DIR / f"full_items_expanded_{ts_str}.json"
    df = pd.read_json(in_path, orient="records")
    print(f"loaded {in_path} with {len(df)} items")

# Items with missing fields and their scores.
df_missing = hel.find_items_missing_profile(df)

print(f"found {len(df_missing)} items for missing profile fields")

#create output file with timestamp
out_path = OUT_DIR / OUT_FILE_PATTERN.format(ts_str) #use current timestamp
df_missing.to_json(out_path, orient="records", indent=2)
print(f"✅ wrote {out_path}")