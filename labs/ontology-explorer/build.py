#!/usr/bin/env python3
"""Ontology Explorer.

Reads the use case ontology and generates a single, self-contained HTML page
that lets you click a class and see its properties, related classes, and
instances (data sources, entities, risk tiers, buckets).

Usage:
    python3 build.py
    python3 build.py --ontology ../../ontology/use_case_ontology.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_ONTOLOGY = ROOT.parent.parent / "ontology" / "use_case_ontology.json"
DEFAULT_OUT = ROOT / "index.html"


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<style>
:root { --navy:#0F1E46; --ice:#CADCFC; --teal:#0E8A7D; --amber:#F2A900; --paper:#f7f9fc; --ink:#111827; --muted:#6b7280; --line:#e5e7eb; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--paper); color:var(--ink); }
header.top { background:var(--navy); color:#fff; padding:26px 32px; }
header.top h1 { margin:0 0 6px; font-size:24px; letter-spacing:.2px; }
header.top p { margin:0; color:var(--ice); font-size:13.5px; }
.layout { display:grid; grid-template-columns:230px 1fr 440px; gap:18px; padding:22px 32px 40px; align-items:start; }
.panel { background:#fff; border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
.panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.8px; color:var(--navy); margin:0 0 12px; }
.classbtn { display:flex; flex-direction:column; align-items:flex-start; width:100%; text-align:left; background:#fff; border:1px solid var(--line); border-radius:9px; padding:9px 12px; margin-bottom:8px; cursor:pointer; }
.classbtn span { font-size:13px; font-weight:600; color:var(--navy); }
.classbtn small { font-size:10.5px; color:var(--muted); }
.classbtn:hover { border-color:var(--teal); }
.classbtn.active { background:var(--navy); border-color:var(--navy); }
.classbtn.active span, .classbtn.active small { color:#fff; }
.detail h2 { font-size:20px; margin:0 0 2px; color:var(--navy); }
.detail .id { font-size:11px; color:var(--muted); margin:0 0 10px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.detail .desc { font-size:13.5px; line-height:1.5; margin:0 0 14px; }
.detail h3 { font-size:11px; text-transform:uppercase; letter-spacing:.7px; color:var(--teal); margin:16px 0 8px; }
.detail table { width:100%; border-collapse:collapse; font-size:12.5px; }
.detail th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.5px; color:var(--muted); border-bottom:1px solid var(--line); padding:6px 8px; }
.detail td { border-bottom:1px solid #f1f5f9; padding:6px 8px; vertical-align:top; }
.detail code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px; color:var(--navy); }
.detail ul { margin:0; padding-left:18px; font-size:12.5px; line-height:1.6; }
.diagram { text-align:center; }
svg { width:100%; height:auto; }
.note { color:var(--muted); font-size:11.5px; margin-top:10px; }
@media (max-width:1050px) { .layout { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header class="top">
  <h1>@@TITLE@@</h1>
  <p>Click a class to see its properties, related classes, and instances.</p>
</header>
<div class="layout">
  <section class="panel"><h2>Classes</h2><div id="classes"></div></section>
  <section class="panel detail"><div id="detail"></div></section>
  <section class="panel diagram"><h2>Relationships</h2><svg id="diagram" viewBox="0 0 420 380"></svg><p class="note">Arrows point from a property's domain to its range.</p></section>
</div>
<script>
const O = @@ONTOLOGY@@;
const classesEl = document.getElementById('classes');
const detailEl = document.getElementById('detail');
const svgEl = document.getElementById('diagram');
let selected = (O.classes && O.classes[0]) ? O.classes[0].id : '';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function classById(id) { return (O.classes || []).find(c => c.id === id) || { id: id, label: id, description: '' }; }

function neighbors(id) {
  const out = [];
  (O.properties || []).forEach(p => {
    if (p.domain === id) out.push({ id: p.range, rel: p.id, dir: 'out' });
    if (p.range === id) out.push({ id: p.domain, rel: p.id, dir: 'in' });
  });
  return out;
}

function nodeBox(x, y, id, center) {
  const c = classById(id);
  const w = center ? 140 : 112, h = 30;
  const fill = center ? '#0F1E46' : '#ffffff';
  const stroke = center ? '#0F1E46' : '#0E8A7D';
  const color = center ? '#ffffff' : '#0F1E46';
  return `<g><rect x="${x - w/2}" y="${y - h/2}" width="${w}" height="${h}" rx="7" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/><text x="${x}" y="${y + 4}" text-anchor="middle" font-size="10.5" fill="${color}" font-weight="600">${esc(c.label || id)}</text></g>`;
}

function renderClasses() {
  classesEl.innerHTML = (O.classes || []).map(c =>
    `<button class="classbtn ${c.id === selected ? 'active' : ''}" data-id="${esc(c.id)}"><span>${esc(c.label)}</span><small>${esc(c.id)}</small></button>`
  ).join('');
  classesEl.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    selected = b.dataset.id; renderClasses(); renderDetail(); renderDiagram();
  }));
}

function renderDetail() {
  const c = classById(selected);
  let html = `<h2>${esc(c.label)}</h2><p class="id">${esc(c.id)}</p><p class="desc">${esc(c.description || '')}</p>`;
  const props = (O.properties || []).filter(p => p.domain === c.id || p.range === c.id);
  if (props.length) {
    html += `<h3>Properties</h3><table><tr><th>Property</th><th>Domain</th><th>Range</th></tr>` +
      props.map(p => `<tr><td><code>${esc(p.id)}</code></td><td>${esc(p.domain)}</td><td>${esc(p.range)}</td></tr>`).join('') + `</table>`;
  }
  if (c.id === 'DataSource') {
    html += `<h3>Instances and entities</h3><table><tr><th>Source</th><th>Provides</th></tr>` +
      (O.approved_data_sources || []).map(s => `<tr><td>${esc(s)}</td><td>${((O.data_source_entities || {})[s] || []).map(esc).join(', ') || '<span style="color:#9ca3af">(none)</span>'}</td></tr>`).join('') + `</table>`;
  }
  if (c.id === 'Entity') {
    const sources = Object.entries(O.data_source_entities || {});
    html += `<h3>Entities and sources</h3><table><tr><th>Entity</th><th>Provided by</th></tr>` +
      (O.entities || []).map(e => {
        const by = sources.filter(([s, es]) => es.includes(e)).map(([s]) => s);
        return `<tr><td>${esc(e)}</td><td>${by.map(esc).join(', ') || '<span style="color:#9ca3af">(none)</span>'}</td></tr>`;
      }).join('') + `</table>`;
  }
  if (c.id === 'AIUseCase') {
    html += `<h3>Governance gates</h3><ul>` + Object.entries(O.governance_gates || {}).map(([k, v]) => `<li><b>${esc(k)}</b>: ${v.map(esc).join(', ')}</li>`).join('') + `</ul>`;
    html += `<h3>Risk tiers</h3><ul>` + Object.entries(O.risk_tiers || {}).map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(v)}</li>`).join('') + `</ul>`;
  }
  if (c.id === 'RiskTier') {
    html += `<h3>Tiers</h3><ul>` + Object.entries(O.risk_tiers || {}).map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(v)}</li>`).join('') + `</ul>`;
  }
  if (c.id === 'Bucket') {
    html += `<h3>Buckets</h3><ul>` + (O.buckets || []).map(b => `<li>${esc(b)}</li>`).join('') + `</ul>`;
  }
  if (c.id === 'Control') {
    html += `<h3>Controls in the gates</h3><ul>` + Object.entries(O.governance_gates || {}).map(([k, v]) => `<li><b>${esc(k)}</b>: ${v.map(esc).join(', ')}</li>`).join('') + `</ul>`;
  }
  detailEl.innerHTML = html;
}

function renderDiagram() {
  const rel = neighbors(selected).slice(0, 8);
  const cx = 210, cy = 190, r = 135;
  let svg = `<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#94a3b8"/></marker></defs>`;
  rel.forEach((n, i) => {
    const a = (2 * Math.PI * i / Math.max(1, rel.length)) - Math.PI / 2;
    const x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
    const x1 = n.dir === 'out' ? cx : x, y1 = n.dir === 'out' ? cy : y;
    const x2 = n.dir === 'out' ? x : cx, y2 = n.dir === 'out' ? y : cy;
    svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#cbd5e1" stroke-width="1.5" marker-end="url(#arrow)"/>`;
    const mx = (cx + x) / 2, my = (cy + y) / 2;
    svg += `<text x="${mx}" y="${my - 4}" text-anchor="middle" font-size="8.5" fill="#64748b">${esc(n.rel)}</text>`;
    svg += nodeBox(x, y, n.id, false);
  });
  svg += nodeBox(cx, cy, selected, true);
  svgEl.innerHTML = svg;
}

renderClasses();
renderDetail();
renderDiagram();
</script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an interactive ontology explorer.")
    parser.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    path = Path(args.ontology)
    data = json.loads(path.read_text(encoding="utf-8"))
    html = TEMPLATE.replace("@@ONTOLOGY@@", json.dumps(data, ensure_ascii=False)).replace(
        "@@TITLE@@", data.get("name", "Ontology Explorer")
    )
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"Ontology Explorer written to {out}")
    print(f"  classes: {len(data.get('classes', []))}")
    print(f"  properties: {len(data.get('properties', []))}")
    print(f"  entities: {len(data.get('entities', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
