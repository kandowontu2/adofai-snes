"""Real-ROM regression: neighboring ticks, independent expiry, latest arrow."""
import argparse, ctypes as C, json, struct
from pathlib import Path
from emulate import Emulator
from input_helpers import select_level, press, wait


def verify(rom):
    em=Emulator(rom=rom)
    out=rom.parent/'verification';out.mkdir(exist_ok=True)
    def put(name,value):C.c_uint16.from_address(em.ram+em.labels[name]).value=value&65535
    def marks(entries,uniform=False):
        now=em.read('tick')
        data=b''.join(struct.pack('<HH',pos,(now-age)&65535) for pos,age in entries)
        C.memmove(em.cache_ram+0x1000,data,len(data))
        put('meter_head',len(data));put('meter_count',len(entries))
        put('meter_average',entries[-1][0]);put('meter_uniform',entries[0][0] if uniform else 65535);put('meter_dirty',1)
        em.run();em.run()
    def pixel(pos):
        # Check the actual PPU glyph, not just the CPU's staging bitmap.
        video=em.core.retro_get_memory_data(3)
        row=C.string_at(video+0xA800+(pos//8)*16+2,2)
        bit=7-pos%8
        return ((row[0]>>bit)&1)|(((row[1]>>bit)&1)<<1)
    try:
        for _ in range(120):em.run()
        font=(rom.parent/'font.bin').read_bytes()
        expected=bytes(v for i in range(0,len(font),2) for v in [font[i]|font[i+1]]*2)
        video=em.core.retro_get_memory_data(3)
        assert C.string_at(video+0xA000,2048)==expected,'Static text must use full-bright ink'
        em.capture(out/'menu-text-brightness.png')
        select_level(em,1);press(em,1);press(em,3)
        wait(em,lambda:em.read('combo')>=3,1200)
        chart=json.loads((rom.parent/'level1.json').read_text())
        put('autoplay',0);manual_positions=[]
        for bias in (-2,1,-1,2,-2,1,-1,2):
            target=chart['notes'][em.read('step')+1]['frame']+em.read('speed_offset',True)+bias
            for _ in range(100):
                delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                current=em.read('elapsed')+delta*.004*em.av.timing.fps
                if current+1>=target:break
                em.run()
            head=em.read('meter_head');em.run([8])
            wait(em,lambda:em.read('meter_head')!=head,10)
            position=C.c_uint16.from_address(em.cache_ram+0x1000+head).value
            assert em.read('meter_average')==position
            manual_positions.append(position)
            em.run();em.run()
            arrow=C.c_uint16.from_address(em.ram+0x800+25*64+(7+position//8)*2).value
            assert arrow==0x3c10+(position&7),(position,hex(arrow))
        assert len(set(manual_positions))>=3,manual_positions
        put('autoplay',1)
        marks([(40,140),(41,80),(42,20)])
        assert [pixel(p) for p in (40,41,42)]==[1,2,3]
        assert em.read('meter_average')==42
        hud=C.c_uint16.from_address(em.ram+0x800+25*64+(7+42//8)*2).value
        assert hud==0x3c12,hex(hud)
        em.capture(out/'meter-neighboring-hits.png')
        from PIL import Image
        picture=Image.open(out/'meter-neighboring-hits.png').convert('RGB')
        brightness=[sum(picture.getpixel((56+p,193))) for p in (40,41,42)]
        assert brightness[0]<brightness[1]<brightness[2],brightness
        for _ in range(44):em.run()
        assert pixel(40)==0 and pixel(41)>0 and pixel(42)>0
        for _ in range(60):em.run()
        assert pixel(41)==0 and pixel(42)>0
        for _ in range(60):em.run()
        assert pixel(42)==0
        marks([(40,80)],uniform=True)
        assert pixel(40)==2
        marks([(40,0)],uniform=True)
        assert pixel(40)==3,'A new coincident hit must brighten a faded mark'
        marks([(p,0) for p in range(100)])
        assert em.read('meter_count')>=100
        assert all(pixel(p)==3 for p in range(100))
        result=dict(passed=True,neighboring_ticks=True,independent_expiry=True,
                    simultaneous_markers=100,latest_arrow=True,manual_positions=manual_positions,
                    fade_brightness=brightness,**em.evidence())
        (out/'hit-meter.json').write_text(json.dumps(result,indent=2));print(result)
    finally:em.close()


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True)
    verify(ap.parse_args().rom.resolve())
