#!/usr/bin/env python3

#"Takes the dataframe from the latest full_items_expanded_<ts>.json file and checks all URLs, outputting a dataframe."

import json, pathlib, pandas as pd
import importlib
import sys
import asyncio
import nest_asyncio
from tqdm.auto import tqdm

# Ensure repo root is on sys.path so sibling package `sshmarketplacelib` can be imported
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sshmarketplacelib import eval as eva, helper as hel

pathlib.Path("data/processed")
OUT_FILE_PATTERN = "full_items_URLcheck_{}.json"

#read the latest full_items<ts>.json file
IN_DIR = pathlib.Path("../data/")
existing_files = list(IN_DIR.glob("full_items_*.json"))
print(f"Found {len(existing_files)} input files in {IN_DIR} matching full_items_*.json")
if not existing_files:
    print("No input files found.")
else:
    latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
    ts_str = latest_file.stem.split("_")[-1]
    in_path = IN_DIR / f"full_items_{ts_str}.json"
    df = pd.read_json(in_path, orient="records")
    print(f"loaded {in_path} with {len(df)} items")


#check URLs for all items, add columns for URL status. Define the fields to check and whether to use async (faster, check if this work via GH actions)
def check_urls(row, var, mode):
    if mode not in ['sync', 'async']:
        raise ValueError("mode must be 'sync' or 'async'")
    if var not in row:
        return pd.Series({f'{var}_status': 'missing'})
    urls = []
    if var in row and row[var]:
        #split the fields list into individual URLs and check each one
        if isinstance(row[var], list):
            for url in row[var]:
                urls.append((var, url))
        else:
            urls.append((var, row[var]))
    results = {}
    if mode == 'async':
        nest_asyncio.apply()
        #funtion to check a single URL. Returns a tuple of (field, url, status). Self-contained so it can be used with asyncio.gather
        async def check_url(field, url): #rewrite from scratch to be self-contained and not rely on eva.simple_URL_check, which is not async
            try:
                status = await eva.async_URL_check(url) #this is not defined yet, but will be an async version of simple_URL_check that uses aiohttp or similar to check the URL without blocking
            except Exception as e:
                status = f'error: {str(e)}'
            return (field, url, status)
        #check all URLs asynchronously
        async def check_all_urls_async():
            tasks = []
            for field, url in urls:
                tasks.append(check_url(field, url))
            return await asyncio.gather(*tasks)
        loop = asyncio.get_event_loop()
        url_results = loop.run_until_complete(check_all_urls_async())
        for field, url, status in url_results:
            results[f'{field}_status'] = status
    else:
        for field, url in urls:
            status = eva.simple_URL_check(url)
            results[f'{field}_status'] = status
    #return the results, the checked URLS, and the MP persistent ID for reference
    results['checked_URLs'] = [url for field, url in urls]
    results['persistentId'] = row.get('persistentId', None)
    #construct the MP URL
    if 'persistentId' in row and row['persistentId']:
        results['MP_URL'] = f"https://marketplace.sshopencloud.eu/{row['category']}/{row['persistentId']}"
    else:
        results['MP_URL'] = None
    return pd.Series(results)
   
   
#apply on df for accessibleAt, logging progress every 100 items os we know it's working and not stuck. Use async mode for faster checking, but can switch to sync if there are issues with async in GH actions or similar environments.
tqdm.pandas(desc="Checking accessibleAt")

df_urls = df.progress_apply(
    lambda row: check_urls(row, "accessibleAt", mode="async"),
    axis=1
)
#filter the new dataframe, drop all 200s and keep only the items with URL issues for review
df_issues = df_urls[df_urls['accessibleAt_status'] != 200]
print(f"Found {len(df_issues)} items with URL issues out of {len(df)} total items.")
#save the results to a new csv file for review, including the persistentId and MP URL for reference
out_path = OUT_DIR / OUT_FILE_PATTERN.format(ts_str)
df_issues.to_csv(out_path, index=True)
print(f"Saved URL check results to {out_path}")