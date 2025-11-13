#!/usr/bin/env python3
"""
visualize_data_table_only.py

Generates an HTML dashboard (no Plotly) containing:
 - Missing Fields Summary (counts)
 - Source filter
 - DataTable with Resource list and inline MissingFields display
"""

import json
import pathlib
import pandas as pd

# --- Configuration ---
IN_DIR = pathlib.Path("data/processed")
OUT_DIR = pathlib.Path("dashboard_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Find latest input file ---
existing_files = sorted(IN_DIR.glob("full_items_MDcheck_*.json"), key=lambda p: p.stat().st_mtime)
if not existing_files:
    raise SystemExit("No input files found in data/processed matching full_items_MDcheck_*.json")

latest_file = existing_files[-1]
ts_str = latest_file.stem.split("_")[-1]
in_path = IN_DIR / f"full_items_MDcheck_{ts_str}.json"

# --- Load data ---
with open(in_path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

df = pd.DataFrame(data)

# --- Defensive preprocessing ---
# Ensure missing_fields exists and is a list
if 'missing_fields' not in df.columns:
    df['missing_fields'] = [[] for _ in range(len(df))]
else:
    def normalize_missing(x):
        if isinstance(x, (list, tuple)):
            return list(x)
        if pd.isna(x):
            return []
        # If it's a single string (or other scalar), put into list
        return [x]
    df['missing_fields'] = df['missing_fields'].apply(normalize_missing)

# Ensure some other columns exist
df['source.label'] = df.get('source.label', pd.Series(['user-created'] * len(df))).fillna('user-created')
df['score'] = pd.to_numeric(df.get('score', pd.Series([0]*len(df))), errors='coerce').fillna(0.0)
df['missing_count'] = pd.to_numeric(df.get('missing_count', pd.Series([0]*len(df))), errors='coerce').fillna(0).astype(int)
df['category'] = df.get('category', pd.Series([''] * len(df))).fillna('')
df['persistentId'] = df.get('persistentId', pd.Series([''] * len(df))).fillna('')

# Build safe URL column
df['url'] = 'https://marketplace.sshopencloud.eu/' + df['category'].astype(str) + '/' + df['persistentId'].astype(str)

# Prepare table JSON (include missing_fields)
table_data = df[['persistentId', 'label', 'category', 'score', 'missing_count', 'source.label', 'url', 'missing_fields']].copy()
table_data = table_data.rename(columns={
    'persistentId': 'ID',
    'source.label': 'Source',
    'missing_count': 'Missing',
    'missing_fields': 'MissingFields'
})

# Convert to JSON string for embedding in JS. This results in a JSON array literal.
table_json = table_data.to_json(orient='records', force_ascii=False)

# Generate HTML content
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Metadata Completeness Dashboard — In development</title>

<!-- DataTables CSS & JS -->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.3.6/css/buttons.dataTables.min.css">

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js"></script>

<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; }}
  .dashboard-title {{ text-align: center; margin-bottom: 16px; }}
  .controls {{ display:flex; gap:20px; align-items:center; margin-bottom:14px; }}
  .missing-summary {{ margin-bottom: 18px; }}
  #missing-fields-ul {{ columns: 2; -webkit-columns: 2; -moz-columns: 2; list-style: none; padding-left: 0; }}
  #missing-fields-ul li {{ margin: 4px 0; }}
  .missing-badge {{ background: #eee; border-radius: 4px; padding: 2px 6px; margin-left: 8px; font-size: 0.9em; }}
  .missing-list-inline ul {{ margin:0; padding-left:1rem; }}
  .missing-list-inline {{ max-height: 130px; overflow:auto; }}
  table.dataTable td {{ vertical-align: top; }}
</style>
</head>
<body>
  <h1 class="dashboard-title">Metadata Completeness Dashboard</h1>

  <div class="controls">
    <div>
      <label for="source-select"><strong>Filter by Source:</strong></label>
      <select id="source-select">
        <option value="">All Sources</option>
      </select>
    </div>
    <div style="flex:1"></div>
    <div>
      <small>Export:  CSV / Excel available in table buttons</small>
    </div>
  </div>

  <div class="missing-summary">
    <h3>Missing Fields Summary</h3>
    <div class="missing-list-inline">
      <ul id="missing-fields-ul"></ul>
    </div>
  </div>

  <div class="data-table-container">
    <h3>Resource List</h3>
    <table id="resource-table" class="display" style="width:100%">
      <thead>
        <tr>
          <th>ID</th>
          <th>Label</th>
          <th>Category</th>
          <th>Score</th>
          <th>Missing</th>
          <th>Missing Fields</th>
          <th>Source</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

<script>
// Embedded table data (JS array)
const tableData = {table_json};

// Simple HTML escape
function escapeHtml(str) {{
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}}

// Build missing fields summary counts
(function buildMissingSummary() {{
  const counts = {{}};
  tableData.forEach(item => {{
    const mf = item.MissingFields;
    if (Array.isArray(mf)) {{
      mf.forEach(f => {{
        counts[f] = (counts[f] || 0) + 1;
      }});
    }}
  }});
  const entries = Object.entries(counts).sort((a,b) => b[1] - a[1]);
  const ul = document.getElementById('missing-fields-ul');
  if (entries.length === 0) {{
    ul.innerHTML = '<li><em>No missing fields</em></li>';
    return;
  }}
  const frag = document.createDocumentFragment();
  entries.forEach(([field, cnt]) => {{
    const li = document.createElement('li');
    li.innerHTML = `<span class="field-name">${{escapeHtml(field)}}</span><span class="missing-badge">${{cnt}}</span>`;
    // make each field clickable to filter the table by that missing field
    li.style.cursor = 'pointer';
    li.title = 'Click to filter resources missing this field';
    li.addEventListener('click', () => {{
      // set the table search to find rows whose MissingFields contain this exact field string
      // We'll use DataTables column renderer to include the text; use regex search on column 5 (0-based)
      $('#resource-table').DataTable().column(5).search(escapeRegex(field)).draw();
      // Also set dropdown to blank (so source filter not interfering)
      document.getElementById('source-select').value = '';
    }});
    frag.appendChild(li);
  }});
  ul.appendChild(frag);
}})();

// Utility to escape regex special chars for DataTables search
function escapeRegex(text) {{
  return text.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
}}

// Populate source filter dropdown
const sources = [...new Set(tableData.map(item => item.Source))].filter(s => s !== null && s !== undefined && s !== '');
const sourceSelect = document.getElementById('source-select');
sources.forEach(src => {{
  const opt = document.createElement('option');
  opt.value = src;
  opt.textContent = src;
  sourceSelect.appendChild(opt);
}});

// Initialize DataTable
const table = $('#resource-table').DataTable({{
  data: tableData,
  columns: [
    {{ data: 'ID' }},
    {{ data: 'label' }},
    {{ data: 'category' }},
    {{
      data: 'score',
      render: function(data, type) {{
        if (type === 'display' && data !== null && data !== undefined) return Number(data).toFixed(1);
        return data;
      }}
    }},
    {{ data: 'Missing' }},
    {{
      data: 'MissingFields',
      orderable: false,
      searchable: true,
      render: function(data, type) {{
        if (!Array.isArray(data) || data.length === 0) return '<em>—</em>';
        const items = data.map(d => `<li>${{escapeHtml(d)}}</li>`).join('');
        return `<div class="missing-list-inline"><ul style="margin:0 0 0 1rem;padding-left:0">${{items}}</ul></div>`;
      }}
    }},
    {{ data: 'Source' }},
    {{
      data: 'url',
      render: function(data) {{
        if (!data) return '';
        const u = escapeHtml(data);
        return `<a href="${{u}}" target="_blank" rel="noopener noreferrer">Open</a>`;
      }}
    }}
  ],
  dom: 'Bfrtip',
  buttons: ['csv', 'excel'],
  pageLength: 100,
  order: [[6, 'desc']], // Sort by the 8th column (index 7) = Missing Count
  columnDefs: [
    {{ targets: [0,3,4], width: '8%' }},
    {{ targets: [1], width: '25%' }},
    {{ targets: [2,5,6,7], width: '14%' }}
  ]
}});

// Source filter behavior (exact match)
sourceSelect.addEventListener('change', function() {{
  const src = this.value;
  if (src) {{
    // column 6 is Source (zero-based index)
    $('#resource-table').DataTable().column(6).search('^' + escapeRegex(src) + '$', true, false).draw();
    // clear missing fields search
    $('#resource-table').DataTable().column(5).search('').draw();
  }} else {{
    $('#resource-table').DataTable().column(6).search('').draw();
  }}
}});

</script>
</body>
</html>
"""

out_path = OUT_DIR / f"metadata_dashboard_table_{ts_str}.html"
with open(out_path, "w", encoding="utf-8") as fo:
    fo.write(html_content)

print(f"Wrote dashboard to: {out_path}")
