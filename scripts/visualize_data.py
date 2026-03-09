#!/usr/bin/env python3
"""
visualize_data.py

Generates the metadata completeness HTML dashboard.
Output: dashboard_output/metadata_dashboard_table.html
"""

import json
import pathlib
from datetime import datetime, timezone

import pandas as pd

IN_DIR  = pathlib.Path("data/processed")
OUT_DIR = pathlib.Path("dashboard_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Find latest input file ---
existing_files = sorted(IN_DIR.glob("full_items_MDcheck_*.json"), key=lambda p: p.stat().st_mtime)
if not existing_files:
    raise SystemExit("No input files found in data/processed matching full_items_MDcheck_*.json")

latest_file = existing_files[-1]
ts_str = latest_file.stem.split("_")[-1]

with open(latest_file, "r", encoding="utf-8") as fh:
    data = json.load(fh)

df = pd.DataFrame(data)

# --- Preprocessing ---
def _norm_list(x):
    if isinstance(x, (list, tuple)): return list(x)
    if pd.isna(x): return []
    return [x]

for col, default in [("missing_fields", []), ("score", 0.0), ("missing_count", 0),
                     ("category", ""), ("persistentId", ""), ("label", ""),
                     ("source.label", "user-created")]:
    if col not in df.columns:
        df[col] = default

df["missing_fields"] = df["missing_fields"].apply(_norm_list)
df["score"]          = pd.to_numeric(df["score"],         errors="coerce").fillna(0.0)
df["missing_count"]  = pd.to_numeric(df["missing_count"], errors="coerce").fillna(0).astype(int)
df["source.label"]   = df["source.label"].fillna("user-created")
df["url"]            = ("https://marketplace.sshopencloud.eu/"
                        + df["category"].astype(str) + "/"
                        + df["persistentId"].astype(str))

# --- Summary stats ---
n_items      = len(df)
n_categories = int(df["category"].nunique())
avg_score    = round(float(df["score"].mean()), 1) if n_items else 0.0
n_complete   = int((df["score"] == 100).sum())

# --- Table JSON ---
table_data = df[["persistentId", "label", "category", "score", "missing_count",
                 "source.label", "url", "missing_fields"]].rename(columns={
    "persistentId":   "ID",
    "source.label":   "Source",
    "missing_count":  "Missing",
    "missing_fields": "MissingFields",
})
table_json = table_data.to_json(orient="records", force_ascii=False)

# --- Timestamps ---
try:
    snapshot_date = datetime.fromtimestamp(int(ts_str), tz=timezone.utc).strftime("%d %b %Y")
except (ValueError, OSError):
    snapshot_date = ts_str
gen_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# --- HTML (plain string; __PLACEHOLDER__ avoids JS-brace conflicts) ---
HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Metadata Completeness Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.3.6/css/buttons.bootstrap5.min.css">
<style>
  body { font-size: 0.875rem; background: #f8f9fa; }
  .main-card { background: #fff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .stat-card { border-left: 3px solid; border-radius: 6px; }
  .stat-card.c-primary { border-color: #0d6efd; }
  .stat-card.c-info    { border-color: #0dcaf0; }
  .stat-card.c-warning { border-color: #ffc107; }
  .stat-card.c-success { border-color: #198754; }
  .score-bar { display:flex; align-items:center; gap:5px; }
  .score-track { flex:1; height:7px; background:#e9ecef; border-radius:4px; overflow:hidden; min-width:40px; }
  .score-fill  { height:100%; border-radius:4px; }
  .score-lbl   { font-size:0.78em; min-width:2em; text-align:right; color:#666; }
  .miss-list   { max-height:110px; overflow-y:auto; padding-left:1.1rem; margin:0; font-size:0.82em; }
  #miss-chips  { display:flex; flex-wrap:wrap; gap:5px; list-style:none; padding:0; margin:0; }
  #miss-chips li {
    cursor:pointer; background:#f1f3f5; border:1px solid #dee2e6;
    border-radius:20px; padding:2px 10px; font-size:0.8em; white-space:nowrap;
    transition: background .15s;
  }
  #miss-chips li:hover, #miss-chips li.active { background:#0d6efd; color:#fff; border-color:#0d6efd; }
  a.mp-link { text-decoration:none; font-size:1.1em; }
  a.mp-link:hover { color:#0d6efd; }
</style>
</head>
<body>
<div class="container-fluid px-4 py-3">

<!-- Header -->
<div class="d-flex align-items-baseline justify-content-between mb-3">
  <h5 class="mb-0 fw-semibold">SSHOC Marketplace &mdash; Metadata Completeness</h5>
  <span class="text-muted" style="font-size:0.78em">
    Snapshot: <strong>__SNAPSHOT_DATE__</strong>
    &nbsp;&middot;&nbsp;
    Dashboard generated: __GEN_DATE__
  </span>
</div>

<!-- Stats row -->
<div class="row g-2 mb-3">
  <div class="col-6 col-md-3">
    <div class="card stat-card c-primary h-100 px-3 py-2">
      <div class="fs-3 fw-bold text-primary lh-1 mb-1">__N_ITEMS__</div>
      <div class="text-muted small">Items with metadata issues</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card c-info h-100 px-3 py-2">
      <div class="fs-3 fw-bold lh-1 mb-1" style="color:#0dcaf0">__N_CATS__</div>
      <div class="text-muted small">Categories represented</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card c-warning h-100 px-3 py-2">
      <div class="fs-3 fw-bold text-warning lh-1 mb-1">__AVG_SCORE__</div>
      <div class="text-muted small">Average completeness score</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card c-success h-100 px-3 py-2">
      <div class="fs-3 fw-bold text-success lh-1 mb-1">__N_COMPLETE__</div>
      <div class="text-muted small">Fully complete (score&nbsp;100)</div>
    </div>
  </div>
</div>

<!-- Most-missing fields -->
<div class="main-card mb-3 p-3">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span class="fw-semibold small">Most-missing fields</span>
    <small class="text-muted">Click a field to filter the table</small>
    <button id="clear-miss-btn" class="btn btn-sm btn-link p-0 ms-auto text-secondary" style="display:none;font-size:0.8em">
      Clear field filter &times;
    </button>
  </div>
  <ul id="miss-chips"></ul>
</div>

<!-- Controls + table -->
<div class="main-card p-3">
  <div class="d-flex flex-wrap gap-2 align-items-center mb-2">
    <select id="cat-filter" class="form-select form-select-sm" style="width:auto">
      <option value="">All Categories</option>
    </select>
    <select id="src-filter" class="form-select form-select-sm" style="width:auto">
      <option value="">All Sources</option>
    </select>
    <button id="clear-filters-btn" class="btn btn-sm btn-outline-secondary">Clear all filters</button>
  </div>

  <table id="resource-table" class="table table-sm table-striped table-hover align-top" style="width:100%">
    <thead class="table-light">
      <tr>
        <th>ID</th>
        <th>Label</th>
        <th>Category</th>
        <th>Score</th>
        <th>Missing #</th>
        <th>Missing Fields</th>
        <th>Source</th>
        <th></th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</div>

</div><!-- /container -->

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js"></script>

<script>
const tableData = __TABLE_JSON__;

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                   .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}
function escRe(s) { return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'); }

function scoreColor(s) {
  if (s >= 90) return '#198754';
  if (s >= 70) return '#ffc107';
  if (s >= 40) return '#fd7e14';
  return '#dc3545';
}

// Build missing-fields chips
(function() {
  var counts = {};
  tableData.forEach(function(d) {
    (d.MissingFields || []).forEach(function(f) { counts[f] = (counts[f]||0)+1; });
  });
  var ul = document.getElementById('miss-chips');
  Object.entries(counts).sort(function(a,b){ return b[1]-a[1]; }).forEach(function(e) {
    var li = document.createElement('li');
    li.title = e[1] + ' items missing this field — click to filter';
    li.innerHTML = esc(e[0]) + ' <span style="opacity:.65">(' + e[1] + ')</span>';
    li.dataset.field = e[0];
    li.onclick = function() {
      document.querySelectorAll('#miss-chips li').forEach(function(el){ el.classList.remove('active'); });
      this.classList.add('active');
      dt.column(5).search(escRe(e[0])).draw();
      document.getElementById('cat-filter').value = '';
      document.getElementById('src-filter').value = '';
      dt.column(2).search('').draw();
      dt.column(6).search('').draw();
      document.getElementById('clear-miss-btn').style.display = '';
    };
    ul.appendChild(li);
  });
})();

document.getElementById('clear-miss-btn').onclick = function() {
  dt.column(5).search('').draw();
  document.querySelectorAll('#miss-chips li').forEach(function(el){ el.classList.remove('active'); });
  this.style.display = 'none';
};

// DataTable
const dt = $('#resource-table').DataTable({
  data: tableData,
  columns: [
    { data:'ID', width:'7%' },
    { data:'label', width:'23%' },
    { data:'category', width:'10%' },
    {
      data:'score', width:'13%',
      render: function(data, type) {
        if (type !== 'display') return data;
        var s = Number(data || 0);
        return '<div class="score-bar">'
          + '<div class="score-track"><div class="score-fill" style="width:'+s+'%;background:'+scoreColor(s)+'"></div></div>'
          + '<span class="score-lbl">'+s.toFixed(0)+'</span>'
          + '</div>';
      }
    },
    { data:'Missing', width:'6%' },
    {
      data:'MissingFields', orderable:false, searchable:true, width:'27%',
      render: function(data) {
        if (!Array.isArray(data) || !data.length) return '<em class="text-muted">\u2014</em>';
        return '<ul class="miss-list">'
          + data.map(function(f){ return '<li>'+esc(f)+'</li>'; }).join('')
          + '</ul>';
      }
    },
    { data:'Source', width:'10%' },
    {
      data:'url', orderable:false, searchable:false, width:'4%',
      render: function(data) {
        return data
          ? '<a href="'+esc(data)+'" target="_blank" rel="noopener noreferrer" class="mp-link" title="Open in Marketplace">&#8599;</a>'
          : '';
      }
    }
  ],
  dom: "<'row align-items-center mb-2'<'col-auto'B><'col'f>>rt<'row mt-2'<'col text-muted small'i><'col-auto'p>>",
  buttons: [
    { extend:'csv',   text:'Export CSV',   className:'btn btn-sm btn-outline-secondary' },
    { extend:'excel', text:'Export Excel', className:'btn btn-sm btn-outline-secondary' }
  ],
  pageLength: 100,
  order: [[3, 'asc']],
  language: { search: '', searchPlaceholder: 'Search\u2026' }
});

// Populate dropdowns
[...new Set(tableData.map(function(d){return d.category;}).filter(Boolean))].sort().forEach(function(v){
  $('#cat-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});
[...new Set(tableData.map(function(d){return d.Source;}).filter(Boolean))].sort().forEach(function(v){
  $('#src-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});

$('#cat-filter').on('change', function(){
  dt.column(2).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#src-filter').on('change', function(){
  dt.column(6).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#clear-filters-btn').on('click', function(){
  dt.search('').columns().search('').draw();
  $('#cat-filter,#src-filter').val('');
  document.querySelectorAll('#miss-chips li').forEach(function(el){ el.classList.remove('active'); });
  document.getElementById('clear-miss-btn').style.display = 'none';
});
</script>
</body>
</html>
"""

html = (HTML
    .replace("__TABLE_JSON__",    table_json)
    .replace("__N_ITEMS__",       str(n_items))
    .replace("__N_CATS__",        str(n_categories))
    .replace("__AVG_SCORE__",     str(avg_score))
    .replace("__N_COMPLETE__",    str(n_complete))
    .replace("__SNAPSHOT_DATE__", snapshot_date)
    .replace("__GEN_DATE__",      gen_date))

out_path = OUT_DIR / "metadata_dashboard_table.html"
with open(out_path, "w", encoding="utf-8") as fo:
    fo.write(html)

print(f"Wrote dashboard to: {out_path}")
