"""Compare recorded MesenCE symbol profiles and actual essential OAM."""
import argparse,json,struct
from pathlib import Path
from verification_data import identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]

def icons(path):
    data=path.read_bytes();assert len(data)%548==0
    result={}
    for at in range(0,len(data),548):
        time,count=struct.unpack_from('<HH',data,at);oam=data[at+4:at+548]
        sprites=[]
        for offset in range(0,count,4):
            _,_,tile,attr=oam[offset:offset+4]
            size=(oam[512+offset//16]>>(2*((offset//4)%4)+1))&1
            if size and 32<=tile<112 and 0x32<=attr<=0x36:
                sprites.append(tuple(oam[offset:offset+4]))
        result[time]=sprites
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack;frozen=identity(base/'adofai.sfc')
    results=[]
    scaled='SYMBOL_SCALE_BUILD = 1' in (base/'addresses.inc').read_text()
    for n in (285,286):
        before=base/f'verification/symbols-{n}-before'
        after=base/f'verification/symbols-{n}-final'
        assert json.loads((after/'identity.json').read_text())==frozen
        old=json.loads((before/'timing.json').read_text());new=json.loads((after/'timing.json').read_text())
        a,b=icons(before/'oam.bin'),icons(after/'oam.bin');common=sorted(a.keys()&b.keys())
        assert len(common)>=30,(n,'Insufficient shared timestamps',len(common))
        if scaled:
            ids=json.loads((base/'pack.json').read_text())['levels']
            replay=base/f'verification/mesen-{ids.index(n)+1}-autoplay'
            manifest=json.loads((replay/'manifest.json').read_text())
            assert manifest['passed'] and manifest['suite_digest']==suite_digest()
            assert all(manifest[k]==v for k,v in frozen.items())
            assert int((replay/'snapshot-icon-jobs.txt').read_text())>=100
            assert (replay/'symbol-scale-pixels.txt').read_text().startswith('PASS checks=')
            # Resizing intentionally changes OAM tiles/positions/counts.
            # The independent per-floor oracle checks every emitted object;
            # compare timing here, rather than requiring unscaled artwork.
        else:
            for time in common:assert a[time]==b[time],(n,time,'Essential symbol output changed')
        assert new['max_gap']<=old['max_gap'],(n,old,new)
        assert (new['max_clocks']<=old['max_clocks'] if scaled else new['max_clocks']<old['max_clocks']),(n,old,new)
        results.append(dict(id=n,before=old,after=new,common_timestamps=len(common),
                            identical_timestamps=sum(a[t]==b[t] for t in common),scaled_pixel_oracle=scaled,
                            baseline_identity=json.loads((before/'identity.json').read_text())))
    assert (results[0]['after']['max_gap']<=results[0]['before']['max_gap'] if scaled else
            results[0]['after']['max_gap']<results[0]['before']['max_gap'])
    report=dict(passed=True,**frozen,results=results)
    (base/'verification/symbol-performance.json').write_text(json.dumps(report,indent=2))
    print('SYMBOL PERFORMANCE PASS',[(r['id'],r['identical_timestamps'],r['before']['max_gap'],r['after']['max_gap']) for r in results],flush=True)

if __name__=='__main__':main()
