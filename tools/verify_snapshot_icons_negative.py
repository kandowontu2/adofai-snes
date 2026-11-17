"""Prove the chart-derived icon oracle rejects an incorrect worker glyph."""
import argparse,json,os,struct,subprocess,sys
from pathlib import Path
from verification_data import identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack
    frozen=identity(base/'adofai.sfc')
    control=base.with_name(base.name+'-icon-negative');control.mkdir(exist_ok=True)
    for source in base.iterdir():
        if not source.is_file() or source.suffix=='.pcm':continue
        destination=control/source.name
        if destination.exists():destination.unlink()
        os.link(source,destination)
    rom=bytearray((base/'adofai.sfc').read_bytes())
    # LDA #$3422 in the worker: blue snail -> blue rabbit. Everything
    # else, including the chart and the independent oracle, stays intact.
    begin,end=0x8000,0xF000;needle=bytes.fromhex('a9 22 34')
    hits=[i for i in range(begin,end-2) if rom[i:i+3]==needle]
    assert len(hits)==1,hits
    rom[hits[0]+1]=32
    rom[0x7FDC:0x7FE0]=bytes(4);checksum=(sum(rom)+0x1FE)&65535
    struct.pack_into('<HH',rom,0x7FDC,checksum^65535,checksum)
    (control/'adofai.sfc').unlink();(control/'adofai.sfc').write_bytes(rom)
    ids=json.loads((base/'pack.json').read_text())['levels'];local=ids.index(285)+1
    r=subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',control.name,
                      '--levels',str(local),'--autoplay','--sampled-graphics'],
                     capture_output=True,text=True)
    folder=control/f'verification/mesen-{local}-autoplay'
    text=(folder/'result.txt').read_text()
    assert r.returncode!=0 and 'Snapshot icon byte' in text and text.endswith('FAIL\n'),text
    assert identity(base/'adofai.sfc')==frozen
    result=dict(passed=True,**frozen,suite_digest=suite_digest(),
                negative_control_rejected=True,reason=text.splitlines()[0])
    (base/'verification/snapshot-icon-negative.json').write_text(json.dumps(result,indent=2))
    print('INCORRECT GLYPH REJECTED',result['reason'],flush=True)

if __name__=='__main__':main()
