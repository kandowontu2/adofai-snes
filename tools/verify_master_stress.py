"""Dense BRR-speed playback and the long SPC clock rollover in the master."""
import concurrent.futures,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'build/packs/master'

def main():
    env=os.environ.copy()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
    def run(case):
        n,speed,name=case;out=BASE/'verification'/name;log=ROOT/f'build/master-{name}.log'
        with log.open('w') as f:
            subprocess.run([sys.executable,str(ROOT/'tools/emulate_campaign.py'),'--pack','master','--level',str(n),'--mode','perfect',
                            '--speed',str(speed),'--time-attack','--audio','--music-only','--out',str(out)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            subprocess.run([sys.executable,str(ROOT/'tools/check_campaign_audio.py'),str(out)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        result=json.loads((out/'result.json').read_text());end=result['final']
        assert end['tap_overruns']==0 and end['pattern_vblank_overruns']==0,(name,end)
        if speed==.5:
            ticks=[r['nmi_audio_ticks'] for r in result['transitions'] if r['music_active']]
            assert any(b-a<-32768 for a,b in zip(ticks,ticks[1:])),'Long test did not exercise SPC timer rollover'
        print(name,'PASS',end['combo'],'hits, no misses, no input overrun, no VBlank overrun',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run,[(41,2.,'speed20-41'),(61,2.,'speed20-61'),(35,.5,'speed05-35'),
                           (53,2.,'speed20-53'),(60,2.,'speed20-60')]))

if __name__=='__main__':main()
