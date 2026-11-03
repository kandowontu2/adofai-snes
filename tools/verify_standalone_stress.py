"""Exercise ROM-bank audio/animation concurrency and long-clock rollover."""
import concurrent.futures,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    catalog=json.loads((ROOT/'build/standalone-catalog.json').read_text());env=os.environ.copy()
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[k]='1'
    def run(case):
        n,speed=case;rom=next(r for r in catalog['roms'] if n in r['levels']);pack=rom['key'];local=rom['levels'].index(n)+1
        base=ROOT/'build/packs'/pack;out=base/f'verification/speed{round(speed*10):02d}-{local}'
        with (ROOT/f'build/standalone-stress-{n}.log').open('w') as log:
            subprocess.run([sys.executable,str(ROOT/'tools/emulate_campaign.py'),'--pack',pack,'--level',str(local),'--mode','perfect','--speed',str(speed),'--time-attack','--audio','--music-only','--out',str(out)],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
            subprocess.run([sys.executable,str(ROOT/'tools/check_campaign_audio.py'),str(out)],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
        r=json.loads((out/'result.json').read_text());a=json.loads((out/'audio-check.json').read_text());end=r['final']
        assert end['state']==3 and end['misses']==end['tap_overruns']==end['pattern_vblank_overruns']==0
        assert end['msu_present']==end['msu_pcm']==0
        if speed==.5:
            ticks=[s['nmi_audio_ticks'] for s in r['transitions'] if s['music_active']]
            assert any(b-a<-32768 for a,b in zip(ticks,ticks[1:]))
        row=dict(id=n,pack=pack,rom_sha256=r['rom_sha256'],speed=speed,combo=end['combo'],minimum_correlation=min(w['correlation'] for w in a['windows']),drift_ms=a['drift_ms'])
        print(json.dumps(row),flush=True);return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,[(60,2.),(61,2.),(35,.5)]))
    (ROOT/'build/standalone-stress.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2))


if __name__=='__main__':main()
