"""Check page arrows, song titles and cursor in published SNES menu pixels."""
import argparse,ctypes as C,json
from pathlib import Path
import numpy as np
from PIL import Image
from emulate import Emulator,ROOT
from input_helpers import press


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/campaign' if args.pack=='main' else ROOT/'build/packs'/args.pack
    pack=json.loads((base/'pack.json').read_text());count=len(pack['levels'])
    out=base/'verification/menu-pages';out.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=base/'adofai.sfc');rows=[]
    try:
        for _ in range(120):em.run()
        assert em.read('speed_tenths')==10 and em.read('speed_pitch')==1536,'Fresh boot must use 1.0x'
        for selected in range(count):
            assert em.read('selected_level')==selected
            first=selected//9*9
            for _ in range(3):em.run()
            hud=np.frombuffer(C.string_at(em.ram+0x800,2048),dtype='<u2').reshape(32,32)
            assert (int(hud[5,30])&255)==(1 if first else 0),(selected,'up')
            assert (int(hud[15,30])&255)==(2 if first+9<count else 0),(selected,'down')
            cursor=np.argwhere((hud[6:15,:]&255)==ord('>'))
            assert cursor.tolist()==[[selected%9,0]],(selected,cursor.tolist())
            for i,n in enumerate(pack['levels'][first:first+9]):
                chart=json.loads((base/f'level{n}.json').read_text())
                title=f'{chart["code"]} {chart["title"]}'[:28]
                actual=''.join(chr(int(x)&255) if x&255 else ' ' for x in hud[6+i,2:30]).rstrip()
                assert actual==title.rstrip(),(selected,actual,title)
            video=em.core.retro_get_memory_data(3)
            assert C.string_at(video+0xf000,2048)==hud.tobytes(),'HUD not published to PPU'
            if selected%9==0:
                em.capture(out/f'page-{first//9+1}.png')
                pixels=np.array(Image.open(out/f'page-{first//9+1}.png'))
                for row,visible in ((5,bool(first)),(15,first+9<count)):
                    bright=np.count_nonzero(np.all(pixels[row*8:row*8+8,240:248]>160,axis=2))
                    assert (bright>12)==visible,(selected,row,bright)
                rows.append(dict(first=first+1,up=bool(first),down=first+9<count))
            if selected+1<count:press(em,5)
        press(em,5);assert em.read('selected_level')==0
        press(em,4);assert em.read('selected_level')==count-1
        report=dict(**em.evidence(),pack=args.pack,songs=count,pages=rows,checked_published_pixels=True,wraps_both_directions=True,default_speed=1.)
        (out/'result.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report),flush=True)
    finally:em.close()


if __name__=='__main__':main()
