"""Import the selected Featured revisions from the owner's Steam library.

Private chart/music files stay outside the source release. Native Neo JSON
events retain their gameplay meaning instead of becoming visual-only pauses.
"""
import argparse,collections,copy,hashlib,json,math,re,subprocess
from pathlib import Path
from import_campaign import DEFAULT_GAME
from import_official import normalize_json
from official_catalog import load_game_json
from track_motion import enabled,ease_name
from import_hitsounds import SOUNDS

ROOT=Path(__file__).resolve().parents[1]
FEATURED=json.loads((ROOT/'tools/featured_catalog.json').read_text())


def read_chart(path):
    text=path.read_text(encoding='utf-8-sig');repairs=[]
    # Both released endless.reality files omit this one member separator.
    # Record the repair without rewriting the downloaded author's file.
    marker=']\n\t"decorations"'
    if marker in text:
        assert text.count(marker)==1
        text=text.replace(marker,'],\n\t"decorations"')
        repairs.append('Inserted missing separator before decorations member')
    text,count=re.subn(r'(?m)(^[ \t]*\{[^\n]*\})[ \t]*\n(?=[ \t]*\{)',r'\1,\n',text)
    if count:repairs.append(f'Inserted {count} missing separators between event objects')
    return load_game_json(text),repairs


def neo_fields(raw,data):
    floors=data['floors'];events=collections.defaultdict(list)
    for a in raw['actions']:
        if enabled(a.get('active',True)):events[a['floor']].append(a)
    radius=1.;ease=1;parts=1;behavior=0;x=y=0.;hx=hy=0.;positions=[];cells=[]
    data.update(neo_cosmos=True,native_layout_version=2,native_tile_size=1.5,
        native_track_effects=[],native_effects=[],native_holdsound={},
        native_hit_volume=raw['settings'].get('hitsoundVolume',100)/100,
        native_countdown_multiplier=raw['settings'].get('countdownSpeedMultiplier',1))
    for i,f in enumerate(floors):
        if i:
            a=floors[i-1]['exitangle']-math.pi/2
            x+=1.5*math.cos(a)+hx;y-=1.5*math.sin(a)-hy
        hx=hy=0.
        for a in events[i]:
            kind=a['eventType']
            if kind=='ScaleRadius':radius=a['scale']/100
            elif kind=='SetPlanetRotation':
                ease=next(j for j in range(32) if ease_name(j)==a['ease'])
                parts=a.get('easeParts',1);behavior=int(a.get('easePartBehavior','Mirror')!='Mirror')
            elif kind=='Pause':f['countdownTicks']=a.get('countdownTicks',0)
        # ScaleRadius expands the incoming step and carries that displacement
        # to subsequent floors (scnGame.SetupLevelEvents, radiusScale).
        a=f['entryangle']-math.pi/2
        x-=1.5*(radius-1)*math.cos(a);y+=1.5*(radius-1)*math.sin(a)
        positions.append([x,y])
        f.update(radiusScale=radius,planetEase=ease,planetEaseParts=parts,planetEasePartBehavior=behavior)
        if f['holdLength']>=0:
            arc=(f['exitangle']-f['entryangle'])%(2*math.pi)
            distance=0 if min(arc,2*math.pi-arc)<1e-5 else (2*f['holdLength']+1)*f.get('holdDistanceMultiplier',1)
            a=f['exitangle']-math.pi/2;hx=distance*1.5*math.cos(a);hy=-distance*1.5*math.sin(a)
        for a in events[i]:
            if a['eventType']!='FreeRoam' or a['duration']<2:continue
            region=sum(bool(p.get('freeroam')) for p in floors[:i]);w,h=map(int,a['size']);ox,oy=a['positionOffset']
            extra=math.pi*(f['numPlanets']-2)/f['numPlanets'] if i and not f['midSpin'] and not floors[i-1]['midSpin'] else 0
            arc=((f['exitangle']-f['entryangle'])*(-1 if f['isCCW'] else 1)-extra)%(2*math.pi)
            if arc<1e-5:arc=0 if f['midSpin'] else 2*math.pi
            arc/=math.pi
            f.update(freeroam=True,freeroamRegion=region,freeroamOffset=dict(x=ox,y=oy),
                freeroamEndEarlyBeats=min(a.get('outTime',4),a['duration']-1),
                freeroamEndEase=next(j for j in range(32) if ease_name(j)==a.get('outEase','InOutSine')),
                moveCamAtFreeroamEnd=enabled(a.get('outCam',True)),countdownTicks=a.get('countdownTicks',4),
                freeroamSoundOnBeat=SOUNDS.index(a.get('hitsoundOnBeats','None')),
                freeroamSoundOffBeat=SOUNDS.index(a.get('hitsoundOffBeats','None')))
            f['extraBeats']+=max(arc,a['duration']-arc)
            removed=set();twirls=set()
            for e in events[i]:
                if e['eventType']=='FreeRoamRemove':
                    px,py=map(int,e['position']);sw,sh=map(int,e['size'])
                    removed.update(yy*w+xx for yy in range(py,py+sh) for xx in range(px,px+sw) if 0<=yy*w+xx<w*h)
                elif e['eventType']=='FreeRoamTwirl':twirls.add(int(e['position'][1])*w+int(e['position'][0]))
            for k in range(w*h):
                xx,yy=k%w,k//w
                cells.append(dict(freeroamRegion=region,freeroamPosition=dict(x=xx,y=yy),
                    position=[x+(xx+ox)*1.5,y+(yy+oy)*1.5],isLandable=k not in removed,isSwirl=k in twirls))
    data.update(native_positions=positions,freeroam_cells=cells)
    if any(f.get('freeroam') for f in floors):
        # The preceding moving platform may deliver the planets to a cell
        # displaced from the invisible region root. Sample its actual pose.
        from campaign_assets import compile_chart,FPS
        from track_motion import motion_schedule
        temporary=copy.deepcopy(data)
        for f in temporary['floors']:f['freeroam']=False
        chart,_=compile_chart(temporary);chart.update(mode7=True,motion_step=1)
        moves=motion_schedule(temporary,chart);offsets={}
        for i,f in enumerate(floors):
            if not f.get('freeroam'):continue
            for frame,updates in moves.items():
                if frame>chart['notes'][i]['frame']:break
                offsets.update(updates)
            p=chart['notes'][i-1];n=chart['notes'][i];px,py=offsets.get(i-1,(0,0));nx,ny=offsets.get(i,(0,0))
            f['freeroamEntry']=[round(p['x']+px+24*math.cos(p['exit_angle'])-n['x']-nx),
                                round(p['y']+py+24*math.sin(p['exit_angle'])-n['y']-ny)]


def import_chart(meta,folder,out):
    source=folder/meta['workshop']/'main.adofai';raw,repairs=read_chart(source)
    data=normalize_json(raw,dict(meta,text=meta['workshop']))
    settings=raw['settings'];actions=raw['actions']
    data.update(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_repairs=repairs,
        artist=meta['artist'],author=meta['author'],featured_classic=meta.get('set')!='firestix',featured_wave=meta.get('wave'),
        workshop=meta['workshop'],firestix=meta.get('set')=='firestix',
        track_settings=settings,track_color_import=1,camera_rotation_initial=settings.get('rotation',0),
        camera_actions=[a for a in actions if a['eventType'] in ('MoveCamera','RepeatEvents','SetConditionalEvents')],
        track_actions=[a for a in actions if a['eventType'] in ('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')],
        featured_actions=actions,featured_decorations=raw.get('decorations',[]))
    data['separate_countdown']=enabled(data['separate_countdown'])
    hides={a['floor']:enabled(a['hideTileIcon']) for a in actions if a['eventType']=='Hide' and 'hideTileIcon' in a and enabled(a.get('active',True))}
    hidden=False;data['hidden_icons']=[]
    for i in range(len(data['floors'])):
        hidden=hides.get(i,hidden);data['hidden_icons'].append(hidden)
    if meta.get('neo_cosmos'):neo_fields(raw,data)
    n=meta['id'];out.mkdir(exist_ok=True,parents=True)
    (out/f'level{n}.json').write_text(json.dumps(data,indent=2))
    wav=out/f'{n}-X.wav'
    if not wav.exists():subprocess.run(['ffmpeg','-v','error','-y','-i',str(source.parent/settings['songFilename']),'-c:a','pcm_s16le',str(wav)],check=True)
    return data,dict(hitsound=settings.get('hitsound','Kick'),hitsoundVolume=settings.get('hitsoundVolume',100),
        countdownSpeedMultiplier=settings.get('countdownSpeedMultiplier',1),events=[a for a in actions if a['eventType']=='SetHitsound' and enabled(a.get('active',True))])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--levels',type=int,nargs='+');args=p.parse_args()
    folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950';out=ROOT/'assets/private'
    soundfile=out/'hitsound-levels.json';sounds=json.loads(soundfile.read_text())
    for meta in FEATURED:
        if args.levels and meta['id'] not in args.levels:continue
        data,sound=import_chart(meta,folder,out);sounds[str(meta['id'])]=sound
        print(meta['code'],len(data['floors'])-1,'floors',flush=True)
    soundfile.write_text(json.dumps(sounds,indent=2))


if __name__=='__main__':main()
