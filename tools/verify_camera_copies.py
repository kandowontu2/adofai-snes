"""Check actual SA-1 live-copy results against a separate sprite oracle."""
import argparse,json,re,struct
from pathlib import Path

def signed(v):return (v+32768)%65536-32768
def sprites(source,length,views,arc):
    objects=[];lines=[0]*224;slivers=[0]*224
    def item(i):
        x,y,t,a=source[i:i+4];h=source[512+i//16]>>(2*((i//4)%4))&3
        return x-256*(h&1),y,t,a,16 if h&2 else 8
    for i in range(0,length,4):
        x,y,t,a,size=item(i)
        if y==224:continue
        dx=dy=0
        if i<32 and item((i//16)*16+8)[1]!=224:
            dx=8 if i&4 else -8;dy=8 if i&8 else -8
        for c,s,sx,sy,phase in reversed(views):
            inx,outx=dx,dx;iny,outy=dy,dy
            tile,attr=t,a
            if i>=32 and t>=128:
                q={0:0,0x40:1,0xC0:2,0x80:3}[a&0xC0]
                old=q*16+(15-(t&15) if q%2 else t&15);new=(old+phase)&63
                inx,iny=arc['x'][old]+4,arc['y'][old]+4
                outx,outy=arc['x'][new]+4,arc['y'][new]+4
                tile=(t&0x70)|arc['tiles'][new];attr=(a&0x3F)|arc['flips'][new]
            ox=(x+size//2-inx-128)*16+sx;oy=(y+size//2-iny-104)*16+sy
            # Rotate the shared parent, preserving native arc-cell offsets.
            nx=(ox*c//256)-(oy*s//256);ny=(ox*s//256)+(oy*c//256)
            nx=(nx+8)//16+128+outx-size//2;ny=(ny+8)//16+104+outy-size//2
            if nx>=256 or nx+size<0 or ny>=177 or ny+size<33:continue
            rows=range(max(32,ny),min(177,ny+size))
            if len(objects)==128 or any(lines[r]>=32 or slivers[r]+size//8>34 for r in rows):continue
            for r in rows:lines[r]+=1;slivers[r]+=size//8
            objects.append((nx,ny,tile,attr,size))
    out=bytearray(544)
    for j,(x,y,t,a,size) in enumerate(objects):
        out[j*4:j*4+4]=bytes((x&255,y,t,a))
        out[512+j//4]|=(int(x<0)|2*int(size==16))<<(2*(j%4))
    return bytes(out),len(objects)*4

def verify(pack,folder):
    pack=Path(pack);folder=Path(folder)
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    rom=(pack/'adofai.sfc').read_bytes();arc={}
    for key in ('x','y','tiles','flips'):
        at=labels['orbit_arc_'+key]&0x7fff
        arc[key]=[signed(v) for v in struct.unpack_from('<64H',rom,at)] if key in ('x','y') else list(rom[at:at+64])
    blob=(folder/'camera-copies.bin').read_bytes();stride=8+40+544*2
    assert blob and len(blob)%stride==0
    for at in range(0,len(blob),stride):
        frame,ni,no,count=struct.unpack_from('<4H',blob,at);assert 1<=count<=4
        views=[tuple(signed(v) for v in struct.unpack_from('<5H',blob,at+8+j*10)) for j in range(count)]
        source=blob[at+48:at+48+544];actual=blob[at+48+544:at+stride]
        expected,n=sprites(source,ni,views,arc)
        assert n==no,('Copy object count differs',frame,n,no)
        for a,b in ((0,n),(512,544)):
            assert expected[a:b]==actual[a:b],('Live camera-copy sprite differs',frame,next(i for i in range(a,b) if expected[i]!=actual[i]),expected[a:b].hex(),actual[a:b].hex())
    result=dict(passed=True,jobs=len(blob)//stride)
    (folder/'camera-copy-verification.json').write_text(json.dumps(result,indent=2));print(result,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);a=p.parse_args();verify(a.pack,a.folder)
