"""Compact HUDs and cartridge-native orb/streak presentation tables."""
import math
from PIL import Image,ImageDraw
import make_assets as common

COLOR_NAMES=['FIRE','ICE','GREEN','VIOLET','PINK','GOLD','WHITE','LIME']
COLOR_RGB=[(255,116,43),(80,205,232),(70,215,130),(157,102,255),
           (255,91,176),(255,204,56),(230,235,245),(179,245,66)]
JUDGMENTS=['TOO EARLY','EARLY','EPERFECT','-PERFECT','XPERFECT','PERFECT+',
           'LPERFECT','LATE','TOO LATE','MISS','OVERLOAD']
WEIGHTS=[20,40,75,100,100,100,75,40,20,0,0]

def hud(lines):
    # Sparse text records: VRAM-map byte offset, attribute, length, ASCII.
    result=bytearray()
    for row,text,pal in lines:
        col=(32-len(text))//2
        assert col>=0,text
        result+=(row*64+col*2).to_bytes(2,'little')+bytes([0x20|(pal<<2),len(text)])+text.encode('ascii')
    return bytes(result)+b'\xff\xff'

def orbit_arc_shapes():
    result=[]
    for i in range(16):
        a=(i*4+2)*math.pi/128
        origin=(round(math.cos(a)*24)-4,round(math.sin(a)*24)-4)
        points=[(round(math.cos(j*math.pi/128)*24)-origin[0],
                 round(math.sin(j*math.pi/128)*24)-origin[1]) for j in range(i*4,i*4+5)]
        assert all(1<=x<=6 and 1<=y<=6 for x,y in points),(i,points)
        result.append((origin,points))
    return result

def orbit_arc_layout():
    shapes=orbit_arc_shapes();rows=[]
    for i in range(64):
        q,k=divmod(i,16);base=k if q in (0,2) else 15-k
        flip_x=q in (1,2);flip_y=q in (2,3)
        x,y=shapes[base][0]
        rows.append(((-x-7 if flip_x else x),(-y-7 if flip_y else y),128+base,
                     (64 if flip_x else 0)|(128 if flip_y else 0)))
    return rows

def streak_tiles(sheet,compact=False):
    d=ImageDraw.Draw(sheet)
    if compact:
        # Quarter-circle fragments share their exact endpoint pixels.
        # OBJ flips cover all 64 angles; four levels taper the same curve.
        d.rectangle((0,64,127,127),fill=0)
        for level in range(4):
            for i,(_,points) in enumerate(orbit_arc_shapes()):
                tile=128+level*16+i;x=tile%16*8;y=tile//16*8
                path=[(x+px,y+py) for px,py in points]
                if level<2:d.line(path,fill=1,width=3)
                d.line(path,fill=4-level,width=1)
                # Longer tangent fragments keep zoomed-in streaks connected.
                tile+=64;x=tile%16*8;y=tile//16*8
                fragment=Image.new('P',(8,8));fd=ImageDraw.Draw(fragment)
                path=[(round(3.5+(px-3.5)*1.8),round(3.5+(py-3.5)*1.8)) for px,py in points]
                if level<2:fd.line(path,fill=1,width=3)
                fd.line(path,fill=4-level,width=1)
                sheet.paste(fragment,(x,y))
        return
    for dim in range(2):
        for direction in range(16):
            tile=128+dim*64+(direction//8)*32+(direction%8)*2;x=tile%16*8;y=tile//16*8
            d.rectangle((x,y,x+15,y+15),fill=0)
            a=direction*math.pi/16;dx=math.cos(a)*6;dy=math.sin(a)*6
            p=(round(x+8-dx),round(y+8-dy));q=(round(x+8+dx),round(y+8+dy))
            if not dim:d.line((*p,*q),fill=1,width=3)
            d.line((*p,*q),fill=2 if dim else 4,width=1)

def tables(fps,compact=False,adaptive_audio=False):
    values=[]
    def words(name,items):values.append(name+': .word '+','.join(str(x&65535) for x in items))
    pitches=[round(1536*n/10) for n in range(5,21)]
    if adaptive_audio:pitches=[p if n<=10 else round(p/3)*3 for n,p in zip(range(5,21),pitches)]
    words('speed_pitches',pitches)
    if adaptive_audio:
        audio_pitches=[p if n<=10 else p//3*2 for n,p in zip(range(5,21),pitches)]
        words('audio_speed_pitches',audio_pitches)
        words('audio_speed_streams',[p*3 for p in audio_pitches])
    words('speed_scales',[round(fps*.004*p/1536*65536) for p in pitches])
    baseline=8 if compact else 0
    limit=30 if compact else 8
    words('speed_offset_bases',[i*(limit*2+1)*2 for i in range(16)])
    offsets=[round((c+baseline)*p/1536*65536) for p in pitches for c in range(-limit,limit+1)]
    words('speed_offsets',[v>>16 for v in offsets])
    words('speed_offsets_frac',[v&65535 for v in offsets])
    words('judgment_weights',WEIGHTS)
    values.append('trail_angles: .byte '+','.join(str(round(math.atan(i/128)*16/math.pi)) for i in range(129)))
    words('trail_tiles',[128+i if compact else 128+(i//8)*32+(i%8)*2 for i in range(16)])
    if compact:
        arcs=orbit_arc_layout()
        words('orbit_arc_x',[a[0] for a in arcs]);words('orbit_arc_y',[a[1] for a in arcs])
        values.append('orbit_arc_tiles: .byte '+','.join(str(a[2]) for a in arcs))
        values.append('orbit_arc_flips: .byte '+','.join(str(a[3]) for a in arcs))
    words('decimal_lo',[100000&65535,10000,1000,100,10,1])
    words('decimal_hi',[100000>>16,0,0,0,0,0])
    values.append('color_pointers: .word '+','.join('color_name'+str(i) for i in range(8)))
    for i,name in enumerate(COLOR_NAMES):values.append(f'color_name{i}: .byte "{name:<6}",0')
    palette=[]
    for rgb in COLOR_RGB:
        colors=[(0,0,0)]
        for i in range(1,8):
            if i<=4:colors.append(tuple(round(c*(.18+.205*i)) for c in rgb))
            else:colors.append(tuple(round(c+(255-c)*((i-4)/3)) for c in rgb))
        palette.extend(colors+[(0,0,0)]*8)
    words('orb_colors',[(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in palette])
    values.append('judgment_names: .word '+','.join('judgment_name'+str(i) for i in range(11)))
    for i,name in enumerate(JUDGMENTS):values.append(f'judgment_name{i}: .byte "{name:<12}",0')
    live=['EARLY!!','EARLY','EPERFECT','-PERFECT','XPERFECT','PERFECT+','LPERFECT','LATE','LATE!!','MISS...','OVERLOAD...']
    values.append('live_judgments: .word '+','.join('live_judgment'+str(i) for i in range(11)))
    for i,name in enumerate(live):values.append(f'live_judgment{i}: .byte "{name:<11}",0')
    return '\n'.join(values)+'\n'
