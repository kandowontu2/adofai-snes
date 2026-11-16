"""Extract main-world scenery from the user's installed game, read-only."""
import argparse, collections, json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME, SCENES
from official_catalog import source_chart_json,WORLDS

ROOT=Path(__file__).resolve().parents[1]

def json_scene(game,number,out):
    data=json.loads((ROOT/f'assets/private/level{number}.json').read_text())
    raw=source_chart_json(WORLDS[number-1],data)
    decorations=raw.get('decorations',[])
    names={Path(d.get('decorationImage','')).stem for d in decorations}
    env=UnityPy.load(str(game/'A Dance of Fire and Ice_Data/resources.assets'))
    images={}
    for o in env.objects:
        if o.type.name=='Texture2D':
            t=o.read()
            if t.m_Name in names:images[t.m_Name]=t.image.convert('RGBA')
    settings=raw['settings'];color=tuple(bytes.fromhex(settings['backgroundColor'][:6]))
    canvas=Image.new('RGBA',(256,256),color+(255,));used=[]
    scale=15.2/(settings.get('zoom',100)/100)
    cx,cy=settings.get('position',[0,0])
    for dec in sorted(decorations,key=lambda d:-d.get('depth',0)):
        if dec['eventType']!='AddDecoration' or dec.get('depth',0)<50:continue
        image=images.get(Path(dec.get('decorationImage','')).stem)
        if image is None:continue
        opacity=dec.get('opacity',100)
        visible=dec.get('visible',True)
        for event in raw['actions']:
            if event.get('floor')!=0 or event['eventType']!='MoveDecorations':continue
            if set(event.get('tag','').split())&set(dec.get('tag','').split()):
                opacity=event.get('opacity',opacity)
                visible=event.get('visible',visible)
        if not visible or opacity<=0:continue
        x,y=dec.get('position',[0,0]);sx,sy=dec.get('scale',[100,100]);a=math.radians(dec.get('rotation',0))
        co,si=math.cos(a),math.sin(a);w,h=image.size
        matrix=np.array([[co*sx/100,-si*sy/100,x],[si*sx/100,co*sy/100,y],[0,0,1.]])
        target=np.array([[scale,0,128-cx*scale],[0,-scale,108+cy*scale],[0,0,1.]])@matrix@np.array([[.01,0,-w*.005],[0,-.01,h*.005],[0,0,1.]])
        if abs(np.linalg.det(target))<1e-12:continue
        corners=target@np.array([[0,w,w,0],[0,0,h,h],[1,1,1,1]])
        if corners[0].max()<0 or corners[0].min()>256 or corners[1].max()<0 or corners[1].min()>256:continue
        rgba=bytes.fromhex(dec.get('color','ffffff').ljust(8,'f'))
        tint=tuple(rgba[:3])+(round(rgba[3]*opacity/100),)
        colored=ImageChops.multiply(image,Image.new('RGBA',image.size,tint))
        canvas.alpha_composite(colored.transform((256,256),Image.Transform.AFFINE,tuple(np.linalg.inv(target)[:2].ravel()),resample=Image.Resampling.BILINEAR))
        used.append(dec.get('decorationImage'))
    out.mkdir(parents=True,exist_ok=True);canvas.convert('RGB').save(out/f'main-{number}.png')
    (out/f'main-{number}.json').write_text(json.dumps(dict(level=number,source=data['source'],sprites=used,components=[],background=dict(zip('rgba',[v/255 for v in color]+[1.])),actions=raw['actions'],decorations=decorations),indent=2))
    print(number,len(used),'visible JSON scenery images',flush=True)

def scene(game, number, out):
    env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{SCENES[number]}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version)
    gen.load_local_game(str(game));env.typetree_generator=gen
    gos={};transforms={};by_go={};sprites=[];cameras=[];components=[];floors={}
    for o in env.objects:
        kind=o.type.name
        if kind=='GameObject':gos[o.path_id]=o.read_typetree()
        elif kind in ('Transform','RectTransform'):
            d=o.read_typetree();transforms[o.path_id]=d;by_go[d['m_GameObject']['m_PathID']]=o.path_id
        elif kind=='SpriteRenderer':sprites.append((o,o.read_typetree()))
        elif kind=='Camera':cameras.append(o.read_typetree())
        elif kind=='MonoBehaviour':
            b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
            cls=b.m_Script.deref().read().m_ClassName
            if cls=='scrFloor':
                d=o.read_typetree();floors[d['m_GameObject']['m_PathID']]=d['seqID']
            elif cls.startswith('ffx') or cls in ('scrParallax','scrColorChangeOnBeat','scrOpacityChangeOnBeat','scrSpriteAnimator','scrPulseOnBeat'):
                components.append(dict(cls=cls,data=o.read_typetree()))
    cache={}
    def inactive_parents(tid):
        result=[]
        while tid:
            t=transforms[tid];go=gos[t['m_GameObject']['m_PathID']]
            if not go['m_IsActive']:result.append(go['m_Name'])
            tid=t['m_Father']['m_PathID']
        return result
    def transform(tid):
        if not tid:return np.eye(3),True
        if tid in cache:return cache[tid]
        d=transforms[tid];parent,active=transform(d['m_Father']['m_PathID'])
        q=d['m_LocalRotation'];a=math.atan2(2*(q['w']*q['z']+q['x']*q['y']),1-2*(q['y']**2+q['z']**2))
        c,s=math.cos(a),math.sin(a);scale=d['m_LocalScale'];pos=d['m_LocalPosition']
        local=np.array([[c*scale['x'],-s*scale['y'],pos['x']],[s*scale['x'],c*scale['y'],pos['y']],[0,0,1.]])
        result=parent@local,active and bool(gos[d['m_GameObject']['m_PathID']]['m_IsActive'])
        cache[tid]=result;return result
    cameras={gos[c['m_GameObject']['m_PathID']]['m_Name']:c for c in cameras}
    cam=cameras['BGStaticCam'];color=cam['m_BackGroundColor']
    canvas=Image.new('RGBA',(256,256),tuple(round(color[k]*255) for k in 'rgba'))
    images={};used=[]
    for o,d in sorted(sprites,key=lambda row:row[1]['m_SortingOrder']):
        gid=d['m_GameObject']['m_PathID'];go=gos[gid]
        if go['m_Layer'] not in (10,11) or not d['m_Enabled']:continue
        # This full-screen curtain fades away at the opening of 6-X.
        # Bake the scenery underneath; its fade is represented by palettes.
        if go['m_Name'] in ('PureBlack','Bgbarsample'):continue
        matrix,active=transform(by_go[gid])
        # The original controller activates the high-detail BG root at
        # runtime. Other disabled phase/backup objects remain disabled.
        active=not any(name!='BG' for name in inactive_parents(by_go[gid]))
        if not active or d['m_Color']['a']<=0 or not d['m_Sprite']['m_PathID']:continue
        camera=cameras['BGMovingCam' if go['m_Layer']==10 else 'BGStaticCam']
        cm,_=transform(by_go[camera['m_GameObject']['m_PathID']]);view=np.linalg.inv(cm)
        scale=152/(2*camera['orthographic size'])
        projection=np.array([[scale,0,128],[0,-scale,108],[0,0,1.]])@view@matrix
        key=tuple(d['m_Sprite'].values())
        if key not in images:
            spr=o.read().m_Sprite.deref().read();images[key]=(spr.image.convert('RGBA'),spr.m_PixelsToUnits,spr.m_Pivot)
        image,ppu,pivot=images[key];w,h=image.size
        source=np.array([[1/ppu,0,-pivot.x*w/ppu],[0,-1/ppu,(1-pivot.y)*h/ppu],[0,0,1.]])
        target=projection@source
        if abs(np.linalg.det(target))<1e-12:continue
        corners=target@np.array([[0,w,w,0],[0,0,h,h],[1,1,1,1]])
        if corners[0].max()<0 or corners[0].min()>256 or corners[1].max()<0 or corners[1].min()>256:continue
        tint=tuple(round(d['m_Color'][k]*255) for k in 'rgba')
        colored=ImageChops.multiply(image,Image.new('RGBA',image.size,tint))
        inv=np.linalg.inv(target)
        canvas.alpha_composite(colored.transform((256,256),Image.Transform.AFFINE,tuple(inv[:2].ravel()),resample=Image.Resampling.BILINEAR))
        used.append(dict(name=go['m_Name'],game_object=gid,layer=go['m_Layer'],order=d['m_SortingOrder'],sprite=key))
    out.mkdir(parents=True,exist_ok=True);canvas.convert('RGB').save(out/f'main-{number}.png')
    for c in components:
        c['floor']=floors.get(c['data']['m_GameObject']['m_PathID'])
        target=c['data'].get('objFade',{}).get('m_PathID')
        if target in gos:c['target_name']=gos[target]['m_Name']
    inventory=[]
    for _,d in sprites:
        gid=d['m_GameObject']['m_PathID'];go=gos[gid];m,active=transform(by_go[gid])
        inventory.append(dict(name=go['m_Name'],layer=go['m_Layer'],active=active,inactive=inactive_parents(by_go[gid]),enabled=d['m_Enabled'],position=m[:2,2].tolist(),alpha=d['m_Color']['a']))
    report=dict(level=number,source=f'Unity scene level{SCENES[number]}',background=color,sprites=used,components=components,inventory=inventory)
    (out/f'main-{number}.json').write_text(json.dumps(report,indent=2))
    print(number,len(used),'visible background sprites',collections.Counter(c['cls'] for c in components if c['floor'] is not None),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--game',type=Path,default=Path(DEFAULT_GAME));p.add_argument('--levels',type=int,nargs='+',default=list(range(1,13)));p.add_argument('--out',type=Path,default=ROOT/'assets/private/main-vfx');a=p.parse_args()
    for n in a.levels:(json_scene if n in (3,5) else scene)(a.game,n,a.out)
