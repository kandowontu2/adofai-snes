"""Refresh icon-only chart flags without rerasterizing unchanged geometry."""
import json
from pathlib import Path
from campaign_assets import compile_chart
from official_catalog import PACKS
ROOT=Path(__file__).resolve().parents[1]

def main():
    for pack,meta in PACKS.items():
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        locations=json.loads((base/'placements.json').read_text())
        image=bytearray(0x800000);image[:0x408000]=(base/'payload0.bin').read_bytes();image[0x410000:]=(base/'payload1.bin').read_bytes()
        hidden=0
        for n in meta['levels']:
            data=json.loads((ROOT/f'assets/private/level{n}.json').read_text(encoding='utf-8'))
            fresh,blob=compile_chart(data);count=len(fresh['notes'])
            old=(base/f'chart{n}.bin').read_bytes()
            assert old[:7*count]==blob[:7*count] and old[8*count:]==blob[8*count:]
            assert all((a&127)==(b&127) for a,b in zip(old[7*count:8*count],blob[7*count:8*count]))
            chart=json.loads((base/f'level{n}.json').read_text())
            for before,after in zip(chart['notes'],fresh['notes']):before['flags']=after['flags']
            chart['hidden_icons']=sum(bool(note['flags']&128) for note in chart['notes']);hidden+=chart['hidden_icons']
            (base/f'level{n}.json').write_text(json.dumps(chart,indent=2))
            address=locations[f'chart{n}'];offset=address-0xC00000 if address>=0xC00000 else address+0x400000 if 0x3E8000<=address<0x400000 else address
            image[offset:offset+len(blob)]=blob;(base/f'chart{n}.bin').write_bytes(blob)
        (base/'payload0.bin').write_bytes(image[:0x408000]);(base/'payload1.bin').write_bytes(image[0x410000:])
        print(pack,hidden,'hidden tile icons; chart timing and physics bytes unchanged',flush=True)

if __name__=='__main__':main()
