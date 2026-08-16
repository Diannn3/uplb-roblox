#!/usr/bin/env python3
"""Network-opt-in OSM/Overture AOI comparison. Raw bulk data stays gitignored."""
import argparse, hashlib, json, subprocess, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; RAW=ROOT/'research/raw'; RESULTS=ROOT/'research/results'

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

BBOX=read_json(ROOT/'research/campus_bbox.json')
def sha256(p):
    h=hashlib.sha256();
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1048576),b''): h.update(c)
    return h.hexdigest()
def fetch_osm(out):
    s,w,n,e=BBOX['south'],BBOX['west'],BBOX['north'],BBOX['east']
    q='[out:json][timeout:180];(way["building"](%s,%s,%s,%s);relation["building"](%s,%s,%s,%s);way["highway"](%s,%s,%s,%s);way["waterway"](%s,%s,%s,%s););out center tags geom;' % ((s,w,n,e)*4)
    url='https://overpass-api.de/api/interpreter?'+urllib.parse.urlencode({'data':q})
    req=urllib.request.Request(url,headers={'User-Agent':'uplb-roblox-research/0.1'})
    with urllib.request.urlopen(req,timeout=240) as r: out.write_bytes(r.read())
def fetch_overture(out):
    w,s,e,n=BBOX['west'],BBOX['south'],BBOX['east'],BBOX['north']
    subprocess.run(['overturemaps','download',f'--bbox={w},{s},{e},{n}','-f','geojson','--type=building','-o',str(out)],check=True)
def summarize_osm(p):
    els=read_json(p).get('elements',[])
    return {'elements':len(els),'buildings':sum('building' in x.get('tags',{}) for x in els),'highways':sum('highway' in x.get('tags',{}) for x in els),'waterways':sum('waterway' in x.get('tags',{}) for x in els),'named':sum(bool(x.get('tags',{}).get('name')) for x in els)}
def summarize_ov(p):
    fs=read_json(p).get('features',[])
    return {'features':len(fs),'named':sum(bool((x.get('properties') or {}).get('names')) for x in fs),'with_height':sum((x.get('properties') or {}).get('height') is not None for x in fs),'with_floors':sum((x.get('properties') or {}).get('num_floors') is not None for x in fs)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--fetch',action='store_true'); a=ap.parse_args(); RAW.mkdir(exist_ok=True); RESULTS.mkdir(exist_ok=True)
    osm=RAW/'osm_uplb_aoi.json'; ov=RAW/'overture_buildings_uplb_aoi.geojson'
    if a.fetch: fetch_osm(osm); fetch_overture(ov)
    r={'bbox':{k:BBOX[k] for k in ('west','south','east','north')},'inputs':{},'summaries':{},'notes':[]}
    if osm.exists(): r['inputs']['osm']={'path':str(osm.relative_to(ROOT)),'sha256':sha256(osm)}; r['summaries']['osm']=summarize_osm(osm)
    else: r['notes'].append('OSM extract absent; run --fetch in a network-enabled environment.')
    if ov.exists(): r['inputs']['overture']={'path':str(ov.relative_to(ROOT)),'sha256':sha256(ov)}; r['summaries']['overture']=summarize_ov(ov)
    else: r['notes'].append('Overture extract absent; install official overturemaps CLI then run --fetch.')
    out=RESULTS/'osm_overture_comparison.json'; out.write_text(json.dumps(r,indent=2)+'\n', encoding='utf-8'); print(json.dumps(r,indent=2))
if __name__=='__main__': main()
