"""Build the official-world ExHiROM cartridge packs."""
import argparse
import os
import re
from pathlib import Path
import struct
import subprocess
import sys
from build import command

ROOT=Path(__file__).resolve().parent

def refresh_menu_font(out,sa1=False):
    """Refresh editable font art, including arrows and the timing meter."""
    import json
    placements=json.loads((out/'placements.json').read_text())
    cpu=placements['font'];offset=cpu-0xC00000 if cpu>=0xC00000 else cpu+0x400000 if 0x3E8000<=cpu<0x400000 else cpu
    variant='mode7' if 'MSU_BUILD = 1' in (out/'addresses.inc').read_text() else 'campaign'
    font=(ROOT/'assets/graphics'/variant/'font.chr').read_bytes()
    assert len(font)==2048
    path=out/('sa1_payload.bin' if sa1 else 'payload0.bin' if offset<0x408000 else 'payload1.bin')
    start=offset-0x10000 if sa1 else offset if offset<0x408000 else offset-0x410000
    data=bytearray(path.read_bytes());data[start:start+len(font)]=font;path.write_bytes(data)
    (out/'font.bin').write_bytes(font)
def main():
    os.chdir(ROOT)
    sys.path.insert(0,str(ROOT/'tools'))
    from official_catalog import PACKS
    ap=argparse.ArgumentParser();ap.add_argument('--assets-only',action='store_true');ap.add_argument('--skip-assets',action='store_true')
    ap.add_argument('--pack',choices=[*PACKS,'master']);ap.add_argument('--all',action='store_true');ap.add_argument('--out',type=Path);ap.add_argument('--levels',type=int,nargs='+');args=ap.parse_args()
    for pack in PACKS if args.all or args.pack is None else [args.pack]:
        out=args.out or (ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}')
        out.mkdir(parents=True,exist_ok=True)
        if not args.skip_assets:subprocess.run([sys.executable,'tools/campaign_assets.py','--pack',pack,'--out',str(out)]+(['--levels',*map(str,args.levels)] if args.levels else []),check=True)
        if args.assets_only:continue
        sa1='SA1_BUILD = 1' in (out/'addresses.inc').read_text()
        refresh_menu_font(out,sa1)
        if sa1:
            if not (out/'sa1_worker.bin').exists():(out/'sa1_worker.bin').write_bytes(bytes(0x8000))
        subprocess.run([command('ca65'),'--cpu','65816','-I','.', '-I',str(out),'--bin-include-dir',str(out),'-g','-o',str(out/'game.o'),'-l',str(out/'game.lst'),'src/campaign.s'],check=True)
        subprocess.run([command('ld65'),'-C',str(out/('sa1.cfg' if sa1 else 'exhirom.cfg')),'-o',str(out/'adofai.sfc'),'-m',str(out/'adofai.map'),'-Ln',str(out/'adofai.lbl'),str(out/'game.o')],check=True)
        dest=out/'adofai.sfc';rom=bytearray(dest.read_bytes());assert len(rom)==0x800000
        if not sa1:rom[0x8000:0x10000]=rom[0x408000:0x410000]
        if sa1 and 'SA1_FASTROM_MIRROR = 1' in (out/'addresses.inc').read_text():
            assert not any(rom[0x200000:0x208000]),'FastROM code mirror overlaps packed data'
            rom[0x200000:0x208000]=rom[:0x8000]
            if 'SA1_FASTROM_HELPERS = 1' in (out/'addresses.inc').read_text():
                code_size=re.search(r'NEO_CODE_BYTES = \$([0-9A-Fa-f]+)',(out/'addresses.inc').read_text())
                helper_end=0x10000+(int(code_size[1],16) if code_size else 0x2000)
                assert not any(rom[0x20f000:0x200000+helper_end]),'FastROM helpers overlap packed data'
                rom[0x20f000:0x200000+helper_end]=rom[0xf000:helper_end]
        header=0x7FDC if sa1 else 0x40FFDC
        rom[header:header+4]=bytes(4);checksum=(sum(rom)+0x1FE)&65535
        struct.pack_into('<HH',rom,header,checksum^65535,checksum);dest.write_bytes(rom)
        print('Built',dest,'(8 MiB '+('SA-1' if sa1 else 'ExHiROM')+'), checksum',hex(checksum),flush=True)
if __name__=='__main__':main()
