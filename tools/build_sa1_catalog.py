"""Build rotation assets per chart, then assemble an isolated SA-1 master.

Worker subprocesses write separate directories; the validated stock master
and its PCM files are never modified. PCM data is reused through hardlinks.
"""
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from track_camera import rotation_schedule
from animation_assets import generate
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'build/packs/master'

def copy_file(src,dst):
    if dst.exists():return
    if src.suffix=='.pcm':os.link(src,dst)
    else:shutil.copyfile(src,dst)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--out',type=Path,default=ROOT/'build/packs/sa1-release');ap.add_argument('--levels',nargs='+',type=int)
    ap.add_argument('--rebuild-tracks',action='store_true');ap.add_argument('--job-root',type=Path,default=ROOT/'build/sa1-rotation-jobs');args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    for p in SOURCE.iterdir():
        if p.is_file():copy_file(p,out/p.name)
    selected=args.levels or list(range(1,62));jobs=[]
    for n in selected:
        c=json.loads((SOURCE/f'level{n}.json').read_text());d=json.loads((ROOT/f'assets/private/level{n}.json').read_text())
        rotation_schedule(d,c)
        if args.rebuild_tracks or any((a,b)!=(256,0) for _,a,b in c['camera_rotation_versions']):jobs.append((n,c));continue
        generate(out,c,(out/f'timeline{n}.bin').read_bytes(),(out/f'patterns{n}.bin').read_bytes())
        (out/f'level{n}.json').write_text(json.dumps(c,indent=2))
    def work(item):
        n,c=item;job=args.job_root/str(n);job.mkdir(parents=True,exist_ok=True)
        stamp=job/'rotation-complete.json'
        digest=hashlib.sha256((ROOT/f'assets/private/level{n}.json').read_bytes())
        # Verification/reporting edits do not alter compiled charts. Track
        # compiler modules, build options and the imported source do.
        compiler_names={'campaign_assets.py','make_assets.py','presentation_assets.py','animation_assets.py','msu_assets.py','spc_campaign.py','hit_sound_assets.py','build_sa1_catalog.py'}
        paths=[p for p in (ROOT/'tools').glob('*.py') if p.name in compiler_names or p.name.startswith('track_')]
        for path in sorted(paths):digest.update(path.name.encode());digest.update(path.read_bytes())
        fingerprint=digest.hexdigest()
        if stamp.exists() and json.loads(stamp.read_text()).get('fingerprint')==fingerprint:return dict(level=n,passed=True,cached=True)
        # Audio/checkpoint PCM settings are unchanged by camera compilation.
        for p in SOURCE.iterdir():
            if p.is_file() and (p.name in (f'level{n}.brr',f'level{n}-audio.json',f'msu-{n}.json') or p.suffix=='.pcm' and (p.stem==f'adofai-{n}' or any(p.stem==f'adofai-{1000+n*32+i}' for i in range(len(c['checkpoints']))))):copy_file(p,job/p.name)
        command=[sys.executable,str(ROOT/'tools/campaign_assets.py'),'--pack','master','--out',str(job),'--levels',str(n),'--camera-rotation','--material-capacity',str(c.get('authored_material_capacity',48))]
        # R's sparse moving geometry supports 30-Hz authored motion without
        # exceeding the pattern budget; dense charts retain their cadence.
        if n==45:command+=['--motion-step','2']
        if c.get('shared_track_contour'):command.append('--shared-contours')
        with (job/'build.log').open('w') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        row=dict(level=n,passed=result.returncode==0,log=str(job/'build.log'),fingerprint=fingerprint)
        if row['passed']:stamp.write_text(json.dumps(row))
        return row
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(work,jobs):rows.append(row);print(json.dumps(row),flush=True)
    (out/'rotation-asset-results.json').write_text(json.dumps(rows,indent=2))
    if not all(r['passed'] for r in rows):raise RuntimeError('Rotation asset failures; see rotation-asset-results.json')
    for n,c in jobs:
        job=args.job_root/str(n)
        prefixes=(f'animation{n}-checkpoint-',)
        names={f'{prefix}{n}.bin' for prefix in ('chart','track_chr','track_map','timeline','patterns','animation','checkpoints','visibility_index')}
        names|={f'level{n}.json',f'level{n}.brr'}
        for p in job.iterdir():
            if p.is_file() and (p.name in names or p.name.startswith(prefixes)):shutil.copyfile(p,out/p.name)
    pack=json.loads((SOURCE/'pack.json').read_text())
    if args.levels:pack['levels']=selected
    (out/'pack.json').write_text(json.dumps(pack,indent=2))
    charts=[json.loads((out/f'level{n}.json').read_text()) for n in pack['levels']]
    (out/'manifest.json').write_text(json.dumps(charts,indent=2))
    import msu_assets
    msu_assets.generate(out,charts,{c['id']:(out/f'level{c["id"]}.brr').read_bytes() for c in charts})
    subprocess.run([sys.executable,str(ROOT/'tools/build_sa1.py'),'--out',str(out)],cwd=ROOT,check=True)
    print('SA-1 master built:',out,flush=True)

if __name__=='__main__':main()
