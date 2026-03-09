#!/usr/bin/env python3
"""
create_curation_dashboard.py

Generates a curation HTML dashboard combining:
  - Metadata completeness issues  (data/processed/full_items_MDcheck_<ts>.json)
  - URL check results             (data/processed/full_items_URLcheck_<ts>.csv, optional)

Output: dashboard_output/curation_dashboard.html
"""

import ast
import json
import pathlib
from datetime import datetime, timezone

import pandas as pd

PROCESSED = pathlib.Path("data/processed")
DATA      = pathlib.Path("data")
OUT       = pathlib.Path("dashboard_output")
OUT.mkdir(parents=True, exist_ok=True)

# ── 1.  Metadata-completeness data ───────────────────────────────────────────

md_files = sorted(PROCESSED.glob("full_items_MDcheck_*.json"),
                  key=lambda p: p.stat().st_mtime)
if not md_files:
    raise SystemExit("No full_items_MDcheck_*.json found in data/processed")

ts_str = md_files[-1].stem.rsplit("_", 1)[-1]

with open(md_files[-1], encoding="utf-8") as fh:
    df_md = pd.DataFrame(json.load(fh))


def _to_list(x):
    if isinstance(x, (list, tuple)):
        return list(x)
    if pd.isna(x):
        return []
    return [str(x)]


for col, default in [("missing_fields", []), ("score", 0.0), ("missing_count", 0),
                     ("category", ""), ("persistentId", ""),
                     ("label", ""), ("source.label", "user-created")]:
    if col not in df_md.columns:
        df_md[col] = default

df_md["missing_fields"] = df_md["missing_fields"].apply(_to_list)
df_md["score"]          = pd.to_numeric(df_md["score"],         errors="coerce").fillna(0.0)
df_md["missing_count"]  = pd.to_numeric(df_md["missing_count"], errors="coerce").fillna(0).astype(int)
df_md["source.label"]   = df_md["source.label"].fillna("user-created")
df_md["url"]            = ("https://marketplace.sshopencloud.eu/"
                            + df_md["category"].astype(str) + "/"
                            + df_md["persistentId"].astype(str))

md_table = df_md[["persistentId", "label", "category", "score",
                   "missing_count", "missing_fields", "source.label", "url"]].rename(
    columns={"persistentId": "ID", "source.label": "Source",
             "missing_count": "Missing", "missing_fields": "MissingFields"})
md_json = md_table.to_json(orient="records", force_ascii=False)
n_md    = len(df_md)

# ── 2.  URL-check data (optional) ────────────────────────────────────────────

url_json      = "[]"
url_available = False
n_url         = 0

url_files = sorted(PROCESSED.glob("full_items_URLcheck_*.csv"),
                   key=lambda p: p.stat().st_mtime)
if url_files:
    df_u = pd.read_csv(url_files[-1], index_col=0)
    snap_files = sorted(DATA.glob("full_items_*.json"), key=lambda p: p.stat().st_mtime)
    if snap_files and "persistentId" in df_u.columns:
        snap = pd.read_json(snap_files[-1], orient="records")
        keep = [c for c in ["persistentId", "label", "category", "source.label"]
                if c in snap.columns]
        df_u = df_u.merge(snap[keep], on="persistentId", how="left")
        df_u["source.label"] = df_u["source.label"].fillna("user-created")
        if "checked_URLs" in df_u.columns:
            df_u["checked_URLs"] = df_u["checked_URLs"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
        if "MP_URL" in df_u.columns:
            df_u["url"] = df_u["MP_URL"].fillna("")
        df_u = df_u.rename(columns={"persistentId": "ID", "source.label": "Source",
                                     "accessibleAt_status": "Status",
                                     "checked_URLs": "URLs"})
        url_cols = [c for c in ["ID", "label", "category", "Status", "URLs", "Source", "url"]
                    if c in df_u.columns]
        url_json      = df_u[url_cols].to_json(orient="records", force_ascii=False)
        url_available = True
        n_url         = len(df_u)

# ── 3.  Build template values ─────────────────────────────────────────────────

gen_date      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
n_url_display = str(n_url) if url_available else "\u2014"
url_tab_label = f"URL Issues ({n_url})" if url_available else "URL Issues (not checked)"

if url_available:
    url_tab_body = """\
<div class="row g-2 mb-2">
  <div class="col-auto">
    <select id="url-cat-filter" class="form-select form-select-sm">
      <option value="">All Categories</option>
    </select>
  </div>
  <div class="col-auto">
    <select id="url-src-filter" class="form-select form-select-sm">
      <option value="">All Sources</option>
    </select>
  </div>
  <div class="col-auto">
    <button id="url-clear-btn" class="btn btn-outline-secondary btn-sm">Clear</button>
  </div>
</div>
<table id="url-table" class="table table-sm table-striped" style="width:100%">
  <thead><tr>
    <th>ID</th><th>Label</th><th>Category</th>
    <th>HTTP Status</th><th>Checked URL(s)</th><th>Source</th><th>Link</th>
  </tr></thead>
  <tbody></tbody>
</table>"""

    url_tab_js = """\
const urlTable = $('#url-table').DataTable({
  data: urlData,
  columns: [
    { data:'ID' },
    { data:'label' },
    { data:'category' },
    { data:'Status', render: function(d) {
        var s = String(d == null ? '' : d);
        var cls = s.charAt(0) === '2' ? 'status-ok' : 'status-err';
        return '<span class="' + cls + '">' + esc(s) + '</span>';
      }
    },
    { data:'URLs', orderable:false,
      render: function(d) {
        if (Array.isArray(d)) {
          return d.map(function(u){ return '<a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(u)+'</a>'; }).join('<br>');
        }
        return esc(String(d == null ? '' : d));
      }
    },
    { data:'Source' },
    { data:'url', render: function(d){ return d ? '<a href="'+esc(d)+'" target="_blank" rel="noopener">&#8599;</a>' : ''; } }
  ],
  dom: "<'row'<'col-sm-6'B><'col-sm-6'f>>rtip",
  buttons: ['csv','excel'],
  pageLength: 50,
  order: [[3,'asc']],
  columnDefs: [
    {targets:[0,3,6], width:'7%'},
    {targets:[1],     width:'20%'},
    {targets:[2,5],   width:'10%'},
    {targets:[4],     width:'32%'}
  ]
});

[...new Set(urlData.map(function(d){return d.category;}).filter(Boolean))].sort().forEach(function(v){
  $('#url-cat-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});
[...new Set(urlData.map(function(d){return d.Source;}).filter(Boolean))].sort().forEach(function(v){
  $('#url-src-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});

$('#url-cat-filter').on('change', function(){
  urlTable.column(2).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#url-src-filter').on('change', function(){
  urlTable.column(5).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#url-clear-btn').on('click', function(){
  urlTable.search('').columns().search('').draw();
  $('#url-cat-filter,#url-src-filter').val('');
});
$('#tab-url-btn').on('shown.bs.tab', function(){ urlTable.columns.adjust(); });"""

else:
    url_tab_body = """\
<div class="alert alert-info mt-3">
  <strong>URL check data not available.</strong><br>
  Run <code>python scripts/checkURLs.py</code> to check <code>accessibleAt</code> URLs,
  then re-run this script to include the results in the dashboard.
</div>"""
    url_tab_js = ""

# ── 4.  HTML (plain string — .replace() avoids JS-brace escaping issues) ─────

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SSHOC Marketplace \u2014 Curation Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.3.6/css/buttons.bootstrap5.min.css">
<style>
  body { font-size: 0.9rem; }
  .card-warning { border-left: 4px solid #fd7e14; }
  .card-danger  { border-left: 4px solid #dc3545; }
  .missing-list { max-height: 120px; overflow-y: auto; padding-left: 1rem; margin: 0; }
  .field-badge  { background: #eee; border-radius: 3px; padding: 1px 6px; margin-left: 6px; font-size: .85em; }
  .status-ok    { color: #198754; }
  .status-err   { color: #dc3545; font-weight: 600; }
  #miss-summary { columns: 3; list-style: none; padding: 0; }
  #miss-summary li { margin: 3px 0; cursor: pointer; }
  #miss-summary li:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="container-fluid py-3">

<h2 class="mb-1">SSHOC Marketplace \u2014 Curation Dashboard</h2>
<p class="text-muted mb-3">Generated: __GEN_DATE__ &nbsp;|&nbsp; Snapshot: __TS_STR__</p>

<div class="row g-3 mb-4">
  <div class="col-sm-6 col-md-3">
    <div class="card card-warning h-100 p-3">
      <div class="fs-2 fw-bold">__N_MD__</div>
      <div class="text-muted">Items with metadata issues</div>
    </div>
  </div>
  <div class="col-sm-6 col-md-3">
    <div class="card card-danger h-100 p-3">
      <div class="fs-2 fw-bold">__N_URL__</div>
      <div class="text-muted">Items with URL issues</div>
    </div>
  </div>
</div>

<ul class="nav nav-tabs mb-0" id="mainTabs" role="tablist">
  <li class="nav-item" role="presentation">
    <button class="nav-link active" id="tab-md-btn" data-bs-toggle="tab"
            data-bs-target="#tab-md" type="button">Metadata Issues (__N_MD__)</button>
  </li>
  <li class="nav-item" role="presentation">
    <button class="nav-link" id="tab-url-btn" data-bs-toggle="tab"
            data-bs-target="#tab-url" type="button">__URL_TAB_LABEL__</button>
  </li>
</ul>

<div class="tab-content border border-top-0 p-3">

  <!-- Metadata Issues tab -->
  <div class="tab-pane fade show active" id="tab-md" role="tabpanel">
    <h6 class="mt-2">Missing Fields Frequency
      <small class="text-muted fw-normal">(click a field to filter the table)</small></h6>
    <ul id="miss-summary" class="mb-3"></ul>

    <div class="row g-2 mb-2">
      <div class="col-auto">
        <select id="md-cat-filter" class="form-select form-select-sm">
          <option value="">All Categories</option>
        </select>
      </div>
      <div class="col-auto">
        <select id="md-src-filter" class="form-select form-select-sm">
          <option value="">All Sources</option>
        </select>
      </div>
      <div class="col-auto">
        <button id="md-clear-btn" class="btn btn-outline-secondary btn-sm">Clear</button>
      </div>
    </div>

    <table id="md-table" class="table table-sm table-striped" style="width:100%">
      <thead><tr>
        <th>ID</th><th>Label</th><th>Category</th>
        <th>Score</th><th>Missing</th><th>Missing Fields</th>
        <th>Source</th><th>Link</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <!-- URL Issues tab -->
  <div class="tab-pane fade" id="tab-url" role="tabpanel">
    __URL_TAB_BODY__
  </div>

</div><!-- /tab-content -->
</div><!-- /container -->

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js"></script>

<script>
const mdData  = __MD_JSON__;
const urlData = __URL_JSON__;

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                   .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}
function escRe(s) {
  return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');
}

// Missing fields frequency summary
(function() {
  var counts = {};
  mdData.forEach(function(d) {
    (d.MissingFields || []).forEach(function(f) { counts[f] = (counts[f] || 0) + 1; });
  });
  var ul = document.getElementById('miss-summary');
  Object.entries(counts).sort(function(a,b){ return b[1] - a[1]; }).forEach(function(e) {
    var li = document.createElement('li');
    li.innerHTML = '<span>' + esc(e[0]) + '</span><span class="field-badge">' + e[1] + '</span>';
    li.title = 'Filter table by this field';
    li.onclick = function() {
      mdTable.column(5).search(escRe(e[0])).draw();
      document.getElementById('md-cat-filter').value = '';
      document.getElementById('md-src-filter').value = '';
    };
    ul.appendChild(li);
  });
})();

// Metadata DataTable
const mdTable = $('#md-table').DataTable({
  data: mdData,
  columns: [
    { data:'ID' },
    { data:'label' },
    { data:'category' },
    { data:'score', render: function(d,t){ return t === 'display' ? Number(d||0).toFixed(1) : d; } },
    { data:'Missing' },
    { data:'MissingFields', orderable:false, searchable:true,
      render: function(d) {
        if (!Array.isArray(d) || !d.length) return '<em>\u2014</em>';
        return '<ul class="missing-list">' + d.map(function(f){ return '<li>'+esc(f)+'</li>'; }).join('') + '</ul>';
      }
    },
    { data:'Source' },
    { data:'url', render: function(d){ return d ? '<a href="'+esc(d)+'" target="_blank" rel="noopener">&#8599;</a>' : ''; } }
  ],
  dom: "<'row'<'col-sm-6'B><'col-sm-6'f>>rtip",
  buttons: ['csv','excel'],
  pageLength: 50,
  order: [[3,'asc']],
  columnDefs: [
    {targets:[0,3,4,7], width:'7%'},
    {targets:[1],       width:'22%'},
    {targets:[2,6],     width:'11%'},
    {targets:[5],       width:'28%'}
  ]
});

[...new Set(mdData.map(function(d){return d.category;}).filter(Boolean))].sort().forEach(function(v){
  $('#md-cat-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});
[...new Set(mdData.map(function(d){return d.Source;}).filter(Boolean))].sort().forEach(function(v){
  $('#md-src-filter').append('<option value="'+esc(v)+'">'+esc(v)+'</option>');
});

$('#md-cat-filter').on('change', function(){
  mdTable.column(2).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#md-src-filter').on('change', function(){
  mdTable.column(6).search(this.value ? '^'+escRe(this.value)+'$' : '', true, false).draw();
});
$('#md-clear-btn').on('click', function(){
  mdTable.search('').columns().search('').draw();
  $('#md-cat-filter,#md-src-filter').val('');
});
$('#tab-md-btn').on('shown.bs.tab', function(){ mdTable.columns.adjust(); });

__URL_TAB_JS__
</script>
</body>
</html>
"""

html = (HTML
    .replace("__GEN_DATE__",      gen_date)
    .replace("__TS_STR__",        ts_str)
    .replace("__N_MD__",          str(n_md))
    .replace("__N_URL__",         n_url_display)
    .replace("__URL_TAB_LABEL__", url_tab_label)
    .replace("__URL_TAB_BODY__",  url_tab_body)
    .replace("__MD_JSON__",       md_json)
    .replace("__URL_JSON__",      url_json)
    .replace("__URL_TAB_JS__",    url_tab_js))

out_path = OUT / f"curation_dashboard.html"
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write(html)

print(f"Wrote curation dashboard to: {out_path}")
