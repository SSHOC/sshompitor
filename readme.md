# sshompitor

Monitoring and data quality tool for the [SSH Open Marketplace](https://marketplace.sshopencloud.eu/) (SSHOMP) — a catalog of tools, datasets, publications, workflows, and training materials for the Social Sciences and Humanities.

## What it does

- Fetches a full snapshot of all public Marketplace items weekly via the REST API
- Checks each item against a metadata completeness profile and scores it (0–100)
- Identifies items with missing recommended fields (description, keywords, license, etc.)
- Checks HTTP status of `accessibleAt` URLs
- Generates an interactive HTML dashboard for reviewing metadata completeness

## Repository layout

```
sshompitor/
├── sshmarketplacelib/          # Core Python library
│   ├── mpdata.py               # Marketplace API client, item fetching
│   ├── helper.py               # Data analysis utilities, metadata validation
│   └── eval.py                 # URL checking (sync + async)
├── scripts/
│   ├── fetch_full_items.py     # Fetch all items → data/full_items_<ts>.json
│   ├── process_props.py        # Expand/flatten properties column
│   ├── check_recommended_Md.py # Validate metadata completeness per item
│   ├── visualize_data.py       # Generate HTML dashboard
│   └── checkURLs.py            # HTTP-check all accessibleAt URLs
├── .github/workflows/
│   ├── weekly-dump.yml         # Fetch + commit snapshot (Mon 03:00 UTC)
│   ├── create_dashboard.yml    # Full pipeline: props → MD check → dashboard (triggered by dump)
│   ├── stats_daily.yml         # Lightweight daily item counts per category/source
│   ├── process_props.yml       # Manual trigger only
│   ├── check_recommended_md.yml# Manual trigger only
│   └── category_data.yml       # Daily per-category fetch → artifact
├── data/
│   ├── full_items_<ts>.json    # Weekly snapshots (all categories, flat records)
│   └── processed/
│       ├── full_items_expanded_<ts>.json   # With prop_counts column added
│       └── full_items_MDcheck_<ts>.json    # Items with missing fields + score
├── dashboard_output/
│   └── metadata_dashboard_table_<ts>.html  # Weekly dashboard (committed)
├── config.yaml                 # API endpoints and category config
├── requirements.txt
└── setup.py
```

## Automated pipeline

The main pipeline runs every Monday, triggered by the completion of the data dump:

```
weekly-dump.yml (Mon 03:00 UTC)
  → fetches all items from API
  → commits data/full_items_<ts>.json to main

create_dashboard.yml (triggered on dump completion)
  → process_props.py        produces data/processed/full_items_expanded_<ts>.json
  → check_recommended_Md.py produces data/processed/full_items_MDcheck_<ts>.json
  → visualize_data.py       produces dashboard_output/metadata_dashboard_table_<ts>.html
  → commits dashboard HTML and MDcheck JSON to main
```

A fallback schedule (Tuesday 06:00 UTC) covers cases where `workflow_run` is not triggered.

`stats_daily.yml` runs separately at 01:00 UTC every day and records lightweight item counts into `items.json` and `sources.json` at the repo root.

## Metadata profile

Items are validated against a per-category profile. Fields are grouped into:

| Group | Examples |
|---|---|
| Generic Metadata | label, description, contributors, accessibleAt, media, thumbnail |
| Categorisation Metadata | activity, keyword, discipline, language, intended-audience |
| Context Metadata | see-also |
| Access Metadata | license |
| Technical Metadata | technology-readiness-level, version (tools only) |
| Bibliographic Metadata | publication-type, publisher, year, journal (publications/datasets) |

Each item receives a score (0–100) based on the fraction of fields present. Items with any missing fields are included in the dashboard.

## Library

`sshmarketplacelib` is installed as a local package (`pip install -e .`). The three modules are:

**`mpdata.MPData`** — API client
Fetches paginated item lists from the Marketplace REST API by category. Used by `fetch_full_items.py`.

**`helper.Util`** — Analysis utilities
Loads the latest JSON snapshot and provides methods for source statistics, contributor listing, property frequency, related-item queries, and null-value analysis. Module-level functions (`validate_metadata`, `find_items_missing_profile`, `properties_to_dict`) implement the metadata profile validation used by `check_recommended_Md.py`.

**`eval.URLCheck`** — URL checking
Checks HTTP status of URLs extracted from item fields. Module-level `simple_URL_check` (sync) and `async_URL_check` (aiohttp) are used by `checkURLs.py`.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt
```

Copy `config.yaml` and fill in your API credentials if write operations are needed. For read-only use (fetching and analysis) the credential fields are not required.

```bash
# Fetch a fresh snapshot
python scripts/fetch_full_items.py

# Run the full dashboard pipeline
python scripts/process_props.py
python scripts/check_recommended_Md.py
python scripts/visualize_data.py

# Check URLs
python scripts/checkURLs.py
```

## Configuration

`config.yaml` controls API endpoints and categories:

```yaml
DEBUG: True        # If True, write operations do not modify the Marketplace

API:
  SERVER: https://marketplace-api.sshopencloud.eu/
  USER: <your-user>
  PASSWORD: <your-password>

CATEGORIES:
  - toolsandservices
  - publications
  - trainingmaterials
  - workflows
  - datasets
```

## GitHub Actions secrets

The commit steps in `weekly-dump.yml` and `create_dashboard.yml` require a personal access token with `contents: write` permission stored as `ACTIONS_PAT` in the repository secrets.
