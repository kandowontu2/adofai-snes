"""Compare compiled occupied pixels with an independent full-scene silhouette."""
import argparse,bisect,json,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter,ImageChops
from track_motion import motion_schedule
from track_geometry import piece
from verify_render import map_reader
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='sa1-release');ap.add_argument('--level',type=int,default=43)
    ap.add_argument('--start',type=int,default=10150);ap.add_argument('--end',type=int,default=10800);args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;c=json.loads((base/f'level{args.level}.json').read_text());data=json.loads((ROOT/f'assets/private/level{args.level}.json').read_text())
    motion=motion_schedule(data,c);offsets=[(0,0)]*len(c['notes']);events=sorted(motion);cursor=0
    pieces=[piece(c['notes'],i) for i in range(len(c['notes']))]
    timeline=(base/f'timeline{args.level}.bin').read_bytes();patterns=(base/f'patterns{args.level}.bin').read_bytes()
    tile=map_reader((base/f'track_map{args.level}.bin').read_bytes(),c['map_height'],c.get('map_offset_shift',0))
    nodes=[]
    for offset in c['visibility_offsets'][:c['visibility_cells']]:
        count=struct.unpack_from('<H',timeline,offset)[0];nodes.append([struct.unpack_from('<HH',timeline,offset+2+i*4) for i in range(count)])
    def at(rows,f):return rows[bisect.bisect_right(rows,(f,65536))-1][1]
    rows=[]
    for frame in range(args.start,args.end+1,4):
        while cursor<len(events) and events[cursor]<=frame:
            for i,p in motion[events[cursor]].items():offsets[i]=p
            cursor+=1
        camera=next(v for v in reversed(c['camera_versions']) if v[0]<=frame) if 'camera_versions' in c else None
        # Compiler camera data is explicit in render_viewports.
        views=c['render_viewports'];key=max(int(f) for f in views if int(f)<=frame);x,y,w,h=views[str(key)]
        expected=Image.new('L',(w*8,h*8))
        for i,(px,py,im) in enumerate(pieces):
            if not at([tuple(v) for v in c['visibility_floor_versions'][i]],frame):continue
            dx,dy=offsets[i];layer=Image.new('L',expected.size);layer.paste(im,(px+dx-x*8,py+dy-y*8));expected=ImageChops.lighter(expected,layer)
        actual=np.zeros((h*8,w*8),dtype=np.uint8)
        for yy in range(h):
            for xx in range(w):
                value=tile(x+xx,y+yy)
                if value&0x2000:value=at(nodes[(value&0x1fff)|((value&0xc000)>>1)],frame)
                p=at([tuple(v) for v in c['pattern_versions'][value]],frame)
                actual[yy*8:yy*8+8,xx*8:xx*8+8]=np.frombuffer(patterns[p*64:p*64+64],dtype=np.uint8).reshape(8,8)
        ghosts=(actual>0)&(np.array(expected.filter(ImageFilter.MaxFilter(3)))==0)
        count=int(ghosts.sum())
        if count:
            rows.append(dict(frame=frame,extra_pixels=count))
            if len(rows)==1:
                out=base/'verification';out.mkdir(exist_ok=True)
                rgb=np.stack([ghosts*255,(actual>0)*100,np.array(expected)>0],-1).astype(np.uint8)
                Image.fromarray(rgb).resize((w*16,h*16)).save(out/f'ghosts-{args.level}.png')
    print(json.dumps(dict(pack=args.pack,frames=len(range(args.start,args.end+1,4)),ghost_frames=rows[:20],total_ghost_frames=len(rows))))

if __name__=='__main__':main()
