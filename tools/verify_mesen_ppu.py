"""Independently check Mesen's captured hardware map and visible tile pixels."""
import argparse,bisect,json,struct
from pathlib import Path
from verify_render import map_reader
ROOT=Path(__file__).resolve().parents[1]

def sprite_tiles(oam,vram):
    """Decode actual small tile overlays, and check both hardware limits."""
    overlays={};objects=[0]*224;slivers=[0]*224;first_overlay=None
    for i in range(128):
        x,y,tile,attr=oam[i*4:i*4+4]
        high=(oam[512+i//4]>>(2*(i%4)))&3
        if high&1:x-=256
        size=16 if high&2 else 8
        if x<=-size or x>=256 or y>=224:continue
        # SNES OBJ-to-OBJ priority is OAM order, not attr's BG priority.
        # A perfectly valid tile cache can therefore mask parts of an icon.
        if size==16 and attr in (0x32,0x34,0x36):
            assert first_overlay is None,('Gameplay icon behind tile-cache OBJ',i,first_overlay,tile)
        for line in range(max(32,y),min(176,y+size)):
            objects[line]+=1;slivers[line]+=size//8
        if attr==0x21 and size==8 and tile<128:
            if first_overlay is None:first_overlay=i
            assert (x,y) not in overlays,('Duplicate tile overlay',x,y)
            data=vram[0xE000+tile*32:0xE000+tile*32+32]
            pixels=[]
            for py in range(8):
                for px in range(8):
                    bit=7-px
                    pixels.append(sum(((data[py*2+(plane&1)+(16 if plane>=2 else 0)]>>bit)&1)<<plane for plane in range(4)))
            overlays[x,y]=pixels
    assert max(objects)<=32,('Hardware sprite limit',max(objects))
    assert max(slivers)<=34,('Hardware sprite tile limit',max(slivers))
    return overlays

def verify(base,level,folder):
    n=json.loads((base/'pack.json').read_text())['levels'][level-1]
    chart=json.loads((base/f'level{n}.json').read_text())
    if chart.get('mode1_projected'):
        from projected_tracks import Source
        projected_source=Source(base,n)
    timeline=(base/f'timeline{n}.bin').read_bytes();patterns=(base/f'patterns{n}.bin').read_bytes()
    tile=map_reader((base/f'track_map{n}.bin').read_bytes(),chart['map_height'],chart.get('map_offset_shift',0))
    nodes=[]
    for offset in chart['visibility_offsets'][:chart['visibility_cells']]:
        count=struct.unpack_from('<H',timeline,offset)[0]
        rows=[struct.unpack_from('<HH',timeline,offset+2+4*i) for i in range(count)]
        nodes.append(([t for t,v in rows],[v for t,v in rows]))
    versions=[([t for t,v in rows],[v for t,v in rows]) for rows in chart['pattern_versions']]
    projected_frames=chart.get('projected_spill_frames',[])
    projected_times=[f['frame'] for f in projected_frames]
    samples=0;checked_pixels=0
    for path in sorted(folder.glob('ppu-*.bin'),key=lambda p:struct.unpack_from('<H',p.read_bytes())[0]):
        blob=path.read_bytes();mode=7;selectors=None;native_palette=None
        if len(blob)==16+256+65536+512+544+289:
            mode=blob[-289];assert mode in (1,2,3)
            selectors=blob[-288:-192];native_palette=struct.unpack("<96H",blob[-192:]);blob=blob[:-289]
        if len(blob)==16+256+65536+512+544+1:
            mode=blob[-1];blob=blob[:-1];assert mode in (1,7)
        assert len(blob) in (16+256+32768,16+256+65536+512+544),path
        time,cx,cy,c,s,bx,by,step=struct.unpack_from('<H6hH',blob)
        mapping=blob[16:272];vram=blob[272:272+65536];pixels=vram[:32768][1::2]
        extended=len(blob)>16+256+32768
        palette=struct.unpack_from('<256H',blob,272+65536) if extended else None
        overlays=sprite_tiles(blob[-544:],vram) if extended else {}
        if projected_frames and mode==7:
            from mode1_tracks import decode_tile
            at=bisect.bisect_right(projected_times,time)-1
            expected_objects={}
            if at>=0:
                frame=projected_frames[at];glyphs=bytes.fromhex(frame['glyphs'])
                for x,y,g in frame['objects']:
                    raw=decode_tile(glyphs[g*32:g*32+32],list(range(1,len(frame['palette'])+1)))
                    expected_objects[x,y]=[frame['palette'][v-1] if v else None for v in raw]
            assert overlays.keys()==expected_objects.keys(),(path,'projected OBJ coverage',time,len(overlays),len(expected_objects),set(expected_objects)-overlays.keys())
            for xy,expected_obj in expected_objects.items():
                actual=overlays[xy]
                for i,(p,want) in enumerate(zip(actual,expected_obj)):
                    assert (p==0 if want is None else p!=0 and palette[128+p]==want),(path,'projected OBJ pixel',time,xy,i,p,want)
                checked_pixels+=64
        expected_rotation=next(((c,s) for f,c,s in reversed(chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[]))) if f<=time),(256,0))
        assert (c,s)==expected_rotation,(path,'rotation',time,(c,s),expected_rotation)
        if mode in (2,3):
            # Screen-space Mode 1: compare actual VRAM/CGRAM against an
            # independent reconstruction of the original world-space chart.
            expected=projected_source.screen(time)
            top=chart.get('viewport_top',32);bottom=chart.get('viewport_bottom',176)
            for sy in range(top,bottom):
                # The SNES adds one scanline to a BG's zero vertical scroll.
                py=sy+1
                for sx in range(256):
                    addr=(py//8)*32+sx//8
                    entry=struct.unpack_from('<H',vram,0xE000+addr*2)[0]
                    x=(7-sx%8) if entry&0x4000 else sx%8
                    y=(7-py%8) if entry&0x8000 else py%8
                    raw=vram[(entry&1023)*32:(entry&1023)*32+32]
                    p=sum(((raw[y*2+(plane&1)+(16 if plane>=2 else 0)]>>(7-x))&1)<<plane for plane in range(4))
                    index=((entry>>10)&7)*16+p if p else 0
                    wanted_index=int(expected[py,sx])
                    want=int(projected_source.palette[wanted_index])
                    assert (p==0 if wanted_index==0 else p!=0 and palette[index]==want),(path,'projected pixel',step,time,sx,sy,palette[index],want,entry)
                    checked_pixels+=1
            samples+=1
            continue
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
                if chart.get('wrapped_mode7_map'):address=((wy-by)&127)*128+((wx-bx)&127)
                assert mode==1 or 0<=address<16384,(path,'map address',address)
                physical=vram[address*2] if mode==7 else 0
                # Duplicate resident patterns may use another physical slot.
                # Validate the pixels reached by the hardware map directly.
                expected=patterns[indices[value]*64:indices[value]*64+64]
                actual=pixels[physical*64:physical*64+64]
                if mode==1:
                    address=(wy&31)*32+(wx&31)+(1024 if wx&32 else 0)
                    entry=struct.unpack_from('<H',vram,(0xE000 if selectors is not None else 0x8000)+address*2)[0]
                    physical=entry&1023;bank=(entry>>10)&7
                    raw=vram[physical*32:physical*32+32]
                    actual=bytes(sum(((raw[py*2+(plane&1)+(16 if plane>=2 else 0)]>>(7-px))&1)<<plane for plane in range(4)) for py in range(8) for px in range(8))
                x0,x1=max(0,left-wx*8),min(8,right-wx*8+1)
                y0,y1=max(0,top-wy*8),min(8,bottom-wy*8+1)
                for py in range(y0,y1):
                    if mode==1:
                        for px in range(x0,x1):
                            p=actual[py*8+px];index=bank*16+p if p else 0
                            raw_expected=expected[py*8+px]
                            if selectors is not None:
                                self_index=selectors[(bank-2)*16+p] if p else 0
                                assert self_index==raw_expected,(path,'exact palette selector',time,wx,wy,px,py,self_index,raw_expected)
                            expected_color=native_palette[raw_expected-32] if native_palette is not None and raw_expected else palette[raw_expected]
                            assert palette[index]==expected_color,(path,'native tile pixels',step,time,wx,wy,px,py,physical,index,expected[py*8+px])
                        checked_pixels+=x1-x0
                        continue
                    if actual[py*8+x0:py*8+x1]!=expected[py*8+x0:py*8+x1]:
                        position=(wx*8-(cx-128),wy*8-(cy-center))
                        overlay=overlays.get(position) if (c,s,shift)==(256,0,0) and physical==0 else None
                        assert overlay is not None,(path,'pattern',step,time,value,physical,wx,wy)
                        for px in range(x0,x1):
                            p=overlay[py*8+px]
                            color=palette[128+p] if p else palette[0]
                            assert color==palette[expected[py*8+px]],(path,'overlay pixels',step,time,position,px,py,p,expected[py*8+px])
                    checked_pixels+=x1-x0
        samples+=1
    assert samples>0,folder
    from verification_data import identity
    evidence=identity(base/'adofai.sfc')
    manifest=json.loads((folder/'manifest.json').read_text())
    assert all(manifest.get(k)==v for k,v in evidence.items()),'Mesen capture belongs to another build'
    assert manifest.get('passed') is True and manifest.get('vblank_overruns')==0,'Replay validation failed; pixel checks cannot turn it into a pass'
    result=dict(passed=True,code=chart['code'],samples=samples,visible_pixels_checked=checked_pixels,**evidence)
    (folder/'ppu-verification.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--level',type=int,default=1);ap.add_argument('--folder',required=True);a=ap.parse_args()
    verify(ROOT/'build/packs'/a.pack,a.level,Path(a.folder))
