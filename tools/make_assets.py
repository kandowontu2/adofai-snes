"""Build SNES tiles, HUD layouts, chart/timing tables, and streaming audio."""
import json
import math
import random
import shutil
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from spc700 import assemble

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build'
FPS=21477272/357366
RATE=16000
RING=32760
FONT={
'A':['01110','10001','10001','11111','10001','10001','10001'],
'B':['11110','10001','10001','11110','10001','10001','11110'],
'C':['01111','10000','10000','10000','10000','10000','01111'],
'D':['11110','10001','10001','10001','10001','10001','11110'],
'E':['11111','10000','10000','11110','10000','10000','11111'],
'F':['11111','10000','10000','11110','10000','10000','10000'],
'G':['01111','10000','10000','10111','10001','10001','01111'],
'H':['10001','10001','10001','11111','10001','10001','10001'],
'I':['11111','00100','00100','00100','00100','00100','11111'],
'J':['00111','00010','00010','00010','10010','10010','01100'],
'K':['10001','10010','10100','11000','10100','10010','10001'],
'L':['10000','10000','10000','10000','10000','10000','11111'],
'M':['10001','11011','10101','10101','10001','10001','10001'],
'N':['10001','11001','10101','10011','10001','10001','10001'],
'O':['01110','10001','10001','10001','10001','10001','01110'],
'P':['11110','10001','10001','11110','10000','10000','10000'],
'Q':['01110','10001','10001','10001','10101','10010','01101'],
'R':['11110','10001','10001','11110','10100','10010','10001'],
'S':['01111','10000','10000','01110','00001','00001','11110'],
'T':['11111','00100','00100','00100','00100','00100','00100'],
'U':['10001','10001','10001','10001','10001','10001','01110'],
'V':['10001','10001','10001','10001','10001','01010','00100'],
'W':['10001','10001','10001','10101','10101','11011','10001'],
'X':['10001','10001','01010','00100','01010','10001','10001'],
'Y':['10001','10001','01010','00100','00100','00100','00100'],
'Z':['11111','00001','00010','00100','01000','10000','11111'],
'0':['01110','10001','10011','10101','11001','10001','01110'],
'1':['00100','01100','00100','00100','00100','00100','01110'],
'2':['01110','10001','00001','00010','00100','01000','11111'],
'3':['11110','00001','00001','01110','00001','00001','11110'],
'4':['00010','00110','01010','10010','11111','00010','00010'],
'5':['11111','10000','10000','11110','00001','00001','11110'],
'6':['01110','10000','10000','11110','10001','10001','01110'],
'7':['11111','00001','00010','00100','01000','01000','01000'],
'8':['01110','10001','10001','01110','10001','10001','01110'],
'9':['01110','10001','10001','01111','00001','00001','01110'],
'-':['00000','00000','00000','11111','00000','00000','00000'],
'+':['00000','00100','00100','11111','00100','00100','00000'],
':':['00000','00100','00100','00000','00100','00100','00000'],
'.':['00000','00000','00000','00000','00000','00110','00110'],
'/':['00001','00010','00010','00100','01000','01000','10000'],
'%':['11001','11010','00100','00100','01000','10110','00110'],
'!':['00100','00100','00100','00100','00100','00000','00100'],
'<':['00010','00100','01000','10000','01000','00100','00010'],
'>':['01000','00100','00010','00001','00010','00100','01000'],
'=':['00000','00000','11111','00000','11111','00000','00000'],
'[':['01110','01000','01000','01000','01000','01000','01110'],
']':['01110','00010','00010','00010','00010','00010','01110'],
}

def tile_bytes(pix,bpp=4):
    out=bytearray()
    for pair in range(bpp//2):
        for y in range(8):
            for bit in (pair*2,pair*2+1):
                out.append(sum(((int(pix[y,x])>>bit)&1)<<(7-x) for x in range(8)))
    return out

def word_data(values):
    return struct.pack('<'+'H'*len(values),*(x&65535 for x in values))

def graphics():
    from graphics_sources import write_graphics
    write_graphics(OUT, "demo")

def generate_reference_graphics():
    pal=[(8,11,24),(13,17,34),(20,24,43),(31,27,45),(42,30,44),
         (52,35,43),(30,44,61),(35,60,76),(45,85,101),(77,103,120),
         (118,142,157),(188,203,204),(240,224,190),(112,66,49),(58,42,51),(18,32,47)]
    bg=Image.new('P',(256,256),0)
    draw=ImageDraw.Draw(bg)
    for y in range(32,192):
        band=1 if y<60 or y>165 else 2
        draw.line((0,y,255,y),fill=band)
    for y in (67,68,93,126,127,153,173):
        draw.line((0,y,112,y),fill=3)
        draw.line((144,y+6,255,y+6),fill=6)
    draw.rectangle((0,0,255,30),fill=1)
    draw.line((8,30,247,30),fill=6)
    draw.line((8,191,247,191),fill=6)
    draw.rectangle((0,192,255,223),fill=1)
    draw.line((8,30,76,30),fill=13)
    draw.line((180,30,247,30),fill=8)
    rng=random.Random(7701)
    for _ in range(80):
        x=rng.randrange(8,248); y=rng.randrange(38,185)
        draw.point((x,y),fill=rng.choice([3,6,7,9]))
    for x,y in [(23,50),(204,68),(153,158),(67,173),(233,141)]:
        draw.line((x-1,y,x+1,y),fill=9); draw.point((x,y-1),fill=7); draw.point((x,y+1),fill=7)
    for x in range(16,240,16): draw.point((x,200),fill=7)
    tiles=[]; lookup={}; tilemap=[]
    a=np.array(bg)
    for y in range(32):
        for x in range(32):
            t=bytes(tile_bytes(a[y*8:y*8+8,x*8:x*8+8]))
            if t not in lookup: lookup[t]=len(tiles); tiles.append(t)
            tilemap.append(lookup[t])
    assert len(tiles)<=512,len(tiles)
    (OUT/'background.chr').write_bytes(b''.join(tiles))
    (OUT/'background.map').write_bytes(word_data(tilemap))
    # Four matching HUD palettes: muted, ice, fire, and white.
    pal += [(0,0,0),(111,135,153),(111,135,153),(111,135,153)]
    pal += [(0,0,0),(100,208,239),(100,208,239),(100,208,239)]
    pal += [(0,0,0),(255,166,95),(255,166,95),(255,166,95)]
    pal += [(0,0,0),(232,237,232),(232,237,232),(232,237,232)]
    while len(pal)<128: pal.append((0,0,0))
    objpals=[
      [(0,0,0),(29,40,55),(56,75,91),(96,118,132),(147,170,177),(210,221,212),(18,27,42),(42,55,70)],
      [(0,0,0),(81,27,36),(150,43,37),(222,65,35),(255,116,43),(255,176,81),(255,223,145),(255,249,215)],
      [(0,0,0),(18,50,79),(22,100,140),(39,155,201),(80,205,232),(145,236,245),(204,250,253),(246,255,255)],
      [(0,0,0),(32,56,62),(50,91,90),(68,137,120),(122,193,147),(190,228,175),(232,245,207),(255,255,237)],
    ]
    for colors in objpals: pal.extend(colors+[(0,0,0)]*(16-len(colors)))
    pal += [(0,0,0)]*(256-len(pal))
    (OUT/'palette.bin').write_bytes(word_data([(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in pal]))
    bg.putpalette([v for c in pal for v in c]); bg.crop((0,0,256,224)).save(OUT/'background.png')
    font=bytearray()
    for code in range(128):
        pixels=np.zeros((8,8),dtype=np.uint8)
        for y,row in enumerate(FONT.get(chr(code),[])):
            for x,c in enumerate(row): pixels[y,x+1]=int(c)
        font += tile_bytes(pixels,2)
    (OUT/'font.chr').write_bytes(font)
    sheet=Image.new('P',(128,128),0); d=ImageDraw.Draw(sheet)
    def stamp(tile,kind):
        x=(tile%16)*8; y=(tile//16)*8
        if kind in ('future','past','pivot'):
            d.rounded_rectangle((x+1,y+1,x+14,y+14),radius=3,fill=1,outline=2)
            d.line((x+4,y+2,x+11,y+2),fill=3)
            d.line((x+3,y+3,x+12,y+3),fill=2)
            if kind=='past':
                d.rectangle((x+6,y+6,x+9,y+9),fill=3)
            if kind=='pivot':
                d.rounded_rectangle((x+3,y+3,x+12,y+12),radius=2,outline=5)
        elif kind=='planet':
            d.ellipse((x+1,y+1,x+14,y+14),fill=1)
            d.ellipse((x+2,y+2,x+13,y+13),fill=2)
            d.ellipse((x+3,y+2,x+12,y+12),fill=3)
            d.ellipse((x+4,y+3,x+12,y+11),fill=4)
            d.ellipse((x+4,y+3,x+10,y+8),fill=5)
            d.ellipse((x+5,y+3,x+8,y+6),fill=7)
            d.point((x+11,y+10),fill=6)
        elif kind=='ring':
            d.ellipse((x,y,x+15,y+15),outline=4)
            for a,b in [(0,0),(14,0),(0,14),(14,14)]: d.rectangle((x+a,y+b,x+a+1,y+b+1),fill=5)
        elif kind=='trail':
            d.ellipse((x+5,y+5,x+10,y+10),fill=2)
            d.ellipse((x+6,y+6,x+9,y+9),fill=3)
        elif kind=='portal':
            for inset,col in [(0,2),(2,3),(4,4),(6,6)]: d.ellipse((x+inset,y+inset,x+15-inset,y+15-inset),outline=col)
        elif kind=='spark':
            d.line((x+4,y+8,x+11,y+8),fill=6); d.line((x+8,y+4,x+8,y+11),fill=6)
            d.point((x+6,y+6),fill=4); d.point((x+10,y+10),fill=4)
    for tile,kind in [(0,'future'),(2,'past'),(4,'pivot'),(6,'planet'),(8,'ring'),(10,'trail'),(12,'portal'),(14,'spark')]: stamp(tile,kind)
    pixels=np.array(sheet); obj=bytearray()
    for y in range(16):
        for x in range(16): obj+=tile_bytes(pixels[y*8:y*8+8,x*8:x*8+8])
    (OUT/'objects.chr').write_bytes(obj)
    sheet.putpalette([v for c in pal[128:144]+[(0,0,0)]*240 for v in c]); sheet.save(OUT/'objects.png')
    print('Generated',len(tiles),'background tiles and original pixel graphics.')

def hud():
    def make(lines,name):
        words=[0]*1024
        for y,text,palette in lines:
            x=(32-len(text))//2
            for c in text:
                words[y*32+x]=ord(c)|(palette<<10)|0x2000; x+=1
        (OUT/(name+'.hud')).write_bytes(word_data(words))
    make([(2,'A DANCE OF FIRE AND ICE',7),
          (5,'S U P E R   N I N T E N D O',4),
          (8,'1-X',6),(10,'A DANCE OF',7),(12,'FIRE AND ICE',5),
          (17,'TWO PLANETS. ONE BUTTON.',7),
          (19,'TAP WHEN THE PLANET LANDS.',4),
          (22,'A / START  PLAY',7),(24,'X PRACTICE    Y WATCH',5),
          (26,'< > TIMING OFFSET: +0 FRAMES',4)],'title')
    make([(1,'1-X  A DANCE OF FIRE AND ICE',7),
          (3,'COMBO 000   BEST 000    000%',4),
          (24,'START PAUSE   SELECT RETRY',4),
          (26,'A B X Y L R / D-PAD TO TAP',4)],'game')
    make([(1,'1-X  A DANCE OF FIRE AND ICE',7),
          (3,'COMBO 000   BEST 000    000%',4),
          (10,'RHYTHM LOST',6),(12,'TAP TO TRY AGAIN',7),
          (15,'A RETRY    SELECT TITLE',4),
          (24,'KEEP A STEADY BEAT.',5)],'fail')
    make([(1,'1-X  A DANCE OF FIRE AND ICE',7),
          (3,'COMBO 000   BEST 000    100%',4),
          (10,'LEVEL COMPLETE!',5),(13,'PERFECT 000    MISSES 000',7),
          (16,'A PLAY AGAIN   SELECT TITLE',4),
          (24,'FIRE AND ICE IN EQUILIBRIUM.',6)],'clear')
    make([(1,'1-X  A DANCE OF FIRE AND ICE',7),
          (3,'COMBO 000   BEST 000    000%',4),
          (10,'PAUSED',7),(13,'START TO RESUME',5),
          (16,'SELECT TO RETURN TO TITLE',4)],'pause')

def chart():
    data=json.loads((ROOT/'assets/private/level1.json').read_text())
    floors=data['floors']; notes=[]; x=0; y=256
    times=[0.0]; directions=[]
    for f in floors:
        # Unity uses sin(angle) for X, cos(angle) for Y; screen Y goes down.
        angle=(f['exitangle']-math.pi/2)%(2*math.pi)
        directions.append(round(angle/(math.pi/2))%4)
    t=data['offset']+data['countdown']*60/data['bpm']
    for i,f in enumerate(floors):
        if i:
            prev=floors[i-1]
            if i>1:
                arc=(prev['exitangle']-prev['entryangle'])%(math.pi*2)
                if arc<0.00001: arc=math.pi*2
                t+=(arc/math.pi+prev['extraBeats'])*60/data['bpm']/prev['speed']
            times.append(t)
            a=directions[i-1]*math.pi/2
            x+=round(math.cos(a)*24); y+=round(math.sin(a)*24)
        notes.append({'step':i,'x':x,'y':y,'time':times[i],
                      'frame':round(times[i]*FPS), 'direction':directions[i],
                      'slow':f['speed']<0.5})
    # Entry direction for the orbit starts on the previous tile.
    starts=[128]+[((directions[i-1]*64)+128)&255 for i in range(1,len(floors))]
    duration=max(83,math.ceil(notes[-1]['time']+3))
    frames=math.ceil(duration*FPS)
    counts=[]; previous=0
    for frame in range(frames):
        target=math.floor(frame*RATE/FPS/16)*3
        counts.append(target-previous); previous=target
    inc=[]
    clock_scale=round(FPS*0.004*65536)
    for label,values,word in [
      ('note_x',[n['x'] for n in notes],True),('note_y',[n['y'] for n in notes],True),
      ('note_time',[n['frame'] for n in notes],True),('note_angle',starts,False),
      ('note_slow',[int(n['slow']) for n in notes],False),
      ('note_progress',[round(n['step']*100/167) for n in notes],False),
      ('sin24',[round(math.sin(i*math.pi/128)*24) for i in range(256)],False),
      ('cos24',[round(math.cos(i*math.pi/128)*24) for i in range(256)],False),
      ('phase_fast',[round(i*128/(FPS*0.4))&255 for i in range(256)],False),
      ('phase_slow',[round(i*128/(FPS*1.6))&255 for i in range(256)],False),
      ('countdown_angle',[round((f/FPS-data['offset'])*128/0.4)&255 for f in range(128)],False),
      ('clock_lo_low',[(i*clock_scale)&65535 for i in range(256)],True),
      ('clock_lo_high',[(i*clock_scale)>>16 for i in range(256)],True),
      ('clock_hi_low',[(i*clock_scale*256)&65535 for i in range(256)],True),
      ('clock_hi_high',[(i*clock_scale*256)>>16 for i in range(256)],True),
      ('stream_counts',counts,False)]:
        inc.append(label+':')
        for i in range(0,len(values),16): inc.append('    '+('.word ' if word else '.byte ')+','.join(str(v& (65535 if word else 255)) for v in values[i:i+16]))
    (OUT/'tables.inc').write_text('\n'.join(inc)+'\n')
    (OUT/'constants.inc').write_text(f'FIRST_HIT = {notes[1]["frame"]}\nLAST_HIT = {notes[-1]["frame"]}\nSTREAM_END = {frames}\n')
    (OUT/'level.json').write_text(json.dumps({'fps':FPS,'sample_rate':RATE,'notes':notes,'duration':duration,'first_frame':notes[1]['frame'],'last_frame':notes[-1]['frame']},indent=2))
    print('Chart:',len(notes)-1,'hits, first at',notes[1]['time'],'s; last at',notes[-1]['time'],'s.')
    return duration

def audio(duration):
    wav=ROOT/'assets/private/1-X.wav'; raw=OUT/'music.pcm'; brr=OUT/'music.brr'
    if not brr.exists() or brr.stat().st_mtime<wav.stat().st_mtime:
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-af',f'volume=0.78,apad=whole_dur={duration+4}',
                        '-t',str(duration+4),'-ac','1','-ar',str(RATE),'-f','s16le',str(raw)],check=True)
        encoder=ROOT/'.tools/brr_encode.exe'
        if not encoder.exists() or encoder.stat().st_mtime<(ROOT/'tools/brr_encode.c').stat().st_mtime:
            subprocess.run(['gcc','-O3',str(ROOT/'tools/brr_encode.c'),'-lm','-o',str(encoder)],check=True)
        subprocess.run([str(encoder),str(raw),str(brr)],check=True)
    blob=brr.read_bytes()
    blob+=bytes((-len(blob))%RING)
    banks=[]
    for i in range(0,len(blob),RING):
        name=f'music{i//RING+1:02d}.bin'; (OUT/name).write_bytes(blob[i:i+RING]); banks.append(name)
    assert len(banks)<=31
    asm=[]
    for i,name in enumerate(banks): asm.extend([f'.segment "MUSIC{i+1:02d}"',f'.incbin "build/{name}"'])
    (OUT/'music.inc').write_text('\n'.join(asm)+'\n')
    return len(banks)

def linker(banks):
    lines=['MEMORY {',' ZP: start=$0000,size=$0100,type=rw;',
           ' ROM: start=$008000,size=$7FB0,type=ro,file=%O,fill=yes,fillval=$FF;',
           ' HDR: start=$00FFB0,size=$30,type=ro,file=%O,fill=yes;',
           ' VEC: start=$00FFE0,size=$20,type=ro,file=%O,fill=yes;']
    for i in range(1,32): lines.append(f' B{i:02d}: start=${i:02X}8000,size=$8000,type=ro,file=%O,fill=yes,fillval=$00;')
    lines.extend(['}','SEGMENTS {',' ZEROPAGE: load=ZP,type=zp;',
                  ' CODE: load=ROM,type=ro;',' RODATA: load=ROM,type=ro;',
                  ' HEADER: load=HDR,type=ro;',' VECTORS: load=VEC,type=ro;'])
    for i in range(1,banks+1): lines.append(f' MUSIC{i:02d}: load=B{i:02d},type=ro;')
    lines.append(' ASSETS: load=B31,type=ro;')
    lines.append('}')
    (OUT/'lorom.cfg').write_text('\n'.join(lines)+'\n')

def main():
    OUT.mkdir(exist_ok=True)
    if not (ROOT/'assets/private/level1.json').exists():
        subprocess.run([shutil.which('python'),'tools/import_level.py'],cwd=ROOT,check=True)
    graphics(); hud(); duration=chart(); banks=audio(duration); linker(banks)
    (OUT/'spc.bin').write_bytes(assemble())

if __name__=='__main__': main()
