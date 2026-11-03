"""Exercise fast/normal music selection through the real menu, including switching back."""
import argparse,json,struct,ctypes as C
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import configure,press,wait

def verify(base):
    pack=json.loads((base/'pack.json').read_text());assert pack['fast_audio_rate']==8000
    descriptors=(base/'msu_descriptors.bin').read_bytes();em=Emulator(rom=base/'adofai.sfc');rows=[]
    try:
        for _ in range(120):em.run()
        for speed in (10,11,20,10,5,13,10):
            configure(em,speed);press(em,1);press(em,3)
            wait(em,lambda:em.read('state')==1 and em.read('music_active'),1800)
            address=C.c_uint32.from_address(em.ram+em.labels['msu_song_base']).value
            expected=struct.unpack_from('<I',descriptors,4 if speed>10 else 0)[0]
            assert address==expected,(speed,address,expected)
            logical=em.read('speed_pitch');actual=logical if speed<=10 else logical//3*2
            assert em.read('speed_stream')==actual*3
            rows.append(dict(speed=speed/10,music_address=address,music_rate=8000 if speed>10 else 12000))
            press(em,3);wait(em,lambda:em.read('state')==4)
            press(em,2);wait(em,lambda:em.read('state')==0)
        result=dict(passed=True,**em.evidence(),cases=rows)
        (base/'verification/adaptive-switching.json').write_text(json.dumps(result,indent=2));return result
    finally:em.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',required=True);a=p.parse_args();print(verify(ROOT/'build/packs'/a.pack))
