"""Prove a twirl cannot silently corrupt the animation-stream cursor."""
import argparse,json,os,re,struct,subprocess,sys
from pathlib import Path
from verification_data import identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack;frozen=identity(base/'adofai.sfc')
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    physical=lambda a:(a>>16)*0x8000+(a&0x7fff)
    begin,end=map(physical,(labels['neo_far_twirl_orbit'],labels['neo_twirl_complete']))
    rom=bytearray((base/'adofai.sfc').read_bytes());changed=0
    # Recreate the former bad aliases in just the orbit helper. This
    # deliberate post-link fault bypasses the assembler's overlap guard.
    for i in range(begin,end-2):
        if rom[i] not in (0xAD,0xAE,0xCD,0x8D,0x8E,0x9C):continue
        address=struct.unpack_from('<H',rom,i+1)[0]
        if 0x07C8<=address<0x07DE and address%2==0:
            struct.pack_into('<H',rom,i+1,0x05A2+address-0x07C8);changed+=1
    assert changed>=12,changed
    rom[0x7FDC:0x7FE0]=bytes(4);checksum=(sum(rom)+0x1FE)&65535
    struct.pack_into('<HH',rom,0x7FDC,checksum^65535,checksum)
    control=base.with_name(base.name+'-twirl-memory-negative');control.mkdir(exist_ok=True)
    for source in base.iterdir():
        if not source.is_file() or source.suffix=='.pcm':continue
        destination=control/source.name
        if destination.exists():destination.unlink()
        os.link(source,destination)
    (control/'adofai.sfc').unlink();(control/'adofai.sfc').write_bytes(rom)
    ids=json.loads((base/'pack.json').read_text())['levels'];local=ids.index(256)+1
    r=subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',control.name,
                      '--levels',str(local),'--autoplay','--sampled-graphics'],capture_output=True,text=True)
    text=(control/f'verification/mesen-{local}-autoplay/result.txt').read_text()
    assert r.returncode!=0 and 'Twirl overwrote animation stream state' in text and text.endswith('FAIL\n'),text
    assert identity(base/'adofai.sfc')==frozen
    (base/'verification/twirl-memory-negative.json').write_text(json.dumps(dict(passed=True,**frozen,
        suite_digest=suite_digest(),negative_control_rejected=True,reason=text.splitlines()[0]),indent=2))
    print('STREAM CURSOR CORRUPTION REJECTED',text.splitlines()[0],flush=True)

if __name__=='__main__':main()
