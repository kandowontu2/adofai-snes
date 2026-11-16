"""Bounded BG2 scenery: static CHR, four-byte frame cues, palette animation.

No track frame, stream packet, sprite or gameplay tile is modified.
"""
import bisect, collections, json, struct
from pathlib import Path
import numpy as np
from PIL import Image
from make_assets import tile_bytes

ROOT=Path(__file__).resolve().parents[1]
STATIC_LEVELS=set(json.loads((ROOT/'assets/graphics/main-vfx.json').read_text())['static_levels'])

def encode_background(image):
    # BG2 has 112 reserved four-bit tiles. Only scenery is simplified.
    for cell in (1,2):
        small=image.resize((256//cell,256//cell),Image.Resampling.BOX)
        q=small.quantize(colors=15,dither=Image.Dither.NONE)
        pixels=np.asarray(q.resize((256,256),Image.Resampling.NEAREST),dtype=np.uint8)+1
        if cell==2:
            # Cluster scenery patches into the fixed hardware atlas instead
            # of reducing the scene to one solid color per eight-pixel tile.
            # Medoids retain real source edges, rather than averaged blur.
            from scipy.cluster.vq import kmeans2
            from scipy.spatial.distance import cdist
            patches=pixels.reshape(32,8,32,8).transpose(0,2,1,3).reshape(1024,8,8)
            unique,inverse=np.unique(patches.reshape(1024,64),axis=0,return_inverse=True)
            if len(unique)>112:
                pal=np.array([[0,0,0]]+np.array((q.getpalette()+[0]*45)[:45]).reshape(15,3).tolist(),dtype=float)
                vectors=pal[unique.reshape(-1,8,8)[:,::2,::2]].reshape(len(unique),-1)
                centers,_=kmeans2(vectors,112,iter=16,minit='++',seed=1)
                medoids=np.unique(cdist(centers,vectors).argmin(axis=1))
                chosen=medoids[cdist(vectors,vectors[medoids]).argmin(axis=1)]
                pixels=unique[chosen[inverse]].reshape(32,32,8,8).transpose(0,2,1,3).reshape(256,256)
        glyphs=[];lookup={};words=[]
        for y in range(0,256,8):
            for x in range(0,256,8):
                tile=pixels[y:y+8,x:x+8];variants=[tile,tile[:,::-1],tile[::-1,:],tile[::-1,::-1]]
                found=None
                for flip,a in enumerate(variants):
                    key=bytes(tile_bytes(a))
                    if key in lookup:found=lookup[key]|((flip&1)<<14)|((flip&2)<<14);break
                if found is None:
                    key=bytes(tile_bytes(tile));found=len(glyphs);lookup[key]=found;glyphs.append(key)
                # BG2 character base is $5000 words; art starts at $5500.
                words.append((found&0xFC00)|((found&1023)+80))
        if len(glyphs)<=112:
            pal=np.array((q.getpalette()+[0]*45)[:45],dtype=float).reshape(15,3)
            return b''.join(glyphs),struct.pack('<1024H',*words),pal,cell,pixels
    raise AssertionError('Flat-color background exceeded the fixed atlas')

def build_chart(folder,number):
    source=ROOT/'assets/private/main-vfx'
    meta=json.loads((source/f'main-{number}.json').read_text())
    chart=json.loads((folder/f'level{number}.json').read_text())
    image=Image.open(source/f'main-{number}.png').convert('RGB')
    glyphs,tilemap,colors,resolution,pixels=encode_background(image)
    events=[];flashes=[];curtains=[]
    for c in meta.get('components',[]):
        floor=c.get('floor');d=c['data']
        if floor is None or not d.get('m_Enabled',1):continue
        frame=chart['notes'][min(floor,len(chart['notes'])-1)]['frame']
        color=d.get('color',{})
        if c['cls']=='ffxBgColor':events.append((frame,round(d.get('fadeTime',0)*60.0988),np.array([color.get(k,0)*255 for k in 'rgb'])))
        elif c['cls'] in ('ffxFlash','ffxFlashPlus') and not d.get('kill'):
            flashes.append((frame,np.array([color.get(k,1)*255 for k in 'rgb']),color.get('a',1)))
        elif c['cls']=='ffxFadeIn' and c.get('target_name')=='PureBlack' and d.get('value')==0:
            curtains.append((frame,max(1,round(d.get('time',0)*60.0988))))
    events.sort(key=lambda e:e[0]);flashes.sort(key=lambda e:e[0])
    cameras=chart['camera_follow_versions'];times=[c[0] for c in cameras];origin=cameras[0][1:]
    parallax=[c['data'] for c in meta.get('components',[]) if c['cls']=='scrParallax' and c['data'].get('m_Enabled',1)]
    drift=[float(np.median([1-d.get('multiplier_'+axis,1) for d in parallax])) if parallax else 0 for axis in ('x','y')]
    scenery=[d for d in meta.get('decorations',[]) if d.get('decorationImage') in meta['sprites']]
    if scenery:
        drift=[float(np.median([1-d.get('parallax',[100,100])[i]/100 for d in scenery])) for i in (0,1)]
    # A single hardware plane approximates multiple native depths. Keep
    # travel within the scenery's border rather than wrapping a panorama.
    drift=np.clip(drift,-.15,.15).tolist()
    pulse=any(c['cls'] in ('scrOpacityChangeOnBeat','scrPulseOnBeat','ffxPulseMag') and c['data'].get('m_Enabled',1) for c in meta.get('components',[]))
    beat=60.0988*60/chart['bpm'];notes=[n['frame'] for n in chart['notes']]
    original=np.array([meta['background'].get(k,0)*255 for k in 'rgb']);current=original.copy()
    event_at=0;fade_start=0;fade_length=0;fade_from=current.copy();fade_to=current.copy()
    palettes=[];lookup={};cues=bytearray();end=chart['notes'][-1]['frame']+120
    backdrop=struct.unpack_from('<H',(ROOT/'assets/graphics/mode7/palette.bin').read_bytes())[0]
    for frame in range(end+1):
        if fade_length:current=fade_from+(fade_to-fade_from)*min(1,(frame-fade_start)/fade_length)
        while event_at<len(events) and events[event_at][0]<=frame:
            fade_start,fade_length,fade_to=events[event_at];fade_from=current.copy();event_at+=1
            if not fade_length:current=fade_to.copy()
        age=(frame-notes[0])%beat
        gain=.24+(.055*max(0,1-age/(beat*.6)) if pulse else 0)
        rgb=np.clip(colors+(current-original)*.35,0,255)*gain
        for start,col,alpha in flashes:
            if 0<=frame-start<18:rgb+=col*(alpha*.10*(1-(frame-start)/18))
        for start,duration in curtains:rgb*=max(0,min(1,(frame-start)/duration))
        words=[backdrop]+[int(r//8)|(int(g//8)<<5)|(int(b//8)<<10) for r,g,b in np.clip(rgb,0,248)]
        raw=struct.pack('<16H',*words)
        if raw not in lookup:lookup[raw]=len(palettes)*32;palettes.append(raw)
        camera=cameras[bisect.bisect_right(times,frame)-1][1:]
        scroll=[round(float(np.clip((camera[i]-origin[i])*drift[i]/2,-12,12)))&255 for i in (0,1)]
        cues+=bytes(scroll)+struct.pack('<H',lookup[raw])
    if number in STATIC_LEVELS:
        # Static scenery must not freeze an opening black curtain forever.
        # Use the unoccluded source colors, with the same subdued gain.
        words=[backdrop]+[int(r//8)|(int(g//8)<<5)|(int(b//8)<<10) for r,g,b in np.clip(colors*.24,0,248)]
        palettes[0]=struct.pack('<16H',*words)
        cues=bytearray(len(cues))
    assert len(cues)<65536 and len(palettes)*32<65536
    blobs={f'main_vfx_{key}{number}':value for key,value in [('chr',glyphs),('map',tilemap),('cues',bytes(cues)),('pal',b''.join(palettes))]}
    for name,blob in blobs.items():(folder/f'{name}.bin').write_bytes(blob)
    report=dict(id=number,source=meta['source'],animated=number not in STATIC_LEVELS,glyphs=len(glyphs)//32,scenery_pixel_size=resolution,frames=end+1,palettes=len(palettes),background_color_events=len(events),background_flash_events=len(flashes),parallax=drift,track_bytes_changed=0)
    (folder/f'main_vfx{number}.json').write_text(json.dumps(report,indent=2))
    preview=Image.fromarray(pixels).convert('P');preview.putpalette([0,0,0]+[int(v) for row in colors*.3 for v in row]+[0]*720)
    preview.save(folder/f'main_vfx{number}.png')
    return blobs,report

def assets(folder,charts):
    result={};reports=[]
    for c in charts:
        if 1<=c['id']<=12:
            blobs,report=build_chart(folder,c['id']);result.update(blobs);reports.append(report)
    if reports:
        result['main_vfx_descriptors']=bytes(16*len(charts))
        raw=(ROOT/'assets/graphics/mode7/background.map').read_bytes()
        result['main_vfx_default_map']=b''.join(struct.pack('<H',(v&0xFC00)|((v&1023)+80)) for (v,) in struct.iter_unpack('<H',raw))
    (folder/'main-vfx-report.json').write_text(json.dumps(reports,indent=2))
    return result
