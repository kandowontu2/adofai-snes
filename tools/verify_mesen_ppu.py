"""Independently check Mesen's captured hardware map and visible tile pixels."""
import argparse,bisect,json,struct
from pathlib import Path
from verify_render import map_reader
ROOT=Path(__file__).resolve().parents[1]

def verify(base,level,folder):
    n=json.loads((base/'pack.json').read_text())['levels'][level-1]
    chart=json.loads((base/f'level{n}.json').read_text())
    timeline=(base/f'timeline{n}.bin').read_bytes();patterns=(base/f'patterns{n}.bin').read_bytes()
    tile=map_reader((base/f'track_map{n}.bin').read_bytes(),chart['map_height'],chart.get('map_offset_shift',0))
    nodes=[]
    for offset in chart['visibility_offsets'][:chart['visibility_cells']]:
        count=struct.unpack_from('<H',timeline,offset)[0]
        rows=[struct.unpack_from('<HH',timeline,offset+2+4*i) for i in range(count)]
        nodes.append(([t for t,v in rows],[v for t,v in rows]))
    versions=[([t for t,v in rows],[v for t,v in rows]) for rows in chart['pattern_versions']]
    samples=0;checked_pixels=0
    for path in sorted(folder.glob('ppu-*.bin')):
        blob=path.read_bytes();assert len(blob)==16+256+32768,path
        time,cx,cy,c,s,bx,by,step=struct.unpack_from('<H6hH',blob)
        mapping=blob[16:272];vram=blob[272:];pixels=vram[1::2]
        expected_rotation=next(((c,s) for f,c,s in reversed(chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[]))) if f<=time),(256,0))
        assert (c,s)==expected_rotation,(path,'rotation',time,(c,s),expected_rotation)
        indices=[vs[bisect.bisect_right(ts,time)-1] for ts,vs in versions]
        shift=next((v for f,v in reversed(chart.get('camera_raster_shift_versions',[])) if f<=time),0)
        center=chart.get('viewport_center_y',96);half=chart.get('viewport_bottom',160)-center
        cx=(cx+128)//(1<<shift);cy=(cy+center)//(1<<shift)
        ex=(128*abs(c)+half*abs(s)+255)//256;ey=(half*abs(c)+128*abs(s)+255)//256
        left,right,top,bottom=cx-ex,cx+ex-1,cy-ey,cy+ey-1
        for wy in range(top//8,bottom//8+1):
            for wx in range(left//8,right//8+1):
                value=tile(wx,wy)
                if value&0x2000:
                    ts,vs=nodes[(value&0x1fff)|((value&0xc000)>>1)]
                    at=bisect.bisect_right(ts,time)-1;value=vs[at] if at>=0 else 0
                address=(wy-by)*128+wx-bx
                assert 0<=address<16384,(path,'map address',address)
                physical=vram[address*2]
                # Duplicate resident patterns may use another physical slot.
                # Validate the pixels reached by the hardware map directly.
                expected=patterns[indices[value]*64:indices[value]*64+64]
                actual=pixels[physical*64:physical*64+64]
                x0,x1=max(0,left-wx*8),min(8,right-wx*8+1)
                y0,y1=max(0,top-wy*8),min(8,bottom-wy*8+1)
                for py in range(y0,y1):
                    assert actual[py*8+x0:py*8+x1]==expected[py*8+x0:py*8+x1],(path,'pattern',step,time,value,physical,wx,wy)
                    checked_pixels+=x1-x0
        samples+=1
    assert samples>0,folder
    from verification_data import identity
    evidence=identity(base/'adofai.sfc')
    manifest=json.loads((folder/'manifest.json').read_text())
    assert all(manifest.get(k)==v for k,v in evidence.items()),'Mesen capture belongs to another build'
    result=dict(passed=True,code=chart['code'],samples=samples,visible_pixels_checked=checked_pixels,**evidence)
    (folder/'ppu-verification.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--level',type=int,default=1);ap.add_argument('--folder',required=True);a=ap.parse_args()
    verify(ROOT/'build/packs'/a.pack,a.level,Path(a.folder))
