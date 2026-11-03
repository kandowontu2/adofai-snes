"""Full real-controller and audio checks for every 0.1x playback setting."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='main');args=ap.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    base=ROOT/'build/campaign' if args.pack=='main' else ROOT/f'build/packs/{args.pack}'
    chart=json.loads((base/'level1.json').read_text())
    rows=[];out=ROOT/('build/speed-verification' if args.pack=='main' else f'build/{args.pack}-speed-verification');out.mkdir(exist_ok=True)
    for speed in range(5,21):
        folder=out/f'speed-{speed:02d}';log=out/f'speed-{speed:02d}.log'
        with log.open('w') as f:
            subprocess.run([sys.executable,str(ROOT/'tools/emulate_campaign.py'),'--pack',args.pack,'--mode','perfect',
                            '--speed',str(speed/10),'--time-attack','--audio','--music-only','--out',str(folder)],stdout=f,stderr=subprocess.STDOUT,check=True)
            subprocess.run([sys.executable,str(ROOT/'tools/check_campaign_audio.py'),str(folder)],stdout=f,stderr=subprocess.STDOUT,check=True)
        result=json.loads((folder/'result.json').read_text());audio=json.loads((folder/'audio-check.json').read_text())
        assert result['final']['state']==3 and result['final']['combo']==167 and result['final']['misses']==0
        assert sum(result['judgments'])==167
        assert result['score']==sum(c*w for c,w in zip(result['judgments'],[20,40,75,100,100,100,75,40,20,0,0]))
        expected=75.230/(result['speed_pitch']/1536)+(8/result['fps'] if chart.get('mode7') else 0)
        assert abs(result['finish_centis']/100-expected)<.15,(speed,result['finish_centis']/100,expected)
        rows.append(dict(speed=speed/10,rom_sha256=result['rom_sha256'],msu_sha256=result.get('msu_sha256'),pitch=result['speed_pitch'],
                         combo=167,misses=0,finish_seconds=result['finish_centis']/100,
                         minimum_correlation=min(x['correlation'] for x in audio['windows']),drift_ms=audio['drift_ms']))
        print(f'{speed/10:.1f}x PASS: full combo, score, timer, audio',flush=True)
    current=identity(base/'adofai.sfc')
    assert all(r['rom_sha256']==current['rom_sha256'] and r['msu_sha256']==current['msu_sha256'] for r in rows)
    (out/'result.json').write_text(json.dumps(dict(**current,speeds=rows),indent=2))
if __name__=='__main__':main()
