"""Compile an official-world pack, connected BG tracks, and ExHiROM payload."""
import argparse
import hashlib
import inspect
import json
import math
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageChops
import make_assets as common
import presentation_assets as presentation

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/campaign'
FPS=common.FPS
RATE=12000
RING=32760
MAX_NOTES=4352

def note_control(note):
    return (int(note['ccw']) | (2 if note['planets']==3 else 0)
            | (4 if note.get('margin',100)>100 else 0)
            | ((note.get('taps_needed',1)-1)<<3))


def compile_chart(data):
    fs=data['floors'];n=len(fs)
    assert n<=MAX_NOTES
    assert all(f['numPlanets'] in (2,3) for f in fs)
    assert data.get('neo_cosmos') or all(f['holdLength']<=0 for f in fs), 'Holds need Neo Cosmos runtime support'
    from neo_mechanics import duration_beats, packed_pause
    assert all(1<=max(1,int(f.get('tapsNeeded',1)))<=32 for f in fs)
    tau=2*math.pi;beat=60/data['bpm'];times=[0.0]
    def arc(f):
        i=f['seqID']
        extra=math.pi*(f['numPlanets']-2)/f['numPlanets'] if i and not f['midSpin'] and not fs[i-1]['midSpin'] else 0
        value=((f['exitangle']-f['entryangle'])*(-1 if f['isCCW'] else 1)-extra)%tau
        if value<0.00001 or value>tau-0.00001:value=0 if f['midSpin'] else tau
        return value/math.pi
    t=data['offset']+(data['countdown']-1+arc(fs[0])/fs[0]['speed'])*beat
    x=y=0.0;notes=[]
    from track_motion import stick_schedule
    sticking=stick_schedule(data,n)
    checkpoint_events={c['floor']:c for c in data.get('checkpoints',[])}
    for i,f in enumerate(fs):
        if i:
            p=fs[i-1]
            if i>1:t+=duration_beats(p,arc(p))*beat/p['speed']
            times.append(t)
            direction=p['exitangle']-math.pi/2
            x+=math.cos(direction)*24;y+=math.sin(direction)*24
        flags=0
        if i:
            if f['speed']>fs[i-1]['speed']+0.001:flags|=1
            if f['speed']<fs[i-1]['speed']-0.001:flags|=2
            if f['isCCW']!=fs[i-1]['isCCW']:flags|=4
        if f['midSpin'] or f.get('auto',0):flags|=8
        if f['midSpin']:flags|=16
        if f['extraBeats']>0:flags|=32
        if data.get('neo_cosmos') and f.get('freeroam'):flags &= ~32
        if data.get('neo_cosmos') and (f['holdLength']>=0 or
                (i and (fs[i-1]['holdLength']>=0 or f['numPlanets']!=fs[i-1]['numPlanets']))):flags|=32
        if i in checkpoint_events:flags|=64
        if data.get('hidden_icons',[False]*n)[i]:flags|=128
        rate=128*data['bpm']*f['speed']/(60*FPS)*(-1 if f['isCCW'] else 1)
        entry_extra=math.pi*(f['numPlanets']-2)/f['numPlanets']*(-1 if f['isCCW'] else 1) if i and not fs[i-1]['midSpin'] else 0
        notes.append({'step':i,'x_float':x,'y_float':y,'time':times[i],
                      'frame':round(times[i]*FPS),'angle':round((f['entryangle']+entry_extra-math.pi/2)*128/math.pi)&255,
                      'rate':round(rate*256),'ccw':bool(f['isCCW']),'speed':f['speed'],'flags':flags,
                      'exit_angle':f['exitangle']-math.pi/2,
                      'entry_angle':f['entryangle']-math.pi/2,
                      'planets':f['numPlanets'],'margin':f.get('margin',100),
                      'taps_needed':max(1,int(f.get('tapsNeeded',1))),
                      'hold_length':f['holdLength'] if data.get('neo_cosmos') else -1,
                      'freeroam':bool(f.get('freeroam',False)),
                      'stick_to_floor':sticking[i],
                      'spin_kind':'midspin' if f['midSpin'] else 'full' if i and i+1<n and abs(math.remainder(f['exitangle']-f['entryangle'],tau))<.00001 else 'normal',
                      'pause_frames':round(f['extraBeats']*beat/f['speed']*FPS)})
    if data.get('native_layout_version',0)>=2:
        positions=data['native_positions'];size=data.get('native_tile_size',1.5)
        assert len(positions)==n and size>0
        origin=positions[0]
        for note,pos in zip(notes,positions):
            note['x_float']=(pos[0]-origin[0])*24/size
            note['y_float']=-(pos[1]-origin[1])*24/size
    bx=128-math.floor(min(v['x_float'] for v in notes)/8)*8
    by=144-math.floor(min(v['y_float'] for v in notes)/8)*8
    for v in notes:
        v['x']=round(v['x_float']+bx);v['y']=round(v['y_float']+by)
    checkpoints=[]
    prefix=data['countdown']*beat if data['separate_countdown'] else 0
    for trigger,event in sorted(checkpoint_events.items()):
        floor=max(0,min(n-2,trigger+event.get('tileOffset',0)))
        if not floor:continue
        ready=notes[floor]['time']+fs[floor]['extraBeats']*beat/fs[floor]['speed']
        start=max(prefix,ready-4*beat/fs[floor]['speed'])
        block=max(0,math.floor(start*RATE/16))
        checkpoints.append(dict(trigger=trigger,floor=floor,block=block,origin_frame=round(block*16/RATE*FPS),
                                ready_frame=round(ready*FPS),beat_frames=max(1,round(beat/fs[floor]['speed']*FPS))))
    assert all(notes[i]['frame']>=notes[i-1]['frame'] for i in range(2,n))
    arrays=[]
    def words(values):return common.word_data(values)
    def bytes_(values):return bytes(values)
    # Offsets correspond to the fixed WRAM arrays in campaign.s.
    arrays += [words([v['x'] for v in notes]),words([v['y'] for v in notes]),words([v['frame'] for v in notes])]
    arrays += [bytes_([v['angle'] for v in notes]),bytes_([v['flags'] for v in notes]),words([v['rate'] for v in notes])]
    arrays += [bytes_([round(v['step']*100/(n-1)) for v in notes]),bytes_([note_control(v) for v in notes])]
    arrays += [words([packed_pause(v) for v in notes])]
    blob=b''.join(arrays)
    assert len(blob)==14*n
    result={'id':data['id'],'code':data.get('code',f'{data["id"]}-X'),'title':data['title'],'bpm':data['bpm'],'offset':data['offset'],
            'separate_countdown':data['separate_countdown'],'countdown':data['countdown'],
            'notes':notes,'checkpoints':checkpoints,'first_frame':notes[1]['frame'],'last_frame':notes[-1]['frame'],
            'steps':n-1,'hits':sum(not(v['flags']&8) for v in notes[1:]),'beat_frames':round(beat*FPS),
            'first_arc_frames':round(arc(fs[0])*beat/fs[0]['speed']*FPS)}
    if data.get('native_layout_version',0)>=2:result['native_layout_version']=data['native_layout_version']
    if data.get('neo_cosmos'):
        from neo_audio import hold_events
        result['neo_cosmos']=True
        result['neo_sound_events']=hold_events(data,notes)
        from neo_freeroam import compile_regions
        compile_regions(data,result)
        from neo_visuals import configure
        configure(data,result)
    return result,blob

def connected_track(chart,grid=1):
    notes=chart['notes']
    if grid>1:notes=[dict(n,x=round(n['x']/grid)*grid,y=round(n['y']/grid)*grid) for n in notes]
    width=1<<math.ceil(math.log2((max(n['x'] for n in notes)+200)/8))
    height=math.ceil((max(n['y'] for n in notes)+160)/8)
    # One ribbon, one outside contour, one shared seam per pair of tiles.
    # Never outline overlapping link/node primitives: that produced extra
    # boxes inside every tile in the earlier prototype.
    mask=Image.new('L',(width*8,height*8),0);md=ImageDraw.Draw(mask)
    points=[(p['x'],p['y']) for p in notes]
    def endpoint(p,q,sign):
        dx=q[0]-p[0];dy=q[1]-p[1];length=math.hypot(dx,dy)
        return (round(p[0]+sign*dx/length*12),round(p[1]+sign*dy/length*12))
    path=[endpoint(points[0],points[1],-1)]+points+[endpoint(points[-1],points[-2],-1)]
    md.line(path,fill=255,width=15,joint='curve')
    border=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(3)))
    im=Image.new('P',mask.size,0);im.paste(1,mask=mask);im.paste(3,mask=border)
    d=ImageDraw.Draw(im);seams=set()
    for p,q in zip(notes,notes[1:]):
        dx=q['x']-p['x'];dy=q['y']-p['y'];length=math.hypot(dx,dy)
        x=(p['x']+q['x'])/2;y=(p['y']+q['y'])/2
        nx=-dy/length*6;ny=dx/length*6
        ends=tuple(sorted(((round(x+nx),round(y+ny)),(round(x-nx),round(y-ny)))))
        if ends not in seams:d.line(ends,fill=2,width=1);seams.add(ends)
    pixels=np.array(im);tiles=[bytes(32)];lookup={tiles[0]:0};tilemap=[]
    for y in range(height):
        for x in range(width):
            tile=bytes(common.tile_bytes(pixels[y*8:y*8+8,x*8:x*8+8]))
            if tile not in lookup:lookup[tile]=len(tiles);tiles.append(tile)
            tilemap.append(lookup[tile]|(2<<10))
    if len(tiles)>1024 and grid<4:return connected_track(chart,grid*2)
    assert len(tiles)<=1024,(chart['id'],len(tiles))
    im.putpalette([0,0,0,42,54,70,167,194,218,235,244,255]+[0]*756)
    im.save(OUT/f'level{chart["id"]}-track.png')
    chart.update(map_width=width,map_height=height,visual_grid=grid,track_tiles=len(tiles))
    # Sparse rows are run-length encoded. The selected map fits in bank $7F;
    # the runtime decodes only the 32 visible rows, rather than storing a large
    # mostly-empty world map or consuming sprites for every rectangle.
    compressed=compress_map(tilemap,width,height)
    assert len(compressed)<65536
    chart['map_rle_bytes']=len(compressed)
    return b''.join(tiles),compressed

def compress_map(tilemap,width,height):
    # Sparse row headers index only occupied 32-tile spans. Identical spans
    # and identical row headers share storage, including blank space.
    rows=[];spans={};chunks=width//32
    assert chunks<256
    for y in range(height):
        row=tilemap[y*width:(y+1)*width]
        occupied=[k for k in range(chunks) if any(t&0x2000 or t&1023 for t in row[k*32:k*32+32])]
        if not occupied:rows.append((0,()));continue
        first,last=occupied[0],occupied[-1];keys=[]
        for chunk in range(first,last+1):
            span=row[chunk*32:chunk*32+32];encoded=bytearray();start=0
            while start<32:
                end=start+1
                while end<32 and span[end]==span[start]:end+=1
                encoded+=struct.pack('<BH',end-start,span[start]);start=end
            encoded.append(0);key=bytes(encoded)
            spans.setdefault(key,None);keys.append(key)
        rows.append((first,tuple(keys)))
    align=lambda n:(n+3)&~3
    cursor=align(height*2);row_locations={}
    for row in rows:
        if row not in row_locations:
            row_locations[row]=cursor;cursor+=align(2+len(row[1])*2)
    for key in spans:spans[key]=cursor;cursor+=align(len(key))
    assert cursor<262144,('Sparse map capacity',width,height,cursor)
    blob=bytearray(cursor);blob[:height*2]=common.word_data([row_locations[r]//4 for r in rows])
    for (first,keys),where in row_locations.items():
        raw=bytes((first,len(keys)))+common.word_data([spans[k]//4 for k in keys]);blob[where:where+len(raw)]=raw
    for key,where in spans.items():blob[where:where+len(key)]=key
    return bytes(blob)

def compress_track_chr(raw,mode7=False):
    # Track pixels use only two planes. Omit the empty upper planes, then
    # PackBits-compress the remaining bytes; the loader expands in WRAM.
    if not mode7:assert all(raw[i:i+16]==bytes(16) for i in range(16,len(raw),32))
    data=raw if mode7 else b''.join(raw[i:i+16] for i in range(0,len(raw),32));out=bytearray();i=0
    while i<len(data):
        run=1
        while i+run<len(data) and data[i+run]==data[i] and run<128:run+=1
        if run>=3:out.extend((0x80|(run-1),data[i]));i+=run;continue
        start=i;i+=run
        while i<len(data) and i-start<128:
            if i+2<len(data) and data[i]==data[i+1]==data[i+2]:break
            i+=1
        out.append(i-start-1);out.extend(data[start:i])
    return bytes(out)

def encode_music(chart, rate=RATE, suffix=""):
    from embedded_hit_audio import mix_hits, fingerprint
    n=chart['id'];wav=ROOT/f'assets/private/{n}-X.wav';raw=OUT/f'level{n}{suffix}.pcm';brr=OUT/f'level{n}{suffix}.brr'
    with wave.open(str(wav),'rb') as f:duration=f.getnframes()/f.getframerate()
    prefix=chart['countdown']*60/chart['bpm'] if chart['separate_countdown'] else 0
    stop=max(duration+prefix+0.25,chart['notes'][-1]['time']+0.75)
    chart['duration']=stop;chart['end_frame']=round(stop*FPS)
    settings={'source':hashlib.sha256(wav.read_bytes()).hexdigest(),'percussion_mix':fingerprint(chart),'prefix':prefix,'end':stop,
              'rate':rate,'gain':0.78,'hat_offset':chart['offset'] if prefix else None,
              'encoder':hashlib.sha256((ROOT/'tools/brr_encode.c').read_bytes()).hexdigest(),
              'seek_blocks':sorted({round(c['block']*rate/RATE) for c in chart['checkpoints']})}
    manifest=OUT/f'level{n}{suffix}-audio.json'
    if brr.exists() and manifest.exists() and json.loads(manifest.read_text())==settings:return brr.read_bytes()
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-af','volume=0.78','-ac','1','-ar',str(rate),'-f','s16le',str(raw)],check=True)
    pcm=np.fromfile(raw,dtype='<i2').astype(float)
    pcm=np.r_[np.zeros(round(prefix*rate)),pcm,np.zeros(round(2.5*rate))]
    needed=math.ceil((stop+RING/2*16/9/rate+0.1)*rate)
    if len(pcm)<needed:pcm=np.pad(pcm,(0,needed-len(pcm)))
    if prefix:
        # Count-in hats are separate in these native charts; bake them into
        # the cartridge stream at the same positions used by the original.
        rng=np.random.default_rng(75)
        count=round(rate*.045);hat=rng.uniform(-1,1,count)*np.exp(-np.arange(count)/(rate*.008))*6500
        for k in range(chart['countdown']):
            start=round((chart['offset']+k*60/chart['bpm'])*rate)
            if start>=0:pcm[start:start+count]+=hat
    hit_report = mix_hits(pcm, chart, rate)
    (OUT/f'level{n}{suffix}-hit-mix.json').write_text(json.dumps(hit_report,indent=2))
    np.clip(pcm,-32768,32767).astype('<i2').tofile(raw)
    encoder=ROOT/'.tools/brr_encode.exe'
    if not encoder.exists() or encoder.stat().st_mtime<(ROOT/'tools/brr_encode.c').stat().st_mtime:
        subprocess.run(['gcc','-O3',str(ROOT/'tools/brr_encode.c'),'-lm','-o',str(encoder)],check=True)
    seeks=OUT/f'level{n}{suffix}-seeks.txt';seeks.write_text('\n'.join(map(str,settings['seek_blocks'])))
    subprocess.run([str(encoder),str(raw),str(brr),str(seeks)],check=True)
    manifest.write_text(json.dumps(settings,indent=2))
    return brr.read_bytes()

def ui_assets(pack_title='MAIN WORLDS 1-12',mode7=False):
    common.graphics()
    palette=bytearray((ROOT/'build/palette.bin').read_bytes())
    colors=[(0,0,0),(42,54,70),(167,194,218),(235,244,255)]+[(0,0,0)]*12
    palette[64:96]=common.word_data([(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in colors])
    for index,factor in [(3,1/3),(4,2/3)]:
        dim=[tuple(round(c*factor) for c in rgb) for rgb in colors]
        palette[index*32:(index+1)*32]=common.word_data([(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in dim])
    guide_colors=[(0,0,0),(7,12,20),(19,34,47),(75,98,116),(54,153,186),(116,225,245),(255,211,85),(246,250,255)]+[(0,0,0)]*8
    palette[480:512]=common.word_data([(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in guide_colors])
    white=[(0,0,0)]+[(round(90+i*23),)*3 for i in range(1,8)]+[(0,0,0)]*8
    palette[448:480]=common.word_data([(r>>3)|((g>>3)<<5)|((b>>3)<<10) for r,g,b in white])
    # Recover the indexed OBJ sheet, add unambiguous rabbit/snail/spiral icons.
    sheet=Image.new('P',(128,128),0)
    old=(ROOT/'build/objects.chr').read_bytes();pix=np.zeros((128,128),dtype=np.uint8)
    for tile in range(256):
        tx=tile%16*8;ty=tile//16*8;src=old[tile*32:(tile+1)*32]
        for y in range(8):
            for x in range(8):
                pix[ty+y,tx+x]=sum(((src[(bit//2)*16+y*2+bit%2]>>(7-x))&1)<<bit for bit in range(4))
    sheet=Image.fromarray(pix);d=ImageDraw.Draw(sheet)
    def symbol(tile,kind):
        x=tile%16*8;y=tile//16*8
        if kind=='rabbit':
            d.ellipse((x+3,y+6,x+11,y+13),fill=6);d.ellipse((x+8,y+4,x+13,y+10),fill=7)
            d.line((x+9,y+5,x+9,y),fill=6,width=2);d.line((x+12,y+5,x+14,y),fill=7,width=2)
            d.ellipse((x,y+7,x+4,y+11),fill=5);d.rectangle((x+5,y+12,x+13,y+14),fill=5)
            d.point((x+12,y+6),fill=1)
        elif kind=='snail':
            d.ellipse((x+1,y+10,x+14,y+14),fill=6);d.ellipse((x+2,y+3,x+11,y+12),fill=3,outline=7)
            d.arc((x+4,y+5,x+9,y+10),20,320,fill=6,width=1)
            d.ellipse((x+11,y+8,x+14,y+13),fill=5)
            d.line((x+12,y+9,x+11,y+5),fill=6);d.line((x+14,y+9,x+15,y+5),fill=6)
            d.point((x+11,y+4),fill=7);d.point((x+15,y+4),fill=7)
        else:
            d.arc((x+2,y+2,x+13,y+13),25,320,fill=6,width=2)
            d.arc((x+5,y+5,x+10,y+10),80,350,fill=5,width=2)
            d.polygon([(x+10,y),(x+15,y+2),(x+11,y+6)],fill=7)
    symbol(32,'rabbit');symbol(34,'snail');symbol(36,'reverse')
    flip=sheet.crop((32,16,48,32)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    sheet.paste(flip,(48,16))
    # Tile landings: a persistent center mark and three fading flash frames.
    for tile,inset,color in [(40,6,3),(42,1,7),(44,2,5),(46,4,3)]:
        x=tile%16*8;y=tile//16*8
        if tile==40:d.polygon([(x+7,y+6),(x+9,y+8),(x+7,y+10),(x+5,y+8)],fill=color)
        else:d.ellipse((x+inset,y+inset,x+15-inset,y+15-inset),outline=color)
    # Three sizes/brightnesses for each orb's sampled motion history.
    for tile,r,color in [(64,3,4),(66,2,3),(68,1,2)]:
        x=tile%16*8;y=tile//16*8
        d.ellipse((x+8-r,y+8-r,x+8+r,y+8+r),fill=color)
    d.line((55,35,55,41),fill=7,width=2);d.point((55,44),fill=7)
    d.polygon([(49,37),(52,34),(52,40)],fill=6);d.polygon([(62,42),(59,39),(59,45)],fill=6)
    d.rectangle((67,35,70,44),fill=6);d.rectangle((74,35,77,44),fill=6)
    # Checkpoint flag: the activated version has a filled flag and bright base.
    for tile,active in [(74,False),(76,True)]:
        x=tile%16*8;y=tile//16*8
        d.line((x+4,y+2,x+4,y+14),fill=7,width=2)
        d.polygon([(x+6,y+2),(x+13,y+3),(x+11,y+7),(x+6,y+6)],fill=6 if active else 2,outline=7)
        d.line((x+1,y+14,x+9,y+14),fill=6 if active else 3)
    presentation.streak_tiles(sheet,compact=mode7)
    for radius in range(1,5):
        tile=63+radius;x=tile%16*8;y=tile//16*8
        d.rectangle((x,y,x+7,y+7),fill=0)
        for yy in range(8):
            for xx in range(8):
                distance=math.hypot(xx-3.5,yy-3.5)
                if distance<=radius:d.point((x+xx,y+yy),fill=max(2,min(7,round(7-4*distance/radius))))
        tile=[68,69,80,81][radius-1];x=tile%16*8;y=tile//16*8
        d.rectangle((x,y,x+7,y+7),fill=0)
        r=min(3.5,radius)
        d.ellipse((round(x+3.5-r),round(y+3.5-r),round(x+3.5+r),round(y+3.5+r)),outline=5)
    pix=np.array(sheet);objects=b''.join(common.tile_bytes(pix[y*8:y*8+8,x*8:x*8+8]) for y in range(16) for x in range(16))
    hud=presentation.hud
    common_lines=[(3,'COMBO 0000  BEST 0000  000%',4)]
    title=[(1,'A DANCE OF FIRE AND ICE',7),(3,pack_title,5)]
    title += [(16,'UP / DOWN SELECT A LEVEL',4),(19,'START TO PLAY',7),(21,'X PRACTICE    Y WATCH',5),
              (23,'SELECT CALIBRATE  B OPTIONS',6),(24,'L / R SPEED: 1.0X',5),(26,'OFFSET: +00 FRAMES  < >',4)]
    huds=[hud(title),hud(common_lines),
          hud(common_lines+[(21,'RHYTHM LOST',6),(24,'START TO RETRY',7),(26,'SELECT TO MENU',4)]),
          hud([(1,'LEVEL COMPLETE!',5),(5,'JUDGMENT       COUNT  POINTS  ',4),
               (18,'   TOTAL SCORE'.ljust(32),5),(20,'   ACCURACY'.ljust(32),7),(22,'                 SPEED'.ljust(32),4),(24,'START RETRY  SELECT MENU',4)]),
          hud(common_lines+[(10,'PAUSED',7),(13,'START TO RESUME',5),(16,'SELECT TO RETURN TO TITLE',4)]),
          hud([(2,'AUDIO CALIBRATION',7),(5,'TAP ALONG WITH THE CLICK',5),(7,'A B X Y L R / D-PAD TO TAP',4),
               (17,'SAMPLES 000 / 016',7),(21,'KEEP TAPPING AT A STEADY BEAT',4),(24,'START RETRY   SELECT CANCEL',4)]),
          hud([(2,'CALIBRATION COMPLETE',5),(7,'RECOMMENDED OFFSET',7),(10,'+00 FRAMES',6),
               (16,'A APPLY    X TRY AGAIN',7),(20,'< > ADJUST    SELECT CANCEL',4)]),
          hud([(2,'OPTIONS',7),(6,'TIME ATTACK',4),(8,'TRACK SPEED',4),(10,'HIT TIMING',4),
               (12,'FIRE ORB',4),(14,'ICE ORB',4),(16,'AUDIO OFFSET',4),(20,'UP / DOWN SELECT  < > CHANGE',4),
               (22,'A ON OFFSET TO CALIBRATE',4),(25,'B / START / SELECT BACK',5)]),
          hud([(1,'RUN RESULTS',6),(5,'JUDGMENT       COUNT  POINTS  ',4),(18,'   TOTAL SCORE'.ljust(32),5),(20,'   ACCURACY'.ljust(32),7),
               (22,'                 SPEED'.ljust(32),4),(24,'START RETRY  SELECT MENU',4),(26,'SELECT MENU',4)])]
    for i,data in enumerate(huds):(OUT/f'hud{i}.bin').write_bytes(data)
    from graphics_sources import write_graphics
    return write_graphics(OUT, "mode7" if mode7 else "campaign")


def pack_payload(assets,charts,msu=False,rom_data=False,sa1=False):
    if any(c.get('neo_cosmos') for c in charts):
        assets['neo_objects']=(ROOT/'assets/graphics/mode7/freeroam.chr').read_bytes()
        assert len(assets['neo_objects'])==2048
    for c in charts:
        if c.get('neo_cosmos') and any(n.get('freeroam') for n in c['notes']) and not c.get('neo_freeroam_runtime'):
            raise ValueError(f"{c['code']}: free-roam runtime is not implemented; refusing to package it as an ordinary fixed track")
    resident=[c for c in charts if c.get('resident_pattern_format')]
    assert len(resident)<=1,'One paged resident dictionary is supported per cartridge'
    zero_pauses=[]
    if sa1 and not rom_data and len(charts)>61:
        for c in charts:
            name=f'chart{c["id"]}';size=len(c['notes'])*2
            absent=not any(assets[name][-size:]);zero_pauses.append(absent)
            if absent:assets[name]=assets[name][:-size]
        (OUT/'zero-pauses.json').write_text(json.dumps(dict(zip((str(c['id']) for c in charts),zero_pauses))))
        (OUT/'zero_pause_tables.inc').write_text('zero_pause_tables: .byte '+','.join(str(int(v)) for v in zero_pauses)+',0\n')
    from hit_sound_assets import add_assets
    hit_banks=add_assets(assets,charts,OUT)
    # Keep the sound driver in ordinary ROM space, leaving the 32-KiB
    # executable bank available for the renderer and input handling.
    from spc_campaign import assemble
    assets['spc_driver']=assemble(calibration_period=125)
    (OUT/'spc_driver.bin').write_bytes(assets['spc_driver'])
    if msu:
        from animation_assets import coordinate_index
        for c in charts:
            name=f'visibility_index{c["id"]}'
            assets[name]=coordinate_index(c,wrapped=bool(resident))
            (OUT/(name+'.bin')).write_bytes(assets[name])
    # ExHiROM: C0-FF address the first 4 MiB; 40-7D address the upper region.
    # Reserve the reset/code/header bank at file $408000..40FFFF. The top two
    # banks can be reached through their 3E/3F upper-half mirrors.
    free=[(0,0x8000),(0x10000,0x400000),(0x400000,0x408000),(0x410000,0x7E0000),
          (0x7E8000,0x7F0000),(0x7F8000,0x800000)]
    if sa1:
        # The CPU's FastROM code mirror occupies the first 32 KiB of
        # physical bank $20. Keep it out of both static assets and streams.
        free=[(0x12000 if any(c.get('neo_cosmos') for c in charts) else 0x10000,0x200000),(0x208000,0x800000 if rom_data else 0x400000)]
        if resident and not rom_data:free.append((0x400000,0x800000))
    image=bytearray(0x800000);loc={};shared_blobs={}
    def address(offset):
        if offset<0x400000:return offset+0xC00000
        if offset>=0x7E8000 and not sa1:return offset-0x400000
        return offset
    for name,blob in sorted(assets.items(),key=lambda p:(int(sa1 and p[0].startswith('romdata')),-len(p[1]))):
        static_future=name.startswith('resident_future') and len(blob)<=32768
        # A different level can use the C0 window after its loader restores
        # page zero. Keep common graphics/audio and the resident level's
        # own chart data outside C0, since its worker pages that window.
        other_level_data=bool(resident and re.fullmatch(r'(chart|track_map|visibility_index)\d+',name)
                              and int(re.search(r'\d+$',name).group())!=resident[0]['id'])
        # Banks of percussion samples and initial graphics are immutable and
        # often identical across charts. Share their ROM bytes in large packs.
        share=next((prefix for prefix in ('hitbank','hitnotes','track_chr') if name.startswith(prefix)),None) if sa1 and len(charts)>61 else None
        key=(share,blob) if share else None
        if key is not None and key in shared_blobs:
            loc[name]=shared_blobs[key];continue
        if share=='hitnotes':
            prior=next((address for (kind,data),address in shared_blobs.items() if kind==share and data.startswith(blob)),None)
            if prior is not None:
                loc[name]=prior;continue
        for i,(start,end) in enumerate(free):
            # Sequential ROM data must use full banks with linear CPU
            # addresses; the final 32-KiB mirrors have unmapped lower halves.
            if name.startswith('romdata') and start>=0x7E0000 and not sa1:continue
            # Neo resident cartridges need two long audio/animation spans.
            # Cluster their small static tables above the FastROM mirror;
            # placing them at 1 MiB unnecessarily splits the lower 2 MiB.
            static_minimum=0x208000 if sa1 and rom_data and any(c.get('neo_cosmos') for c in resident) else 0x100000
            minimum=(0x400000 if name.startswith('resident_') and not static_future else
                     static_minimum if resident and not other_level_data and not name.startswith('romdata') else 0)
            if any(c.get('native_stream_format') and name==f'visibility_index{c["id"]}' for c in charts):minimum=0x208000
            aligned=(max(start,minimum)+1)&~1
            if name.startswith('patterns'):aligned=(aligned+15)&~15
            if not name.startswith(('music','timeline','visibility_index','track_map','patterns','romdata')) and (aligned&65535)+len(blob)>65536:
                aligned=(aligned+65535)&~65535
            limit=min(end,0x300000) if sa1 and rom_data and not name.startswith(('romdata','resident_')) else end
            if resident and not name.startswith(('romdata','resident_')):limit=min(limit,0x300000 if rom_data else 0x400000)
            if static_future:limit=min(limit,0x300000 if rom_data else 0x400000)
            if aligned+len(blob)<=limit:
                image[aligned:aligned+len(blob)]=blob;loc[name]=address(aligned)
                if key is not None:shared_blobs[key]=loc[name]
                free[i:i+1]=[(a,z) for a,z in [(start,aligned),(aligned+len(blob),end)] if a<z];break
        else:raise RuntimeError(f'8 MiB cartridge is full while placing {name} ({len(blob)} bytes); {sum(end-start for start,end in free)} bytes free; {sum(len(value) for key,value in assets.items() if key not in loc)} bytes unplaced')
    if hit_banks:
        sound_banks={r['id']:r for r in json.loads((OUT/'hit-sounds.json').read_text())}
        start=loc['hitdescriptors']-0xC00000 if loc['hitdescriptors']>=0xC00000 else loc['hitdescriptors']
        for i,c in enumerate(charts):
            row=b''.join(loc[k+str(c['id'])].to_bytes(3,'little') for k in ('hitnotes','hitbank'))
            row+=struct.pack('<HH',*sound_banks[c['id']]['packet_counts'])+bytes(6)
            image[start+16*i:start+16*i+16]=row
    (OUT/'payload0.bin').write_bytes(image[:0x408000])
    (OUT/'payload1.bin').write_bytes(image[0x410000:])
    (OUT/'placements.json').write_text(json.dumps(loc,indent=2))
    defs=[f'{name.upper()}_ADDR = ${addr:06X}' for name,addr in loc.items() if name in ('palette','objects','background_chr','background_map','font','neo_objects')]
    defs.append('HITS_IN_MUSIC = 1')
    if any(c.get('neo_cosmos') for c in charts):defs.append('NEO_BUILD = 1')
    defs += [f'BACKGROUND_CHR_BYTES = {len(assets["background_chr"])}']
    defs += [f'SPC_DRIVER_ADDR = ${loc["spc_driver"]:06X}',f'SPC_DRIVER_BYTES = {len(assets["spc_driver"])}']
    defs += [f'LEVEL_COUNT = {len(charts)}']
    if zero_pauses:defs+=['ZERO_PAUSE_TABLES = 1']
    if hit_banks:defs+=['HIT_SOUND_BANKS = 1',f'HIT_SOUND_DESCRIPTORS_ADDR = ${loc["hitdescriptors"]:06X}']
    if all(c.get('compiled_reference_sets') for c in charts):defs+=['COMPILED_REFERENCE_SETS = 1']
    large=msu and any(len(c['notes'])>3072 for c in charts)
    if large:
        assert sa1,'Large charts require the SA-1 cartridge RAM layout'
        defs+=['LARGE_CHART_BUILD = 1']
    defs += [f'MAX_NOTE_CAPACITY = {4352 if large else 3072 if msu else 2048}']
    defs += [f'MAP_OFFSET_SHIFT = {charts[0].get("map_offset_shift",0)}']
    if msu:defs+=['MSU_BUILD = 1',f'MSU_DATA_VERSION = {20 if any(c["id"]>=62 for c in charts) else 19 if any(c.get("adaptive_raster") for c in charts) else 18 if any(c.get("mode7_zoom_enabled") for c in charts) else 17 if any(c.get("camera_position_events",0) for c in charts) else 16 if any(c.get("native_layout_version",0)>=2 for c in charts) else 15 if any(c.get("track_separators_version") for c in charts) else 14 if any(c.get("opacity_curve_version") for c in charts) else 13 if any(c.get("camera_rotation_versions") for c in charts) else 12}']
    if rom_data:defs+=['ROM_DATA_BUILD = 1']
    if sa1:defs+=['SA1_BUILD = 1','SA1_FASTROM_MIRROR = 1']
    if resident:
        defs+=['ROM_PACKED_COORDS = 1']
        c=resident[0];n=c['id']
        defs += [f'ROM_PATTERN_ADDR = ${loc[f"resident_raw{n}"]:06X}',
                 f'ROM_PATTERN_LEVEL = {charts.index(c)}',
                 f'ROM_PATTERN_COUNT = {len(assets[f"resident_raw{n}"])//64}',
                 'ROM_PATTERN_PAGED = 1','ROM_PATTERN_NO_SPILL = 1',
                 f'ROM_FUTURE_ADDR = ${loc[f"resident_future{n}"]:06X}',
                 f'ROM_FUTURE_COUNT = {len(assets[f"resident_future{n}"])//8}']
        if loc[f'resident_future{n}']>=0xD00000:defs+=['ROM_FUTURE_STATIC = 1']
        if c.get('direct_pattern_until'):defs += [f'ROM_DIRECT_UNTIL = {c["direct_pattern_until"]}']
        if c.get('native_stream_format'):
            defs += [f'ROM_NATIVE_ADDR = ${loc[f"resident_animation{n}"]:06X}',
                     f'ROM_NATIVE_COORDS = ${loc[f"visibility_index{n}"]:06X}',
                     f'ROM_NATIVE_CELLS = {c["visibility_cells"]}']
        if c.get('wrapped_mode7_map'):defs+=['ROM_WRAP_MAP = 1']
    (OUT/'addresses.inc').write_text('\n'.join(defs)+'\n')
    descriptors=[]
    # 32 bytes per descriptor, copied/decoded by load_selected_level.
    for c in charts:
        n=c['id'];desc=bytearray()
        for name in (f'chart{n}',f'music{n}',f'track_chr{n}',f'track_map{n}'):
            desc+=loc[name].to_bytes(3,'little')
        desc+=struct.pack('<HHHHHHH',c['steps'],c['first_frame'],c['end_frame'],c['beat_frames'],
                          c['track_tiles']*(64 if c.get('mode7') else 32),min(65535,len(assets[f'track_map{n}'])),c['map_height'])
        desc+=struct.pack('<H',c['first_arc_frames'])
        desc+=loc[f'checkpoints{n}'].to_bytes(3,'little')+bytes([len(c['checkpoints'])]);descriptors.append(desc)
        checkpoint_data=bytearray()
        for cp in c['checkpoints']:
            checkpoint_data+=struct.pack('<HHH',cp['trigger'],cp['floor'],cp['origin_frame'])
            checkpoint_data+=((0 if msu else loc[f'music{n}'])+cp['block']*9).to_bytes(3,'little')
            checkpoint_data+=struct.pack('<HHB',cp['ready_frame'],cp['beat_frames'],0)
        # These small tables were reserved before packing; fill their addresses.
        offset=loc[f'checkpoints{n}'];offset=offset-0xC00000 if offset>=0xC00000 else offset+0x400000 if 0x3E8000<=offset<0x400000 else offset
        image[offset:offset+len(checkpoint_data)]=checkpoint_data
        (OUT/f'checkpoints{n}.bin').write_bytes(checkpoint_data or bytes(2))
    (OUT/'payload0.bin').write_bytes(image[:0x408000])
    (OUT/'payload1.bin').write_bytes(image[0x410000:])
    (OUT/'descriptors.bin').write_bytes(b''.join(descriptors))
    visibility_descriptors=bytearray()
    mechanics_descriptors=bytearray()
    for c in charts:
        n=c['id'];offsets=c.get('visibility_offsets',[])
        index=assets[f'visibility_index{n}'] if msu else b''.join((loc[f'timeline{n}']+o).to_bytes(3,'little') for o in offsets) or bytes(3)
        addr=loc[f'visibility_index{n}'];offset=addr-0xC00000 if addr>=0xC00000 else addr+0x400000 if 0x3E8000<=addr<0x400000 else addr
        image[offset:offset+len(index)]=index
        visibility_descriptors+=addr.to_bytes(3,'little')+struct.pack('<HB',c.get('visibility_cells',0),int(c.get('moving_tiles',False) and not msu))
    (OUT/'visibility_descriptors.bin').write_bytes(visibility_descriptors)
    if msu:(OUT/'mechanics_descriptors.bin').write_bytes(mechanics_descriptors)
    (OUT/'payload0.bin').write_bytes(image[:0x408000])
    (OUT/'payload1.bin').write_bytes(image[0x410000:])
    config='''MEMORY {
 ZP: start=$0000,size=$0100,type=rw;
 STATE: start=$1800,size=$0500,type=rw;
 PAY0: start=$800000,size=$408000,type=ro,file=%O,fill=yes;
 ROM: start=$008000,size=$7FB0,type=ro,file=%O,fill=yes,fillval=$FF;
 HDR: start=$00FFB0,size=$30,type=ro,file=%O,fill=yes;
 VEC: start=$00FFE0,size=$20,type=ro,file=%O,fill=yes;
 PAY1: start=$410000,size=$3F0000,type=ro,file=%O,fill=yes;
}
SEGMENTS {
 ZEROPAGE: load=ZP,type=zp;
 BSS: load=STATE,type=bss;
 PAYLOAD0: load=PAY0,type=ro;
 CODE: load=ROM,type=ro;
 RODATA: load=ROM,type=ro;
 HEADER: load=HDR,type=ro;
 VECTORS: load=VEC,type=ro;
 PAYLOAD1: load=PAY1,type=ro;
}
'''
    (OUT/'exhirom.cfg').write_text(config)
    if sa1:
        (OUT/'sa1_payload.bin').write_bytes(image[0x10000:])
        (OUT/'sa1.cfg').write_text('''MEMORY {
 ZP: start=$0000,size=$0100,type=rw;
 FASTIRAM: start=$003100,size=$0680,type=rw;
 POLLWRAM: start=$001000,size=$0800,type=rw;
 STATE: start=$1800,size=$0500,type=rw;
 ROM: start=$008000,size=$7FB0,type=ro,file=%O,fill=yes,fillval=$FF;
 HDR: start=$00FFB0,size=$30,type=ro,file=%O,fill=yes;
 VEC: start=$00FFE0,size=$20,type=ro,file=%O,fill=yes;
 WORKER: start=$018000,size=$7000,type=ro,file=%O,fill=yes;
 CAMERAEXT: start=$01F000,size=$1000,type=ro,file=%O,fill=yes;
 PAY: start=$810000,size=$7F0000,type=ro,file=%O,fill=yes;
}
SEGMENTS {
 ZEROPAGE: load=ZP,type=zp;
 BSS: load=STATE,type=bss;
 CODE: load=ROM,type=ro;
 FASTNMI: load=ROM,run=FASTIRAM,type=ro,define=yes;
 FASTWRAM: load=ROM,run=POLLWRAM,type=ro,define=yes;
 RODATA: load=ROM,type=ro;
 HEADER: load=HDR,type=ro;
 VECTORS: load=VEC,type=ro;
 SA1CODE: load=WORKER,type=ro;
 CAMERA: load=CAMERAEXT,type=ro;
 SA1PAYLOAD: load=PAY,type=ro;
}
''')

def common_tables(charts=None, adaptive_audio=False):
    values=[]
    scale=round(FPS*.004*65536)
    recentered=bool(charts and charts[0].get('mode7'))
    baseline=8 if recentered else 0
    baseline_ticks=round(baseline/FPS/.004)
    limit=30 if recentered else 8
    divisor=3 if recentered else 16
    # Twelve trimmed errors, then /4, fit -561..561. Keep the legacy
    # sixteen-sample table intact; the recentered table needs only 1152 bytes.
    result_bias=576 if recentered else 1024
    result_count=1152 if recentered else 2048
    tables=[('sin24',[round(math.sin(i*math.pi/128)*24)&255 for i in range(256)],False),
            ('cos24',[round(math.cos(i*math.pi/128)*24)&255 for i in range(256)],False),
            ('cal_results',[max(-limit,min(limit,round(((i-result_bias)/divisor+baseline_ticks)*FPS*.004)-baseline))&255 for i in range(result_count)],False)]
    if recentered:
        tables.append(('calibration_centers',[(baseline_ticks+round(offset/FPS/.004))&65535 for offset in range(-limit,limit+1)],True))
    for name,nums,word in tables:
        values.append(name+':')
        for i in range(0,len(nums),16):values.append((' .word ' if word else ' .byte ')+','.join(str(v) for v in nums[i:i+16]))
    from official_catalog import WORLDS
    charts=charts or WORLDS[:12]
    placements=json.loads((OUT/'placements.json').read_text()) if (OUT/'placements.json').exists() else {}
    values.append('level_title_pointers: .word '+','.join('title'+str(i) for i in range(len(charts))))
    values.append('level_view_insets: .byte '+','.join(str(c.get('viewport_inset',0)) for c in charts))
    for i,c in enumerate(charts):
        from neo_catalog import display_code
        title=f'{display_code(c.get("code",str(c["id"])+"-X"))} {c["title"]}'[:28]
        values.append(f'title{i}: .byte "{title}",0')
    from menu_sets import tables as menu_tables,write_count as write_menu_count
    write_menu_count(OUT,[c['id'] for c in charts])
    (OUT/'tables.inc').write_text('\n'.join(values)+'\n'+presentation.tables(FPS,compact=charts[0].get('mode7',False),adaptive_audio=adaptive_audio)+menu_tables([c['id'] for c in charts]))
    from spc_campaign import assemble
    (OUT/'spc.bin').write_bytes(assemble(calibration_period=125))

def main():
    global OUT
    from official_catalog import PACKS
    from official_catalog import WORLDS
    from import_tech import TECH
    from import_community import COMMUNITY
    from neo_catalog import NEO
    ap=argparse.ArgumentParser();ap.add_argument('--pack',choices=[*PACKS,'master'],default='main');ap.add_argument('--out',type=Path);ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--chart-cache-only',action='store_true')
    ap.add_argument('--preview-tiles',type=int,choices=range(4,65),default=16)
    ap.add_argument('--past-tiles',type=int,choices=range(0,5),default=1)
    ap.add_argument('--fixed-tile-positions',action='store_true')
    ap.add_argument('--compact-graphics',action='store_true')
    ap.add_argument('--stable-color-quantization',action='store_true',help='Keep palette aliases consistent through authored color cycles')
    ap.add_argument('--material-capacity',type=int,choices=(1,3,6,12,24,48),default=None,help='Override the chart-specific palette capacity')
    ap.add_argument('--shared-contours',action='store_true')
    ap.add_argument('--camera-rotation',action='store_true')
    ap.add_argument('--adaptive-raster',action='store_true')
    ap.add_argument('--adaptive-motion-raster',action='store_true',help='Use half-resolution track textures during dense motion bursts')
    ap.add_argument('--raster-min-shift',type=int,choices=(0,1),default=0,help='Minimum texture reduction for charts whose dense transitions exceed atomic cache capacity')
    ap.add_argument('--camera-zoom',action='store_true',help='Experimental Mode 7 zoom; requires per-chart capacity and runtime PPU validation')
    ap.add_argument('--camera-position',action='store_true')
    ap.add_argument('--reuse-motion-phase',action='store_true')
    ap.add_argument('--viewport-inset',type=int,default=0,choices=(0,8),help='Letterbox for charts exceeding the Mode 7 pattern limit')
    ap.add_argument('--motion-step',type=int,choices=(1,2,4,8),default=None)
    ap.add_argument('--no-pcm',action='store_true',help='Generate the compressed master without full-size PCM tracks')
    args=ap.parse_args();msu=args.pack=='master'
    pack=dict(title='MSU-1 ALL WORLDS + TECH',levels=[m['id'] for m in WORLDS+TECH+COMMUNITY+NEO]) if msu else PACKS[args.pack]
    if args.levels:pack=dict(pack,levels=args.levels)
    OUT=args.out or (ROOT/'build/campaign' if args.pack=='main' else ROOT/f'build/packs/{args.pack}')
    OUT.mkdir(parents=True,exist_ok=True)
    if any(n>=66 and not (ROOT/f'assets/private/level{n}.json').exists() for n in pack['levels']):
        subprocess.run([sys.executable,str(ROOT/'tools/import_neo.py')],check=True)
    if not all((ROOT/f'assets/private/level{n}.json').exists() and 'checkpoints' in json.loads((ROOT/f'assets/private/level{n}.json').read_text()) for n in pack['levels']):
        importer='import_campaign.py' if args.pack=='main' else 'import_official.py'
        subprocess.run([sys.executable,str(ROOT/'tools'/importer)],check=True)
    raw_charts=[json.loads((ROOT/f'assets/private/level{n}.json').read_text()) for n in pack['levels']]
    if msu and any(d.get('track_color_import')!=1 for d in raw_charts):
        subprocess.run([sys.executable,str(ROOT/'tools/import_colors.py')],check=True)
    if msu and any('camera_initial' not in d for d in raw_charts):
        subprocess.run([sys.executable,str(ROOT/'tools/import_camera.py')],check=True)
    if any('hidden_icons' not in d or ('track_settings' not in d and not all(k in d for k in ('native_track_effects','native_track_initial'))) for d in raw_charts):
        subprocess.run([sys.executable,str(ROOT/'tools/import_visibility.py')],check=True)
    charts=[];assets={} if args.chart_cache_only else ui_assets(pack['title'],mode7=msu);external_music={}
    if not args.chart_cache_only:(OUT/'pack.json').write_text(json.dumps(dict(pack,code=args.pack),indent=2))
    for n in pack['levels']:
        source=ROOT/f'assets/private/level{n}.json'
        motion_step=args.motion_step if args.motion_step is not None else (1 if n in (20,22,23,24,26) or n>=66 else 8)
        # These lossless raster-phase choices and stable color clustering
        # are part of the chart build, not private release-cache settings.
        reuse_motion_phase=args.reuse_motion_phase or n in (43,60)
        stable_color_quantization=args.stable_color_quantization or n in (22,58)
        material_capacity=args.material_capacity if args.material_capacity is not None else (12 if n==58 else 48)
        fingerprint=hashlib.sha256((ROOT/'tools/neo_visuals.py').read_bytes()+bytes([args.camera_position,args.camera_rotation,args.camera_zoom,args.adaptive_raster,args.raster_min_shift,args.adaptive_motion_raster,reuse_motion_phase,args.viewport_inset,stable_color_quantization])+source.read_bytes()+inspect.getsource(compile_chart).encode()+inspect.getsource(compress_map).encode()+
            (ROOT/'tools/neo_freeroam.py').read_bytes()+(ROOT/'tools/neo_mechanics.py').read_bytes()+(ROOT/'tools/neo_audio.py').read_bytes()+(ROOT/'tools/track_visibility.py').read_bytes()+(ROOT/'tools/viewport_cells.py').read_bytes()+(ROOT/'tools/track_geometry.py').read_bytes()+(ROOT/'assets/graphics/track-shapes.json').read_bytes()+(ROOT/'tools/track_motion.py').read_bytes()+(ROOT/'tools/track_events.py').read_bytes()+(ROOT/'tools/raster_phase.py').read_bytes()+(ROOT/'tools/track_mipmaps.py').read_bytes()+
            ((ROOT/'tools/track_readability.py').read_bytes()+(ROOT/'tools/track_patterns.py').read_bytes()+(ROOT/'tools/track_camera.py').read_bytes() if msu or n in (26,31) or n>=40 else b'')+
            ((ROOT/'tools/track_colors.py').read_bytes() if msu else b'')+bytes([msu,1,args.preview_tiles,args.past_tiles,args.fixed_tile_positions,material_capacity,args.shared_contours,motion_step])+ (b'compact' if args.compact_graphics else b'')).hexdigest()
        stamp=OUT/f'level{n}-build.json'
        names=[f'{a}{n}' for a in ('chart','track_chr','track_map','timeline','visibility_index','checkpoints')]
        cached_metadata=json.loads((OUT/f'level{n}.json').read_text()) if stamp.exists() else {}
        depth=cached_metadata.get('readability_window',{})
        valid_depth=not msu or cached_metadata.get('authored_visibility') is True
        if valid_depth and stamp.exists() and json.loads(stamp.read_text())==fingerprint and all((OUT/(a+'.bin')).exists() for a in names):
            c=json.loads((OUT/f'level{n}.json').read_text());charts.append(c)
            for a in names:assets[a]=(OUT/(a+'.bin')).read_bytes()
            if msu:
                from animation_assets import generate
                c['compiled_reference_sets']=True
                generate(OUT,c,assets[f'timeline{n}'],(OUT/f'patterns{n}.bin').read_bytes())
                assets[f'track_map{n}']=(OUT/f'track_map{n}.bin').read_bytes()
                assets[f'timeline{n}']=bytes(2)
                size=len(c['notes']);original=assets[f'chart{n}']
                assets[f'chart{n}']=original[:11*size]+bytes(note_control(v) for v in c['notes'])+original[12*size:]
                (OUT/f'level{n}.json').write_text(json.dumps(c,indent=2))
            music=encode_music(c);external_music[n]=music;assets[f'music{n}']=bytes(2) if msu else music
            print(c['code'],'cached track assets',flush=True);continue
        data=json.loads((ROOT/f'assets/private/level{n}.json').read_text());c,blob=compile_chart(data)
        if msu:
            if n in (20,23,26,60):c['precise_viewport_cells']=True
            c['mode7']=True
            c['compiled_reference_sets']=True
            c['motion_step']=motion_step
            c['reuse_motion_phase']=reuse_motion_phase
            c['viewport_inset']=args.viewport_inset
            c['adaptive_motion_raster']=args.adaptive_motion_raster
            c['authored_material_capacity']=material_capacity
            c['stable_color_quantization']=stable_color_quantization
            if args.shared_contours:c['shared_track_contour']=True
            if args.compact_graphics:
                c.update(constrained_graphics=True,readability_foreground=0,readability_detail=0,nearby_motion_only=True,pattern_batch_budget=64)
            from track_camera import camera_schedule
            camera_schedule(data,c)
            if args.camera_rotation:
                from track_camera import rotation_schedule
                rotation_schedule(data,c)
            neo_camera=c.get('neo_cosmos') and c['id'] in (68,70,73)
            if args.camera_zoom or args.adaptive_raster or neo_camera:
                from track_camera import mode7_zoom_schedule
                if neo_camera:
                    # Native camera half-height is five Unity units. Preserve
                    # that vertical field of view in our 144-line play area.
                    c['camera_zoom_versions']=[[f,round(z*10/9),round(inv*9/10)] for f,z,inv in c['camera_zoom_versions']]
                elif not args.camera_zoom:c['camera_zoom_versions']=[[0,256,256]]
                c['adaptive_raster']=args.adaptive_raster
                c['raster_min_shift']=args.raster_min_shift
                mode7_zoom_schedule(c)
                c['authored_zoom_enabled']=args.camera_zoom or bool(neo_camera)
        from track_visibility import visibility_schedule,animated_track
        from track_motion import motion_schedule
        initial,changes=visibility_schedule(data,c)
        authored=(initial,changes)
        motion=motion_schedule(data,c)
        if args.fixed_tile_positions:
            motion={0:motion[0]} if 0 in motion else {}
            c['standalone_fixed_tile_positions']=True
            c['simplified_depth']=True
        if msu:
            from track_readability import depth_schedule
            c['readability_preview']=args.preview_tiles
            c['readability_past']=args.past_tiles
            initial,changes=depth_schedule(c,initial,changes,motion,camera_data=data if args.camera_position else None)
            c['allow_pattern_cache']=True
        if changes or motion or any(a!=3 for a in initial):tiles,tilemap,timeline=animated_track(c,initial,changes,motion=motion,color_data=data if msu else None,authored=authored)
        else:tiles,tilemap=connected_track(c);timeline=bytes(2)
        pattern_data=c.pop('_pattern_data',bytes(16))
        if msu:(OUT/f'patterns{n}.bin').write_bytes(pattern_data)
        blob=common.word_data([v['x']+(v.get('position_track_offset',[0,0])[0] if not v.get('stick_to_floor',True) else 0) for v in c['notes']])+common.word_data([v['y']+(v.get('position_track_offset',[0,0])[1] if not v.get('stick_to_floor',True) else 0) for v in c['notes']])+blob[4*len(c['notes']):]
        if msu:
            size=len(c['notes']);assert size<=4352
            blob=blob[:11*size]+bytes(note_control(v) for v in c['notes'])+blob[12*size:]
        c['map_offset_shift']=2
        assets[f'timeline{n}']=timeline
        (OUT/f'timeline{n}.bin').write_bytes(timeline)
        assets[f'visibility_index{n}']=bytes(max(3,(c.get('visibility_cells',0) if msu else len(c.get('visibility_offsets',[])))*3))
        assets[f'chart{n}']=blob;assets[f'track_chr{n}']=compress_track_chr(tiles,msu);assets[f'track_map{n}']=tilemap
        music=encode_music(c);external_music[n]=music
        assets[f'music{n}']=bytes(2) if msu else music;charts.append(c)
        assets[f'checkpoints{n}']=bytes(max(2,len(c['checkpoints'])*14))
        (OUT/f'level{n}.json').write_text(json.dumps(c,indent=2))
        for a in names:(OUT/(a+'.bin')).write_bytes(assets[a])
        if msu:
            from animation_assets import generate
            generate(OUT,c,timeline,pattern_data)
            assets[f'track_map{n}']=(OUT/f'track_map{n}.bin').read_bytes()
            assets[f'timeline{n}']=bytes(2)
        (OUT/f'level{n}.json').write_text(json.dumps(c,indent=2))
        stamp.write_text(json.dumps(fingerprint))
        print(f'{c["code"]}: {c["hits"]} hits, {c["notes"][-1]["time"]:.3f}s last hit, '
              f'{c["track_tiles"]} track tiles, {len(tilemap)} map bytes, {len(assets[f"music{n}"])} music bytes',flush=True)
    if args.chart_cache_only:return
    (OUT/'manifest.json').write_text(json.dumps(charts,indent=2))
    print('Payload bytes:',sum(map(len,assets.values())))
    for name,blob in assets.items():
        if msu and name.startswith('timeline'):continue
        (OUT/(name+'.bin')).write_bytes(blob)
    pack_payload(assets,charts,msu);common_tables(charts)
    if msu:
        from msu_assets import generate
        generate(OUT,charts,external_music,generate_pcm=not args.no_pcm)

if __name__=='__main__':main()
