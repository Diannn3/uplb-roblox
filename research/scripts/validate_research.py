#!/usr/bin/env python3
from pathlib import Path
import json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
TEXT_ENCODING='utf-8'

def read_text(path: Path) -> str:
    return path.read_text(encoding=TEXT_ENCODING)

required=[
'docs/MASTER_PLAN.md','docs/RESEARCH_FINDINGS.md','docs/GEOSPATIAL_ARCHITECTURE.md','docs/DATA_GOVERNANCE_AND_LICENSING.md','docs/ASSET_PIPELINE.md','docs/ROBLOX_ARCHITECTURE.md','docs/AUTOMATION_AND_VALIDATION.md','docs/ADRS.md','docs/ROADMAP.md','research/sources.json','research/upstream_repositories.json','research/campus_bbox.json']
errors=[]; warnings=[]
for rel in required:
    if not (ROOT/rel).exists(): errors.append(f'missing {rel}')
# JSON parse
for p in list((ROOT/'research').rglob('*.json'))+list((ROOT/'research').rglob('*.geojson')):
    try: json.loads(read_text(p))
    except Exception as e: errors.append(f'bad json {p.relative_to(ROOT)}: {e}')
# Source register
try:
    reg=json.loads(read_text(ROOT/'research/sources.json'))
    for i,s in enumerate(reg['sources']):
        for k in ('id','provider','url','accessed','license','redistribution','status','intended_use'):
            if not s.get(k): errors.append(f'source[{i}] missing {k}')
except Exception: pass
# ADR count
adr=read_text(ROOT/'docs/ADRS.md')
found=set(re.findall(r'^## ADR-(\d{3})',adr,re.M))
expected={f'{i:03}' for i in range(1,14)}
if found!=expected: errors.append(f'ADR set mismatch: {sorted(found)}')
# 48 traceability entries
master=read_text(ROOT/'docs/MASTER_PLAN.md')
rows=set(int(x) for x in re.findall(r'^\|\s*(\d+)\s*\|',master,re.M) if 1<=int(x)<=48)
missing=sorted(set(range(1,49))-rows)
if missing: errors.append(f'missing traceability rows: {missing}')
# Internal Markdown relative links
for p in (ROOT/'docs').glob('*.md'):
    text=read_text(p)
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith(('http://','https://','#','mailto:')): continue
        target=target.split('#',1)[0]
        if not target: continue
        if not (p.parent/target).resolve().exists(): errors.append(f'broken relative link {p.name} -> {target}')
# tracked prohibited bulk/reference formats
tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
blocked_ext={'.laz','.las','.tif','.tiff','.geotiff','.e57','.ply','.glb','.gltf','.fbx','.blend1'}
for rel in tracked:
    if Path(rel).suffix.lower() in blocked_ext: errors.append(f'blocked bulk/generated format tracked: {rel}')
    low=rel.lower()
    if ('streetview' in low or 'street_view' in low) and Path(rel).suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
        errors.append(f'possible Google Street View image tracked: {rel}')
# Core phrases/gates
for phrase,file in [('Google Street View','docs/DATA_GOVERNANCE_AND_LICENSING.md'),('EPSG:32651','docs/GEOSPATIAL_ARCHITECTURE.md'),('StreamingEnabled','docs/ROBLOX_ARCHITECTURE.md'),('CODEX-AUTOMATABLE','docs/ROADMAP.md')]:
    if phrase not in read_text(ROOT/file): errors.append(f'{phrase} absent from {file}')
print(f'validated {len(required)} required paths, {len(found)} ADRs, {len(rows)} traceability rows, {len(tracked)} tracked files')
for w in warnings: print('WARNING:',w)
for e in errors: print('ERROR:',e)
if errors: sys.exit(1)
print('PASS: research package validation succeeded')
