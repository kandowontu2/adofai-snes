"""Re-read a selected installed catalog and restore all native import layers.

Usage: python tools/reimport_catalog.py --pack build/packs/phantigma-master
       --include 298 299 ... --report build/reimport/report.json
Downloaded charts and original game assets stay in assets/private.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--include',type=int,nargs='*',default=[])
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args()
    private=ROOT/'assets/private';ids=list(dict.fromkeys(json.loads((args.pack/'pack.json').read_text())['levels']+args.include))
    backup=args.report.parent/'import-input-before';backup.mkdir(parents=True,exist_ok=True)
    for n in ids:
        if not (backup/f'level{n}.json').exists():shutil.copyfile(private/f'level{n}.json',backup/f'level{n}.json')
    before={n:json.loads((backup/f'level{n}.json').read_text()) for n in ids}
    if args.report_only:
        write_report(ids,before,private,args.report)
        return
    def run(name,*options):
        subprocess.run([sys.executable,str(ROOT/'tools'/name),*map(str,options)],cwd=ROOT,check=True)
    run('import_campaign.py')
    run('import_official.py')
    from neo_catalog import NEO
    neo_ids=[m['id'] for m in NEO if m['id'] in ids]
    if neo_ids:run('import_neo.py','--levels',*neo_ids)
    from import_featured import import_chart,DEFAULT_GAME
    folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950'
    metadata={}
    for name in ('tech','featured','community','firestix','joke','yangsy','main_ex','triple_planet'):
        for entry in json.loads((ROOT/'tools'/f'{name}_catalog.json').read_text()):metadata[entry['id']]=entry
    soundpath=private/'hitsound-levels.json';sounds=json.loads(soundpath.read_text())
    retained=('community','featured_classic','featured_wave','firestix','triple_planet',
              'live_planet_proxies','local_decoration_pivots','perfect_only_tag',
              'decoration_hitboxes_all_regions')
    for n in ids:
        old=before[n]
        if n in neo_ids or not Path(old.get('source','')).is_file():continue
        meta=dict(metadata.get(n,{}))
        for key in ('id','code','title','artist','author'):
            if key not in meta:meta[key]=old.get(key,'' if key in ('artist','author') else n)
        meta['source']=old['source']
        if n in range(40,62):meta['set']='featured_tech'
        if old.get('neo_cosmos'):meta['neo_cosmos']=True
        data,sound=import_chart(meta,folder,private)
        for key in retained:
            if key in old:data[key]=old[key]
        (private/f'level{n}.json').write_text(json.dumps(data,indent=2))
        sounds[str(n)]=sound;soundpath.write_text(json.dumps(sounds,indent=2))
        print('REIMPORTED',n,meta['code'],len(data['floors'])-1,flush=True)
    # JSON imports and Unity scenes use different native camera/layout data.
    # Restore every scene-derived layer after importing the musical floors.
    for name in ('import_native_layout.py','import_stick_to_floors.py','import_visibility.py',
                 'import_colors.py','import_camera.py','import_conditionals.py','import_hitsounds.py'):
        run(name)
    write_report(ids,before,private,args.report)


def write_report(ids,before,private,target):
    from official_catalog import WORLDS,source_chart_json
    from import_tech import TECH
    from import_conditionals import KINDS
    official={m['id']:m for m in WORLDS+TECH}
    rows=[]
    for n in ids:
        old=before[n];new=json.loads((private/f'level{n}.json').read_text())
        if n in official:
            raw=source_chart_json(official[n],new)
            if raw is not None:
                expected=[a for a in raw.get('actions',[]) if a['eventType'] in KINDS]
                assert new.get('track_actions',[])==expected,(n,'Imported track events differ from the verified chart source')
        rows.append(dict(id=n,code=new.get('code',old.get('code',f'{n}-X')),before_floors=len(old['floors']),floors=len(new['floors']),
                         source=new.get('source'),source_sha256=new.get('source_sha256'),
                         decorations=len(new.get('featured_decorations',[])),
                         checkpoints=len(new.get('checkpoints',[]))))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(levels=ids,results=rows),indent=2))
    print('REIMPORT COMPLETE',len(ids),'charts',flush=True)


if __name__=='__main__':main()
