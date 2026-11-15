"""Regenerate full-master PCM files from the retained compiled charts."""
import concurrent.futures,json
from pathlib import Path
from msu_assets import generate_pcm_tracks
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/stock-refresh-master'
OUT=ROOT/'dist/adofai-msu-master'

def generate(n):
    chart=json.loads((BASE/f'level{n}.json').read_text())
    tracks=generate_pcm_tracks(OUT,chart)
    print('PCM',n,len(tracks),flush=True)
    return dict(id=n,tracks=tracks)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    ids=json.loads((BASE/'pack.json').read_text())['levels']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(generate,ids))
    (OUT/'pcm-manifest.json').write_text(json.dumps(rows,indent=2))
    print('PCM COMPLETE',len(rows),flush=True)
