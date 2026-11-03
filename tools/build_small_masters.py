"""Prepare smaller master editions without changing the compatible ROM/data format."""
import argparse,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);args=ap.parse_args()
    source=args.source.resolve();levels=json.loads((source/'pack.json').read_text())['levels']
    for mode in ('hybrid','compressed'):
        target=ROOT/f'build/packs/sa1-renderer-{mode}'
        target.mkdir(parents=True,exist_ok=True)
        keep={f'adofai-{n}.pcm' for n in levels} if mode=='hybrid' else set()
        unexpected=[p for p in target.glob('*.pcm') if p.name not in keep]
        assert not unexpected,f'Use a fresh output folder: unexpected PCM files {unexpected}'
        for p in source.iterdir():
            if not p.is_file() or (p.suffix=='.pcm' and p.name not in keep):continue
            q=target/p.name
            if q.exists():raise FileExistsError(f'Output already exists: {q}')
            if p.suffix in ('.pcm','.msu'):os.link(p,q)
            else:shutil.copy2(p,q)
        (target/'edition.json').write_text(json.dumps(dict(edition=mode,full_song_pcm=mode=='hybrid',checkpoint_pcm=False,pcm_tracks=sorted(keep),source=str(source)),indent=2))
        total=sum((target/name).stat().st_size for name in ['adofai.sfc','adofai.msu',*keep])
        print(mode,total,'bytes',flush=True)

if __name__=='__main__':main()
