"""Two different real-controller grid paths must return to the same exit."""
import argparse,json,os,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',type=Path,required=True);ap.add_argument('--level',type=int,default=1)
    args=ap.parse_args();pack=args.pack.resolve()
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    level=json.loads((pack/'pack.json').read_text())['levels'][args.level-1]
    chart=json.loads((pack/f'level{level}.json').read_text());r=chart['freeroam_regions'][0];note=chart['notes'][r['step']]
    template=(pack/f'verification/mesen-{args.level}/config.lua').read_text()
    old=re.search(r'neo_events=\{(.*?)\}(?=,\w+=|\}\s*$)',template).group(1)
    original=[list(map(int,row.split(','))) for row in re.findall(r'\{([^}]+)\}',old)]
    from neo_freeroam import demo_route
    for case,reverse in [('forward-objectives',False),('reverse-objectives',True)]:
        events=[row for row in original if row[0]<=r['start']]
        key=events[-1][1];at=r['start'];angle=note['angle'];x=y=0;path=[]
        rate=note['rate']/256;sign=1 if rate>0 else -1
        for at,x,y,angle in demo_route(r,note,reverse):
            key=3-key
            assert at<r['return_start']
            events.append([at,key,r['step']])
            path.append([x,y])
        events.append([at+3,0,r['step']])
        events += [row for row in original if row[0]>=r['end']]
        out=pack/'verification'/('neo-free-'+case);out.mkdir(parents=True,exist_ok=True)
        config=re.sub(r'neo_events=\{.*?\}(?=,\w+=|\}\s*$)', 'neo_events={'+','.join('{'+','.join(map(str,e))+'}' for e in events)+'}',template)
        config=re.sub(r'out="[^"]+"','out='+json.dumps(out.as_posix()),config)
        config='local C='+config.removeprefix('return ').rstrip()+'\n'
        config+='C.palette_script=nil; C.graphics_dumps=false; C.arc=nil; C.objects=nil\n'
        config+=f'C.frames={r["end"]+1200}\nC.capture_steps={{{r["step"]}}}\n'
        config+='C.neo_grid={step='+str(r['step'])+',path={'+','.join('{'+','.join(map(str,p))+'}' for p in path)+'},'+','.join(f'{k}={labels[v]}' for k,v in [('hops','neo_free_hops'),('x','neo_free_x'),('y','neo_free_y')])+'}\nreturn C\n'
        cfg=out/'config.lua';cfg.write_text(config)
        result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=120',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],env=dict(os.environ,ADOFAI_TEST_CONFIG=str(cfg)),capture_output=True,text=True,timeout=140,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=(out/'result.txt').read_text() if (out/'result.txt').exists() else result.stdout+result.stderr
        print(case,report,flush=True)
        assert result.returncode==0 and report.endswith('PASS\n')

def verify_failures(pack, level, region_index=0):
    """No objectives, an invalid landing, and idle laser exposure must fail."""
    level_id=json.loads((pack/'pack.json').read_text())['levels'][level-1]
    chart=json.loads((pack/f'level{level_id}.json').read_text());r=chart['freeroam_regions'][region_index]
    template=(pack/f'verification/mesen-{level}/config.lua').read_text()
    old=re.search(r'neo_events=\{(.*?)\}(?=,\w+=|\}\s*$)',template).group(1)
    original=[list(map(int,row.split(','))) for row in re.findall(r'\{([^}]+)\}',old)]
    cases=['idle-laser'] if r.get('laser') else ['missing-coins','outside-grid']
    for case in cases:
        events=[row for row in original if row[0]<=r['start']]
        if case=='outside-grid':
            n=chart['notes'][r['step']];rate=n['rate']/256;sign=1 if rate>0 else -1
            turn=((128-n['angle'])*sign)%256
            if turn<16:turn+=256
            events.append([round(r['start']+turn/abs(rate)),3-events[-1][1],r['step']])
        out=pack/'verification'/('neo-free-'+case);out.mkdir(parents=True,exist_ok=True)
        config=re.sub(r'neo_events=\{.*?\}(?=,\w+=|\}\s*$)','neo_events={'+','.join('{'+','.join(map(str,e))+'}' for e in events)+'}',template)
        config=re.sub(r'out="[^"]+"','out='+json.dumps(out.as_posix()),config)
        config='local C='+config.removeprefix('return ').rstrip()+'\n'
        config+=f'C.palette_script=nil; C.graphics_dumps=false; C.arc=nil; C.objects=nil; C.frames={r["end"]+800}; C.neo_failure_step={r["step"]}\nreturn C\n'
        cfg=out/'config.lua';cfg.write_text(config)
        result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=180',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],env=dict(os.environ,ADOFAI_TEST_CONFIG=str(cfg)),capture_output=True,text=True,timeout=200,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=(out/'result.txt').read_text()
        print(case,report,flush=True)
        assert result.returncode==0 and report.endswith('PASS\n')

if __name__=='__main__':main()
