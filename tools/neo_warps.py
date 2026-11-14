"""Read Mawaru's scene-owned warp markers and their authored link endpoints."""


def extract(objects, chapter, world, by_object):
    result=[]
    for prefix in ('lofi','lofi2'):
        warps=chapter.get(prefix+'_warptiles',[])
        links=chapter.get(prefix+'_links',[])
        for index,ref in enumerate(warps):
            obj=objects[ref['m_PathID']];data=obj.read_typetree()
            transform=world(by_object[data['m_GameObject']['m_PathID']])
            row=dict(section=prefix,index=index,position=transform[:2,3].tolist(),tint=data['tint'])
            if index<len(links):
                link=objects[links[index]['m_PathID']].read_typetree()
                matrix=world(by_object[link['m_GameObject']['m_PathID']])
                # warp_link is a centered 16x64 sprite at 32 pixels/unit.
                # Its longitudinal axis is local Y; preserve scene rotation
                # and scale instead of guessing the connected floors.
                row['link']=[(matrix@[0.,v,0.,1.])[:2].tolist() for v in (-1.,1.)]
            result.append(row)
    return result


def extract_math(objects, chapter, world, by_object, ex=False):
    """Keep scene sprite masks private, with their original world transforms."""
    import numpy as np
    from PIL import Image
    from UnityPy.classes import PPtr
    result=[]
    selected={}
    for section in (1,2):
        for p in chapter[f'math{section}_floorstotint']:selected[p['m_PathID']]=(section,None)
    for j,p in enumerate(chapter['math_randomize']):selected[p['m_PathID']]=(1 if j<6 else 2,j)
    for ident,(section,j) in selected.items():
        obj=objects[ident];data=obj.read_typetree();go=data['m_GameObject']['m_PathID']
        renderer=next(o for o in objects.values() if o.type.name=='SpriteRenderer' and o.read_typetree()['m_GameObject']['m_PathID']==go)
        rd=renderer.read();ptr=rd.m_Sprite
        if j is not None:
            group=j//3;answer=j%3
            overrides={3:'3c'} if not ex else {0:'3',1:'3c',2:'4',3:'3b'}
            if group in overrides:
                suffix=overrides[group]
                field='math_extraquestions'+suffix if answer==0 else 'math_extraanswers'+suffix
                idx=0 if answer==0 else (answer-1 if group in (0,3) else 2-answer)
                raw=chapter[field][idx]
            else:raw=data['frames'][0]
            ptr=PPtr(m_FileID=raw['m_FileID'],m_PathID=raw['m_PathID'],assetsfile=obj.assets_file)
        sprite=ptr.deref().read();im=sprite.image.convert('RGBA')
        # 16 world pixels per Unity unit in the imported track. Preserve
        # source sprite pixel-to-world scale and the parent's affine matrix.
        matrix=world(by_object[go]);ppunit=sprite.m_PixelsToUnits
        sx=im.width/ppunit;sy=im.height/ppunit
        pivot=sprite.m_Pivot
        local=np.array([[1/ppunit,0,-sx*pivot.x],[0,-1/ppunit,sy*(1-pivot.y)],[0,0,1.]])
        affine=matrix[np.ix_([0,1,3],[0,1,3])]@local
        if ex and j==0:affine[0,2]-=1
        # Store the full alpha mask, not proprietary sprite files in Git.
        mask=im.getchannel('A');bounds=mask.getbbox()
        if bounds is None:continue
        left,top,right,bottom=bounds;mask=mask.crop(bounds)
        affine=affine@np.array([[1,0,left],[0,1,top],[0,0,1.]])
        result.append(dict(section=section,kind='text' if j is not None else 'floor',matrix=affine.tolist(),
                           size=list(mask.size),alpha=list(mask.tobytes())))
    return result


def fork_surfaces(notes,root):
    """Mirror the playable pieces themselves, never a different prefab."""
    from PIL import Image,ImageChops,ImageFilter
    from track_geometry import piece,surface,recessed_join
    pivot=notes[root]['y'];parts=[]
    for i in (root+3,root+2,root+1):
        x,y,paint=surface(notes,i)
        # Gems share world lighting; their symmetric footprint stays the
        # same. Corners and their recessed seams reflect pixel for pixel.
        reflected=paint if notes[i].get('gem_platform') else paint.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        parts.append((i,x,2*pivot-y-paint.height+1,reflected))
    x,y,mask=piece(notes,root)
    y2=2*pivot-y-mask.height+1;top=min(y,y2);bottom=max(y+mask.height,y2+mask.height)
    joint=Image.new('L',(mask.width,bottom-top))
    joint.paste(mask,(0,y-top));mirror=Image.new('L',joint.size)
    mirror.paste(mask.transpose(Image.Transpose.FLIP_TOP_BOTTOM),(0,y2-top));joint=ImageChops.lighter(joint,mirror)
    coverage=joint.point(lambda p:255 if p else 0);paint=Image.new('L',joint.size);paint.paste(1,mask=coverage)
    paint.paste(3,mask=ImageChops.subtract(coverage,coverage.filter(ImageFilter.MinFilter(3))))
    if notes[root].get('exit_angle') is not None:
        for angle in (notes[root]['exit_angle'],-notes[root]['exit_angle']):
            seam,ink=recessed_join(paint.size,coverage,(notes[root]['x']-x,pivot-top),angle)
            paint.paste(seam,mask=ink)
    parts.append((root,x,top,paint))
    return parts


def compile_math(data,chart):
    from PIL import Image
    if not data.get('native_math'):return
    roots=(319,727) if data['code']=='T3EX-X' else (248,555)
    notes=[dict(n) for n in chart['notes']]
    for n in notes:n.pop('scene_visual',None)
    for section,root in enumerate(roots,1):
        chapter=next((e['data'] for e in data.get('native_chapter_entities',[]) if e['type']=='Mawaru'),{})
        tint=chapter.get(f'math{section}_floorcolor',dict(r=.8 if section==1 else 1,g=.8,b=.8 if section==1 else .2))
        for i in range(root,min(root+24,len(notes))):chart['notes'][i]['math_tint']=tint
        parts=fork_surfaces(notes,root)+fork_surfaces(notes,root+12)
        x0=min(x for i,x,y,m in parts);y0=min(y for i,x,y,m in parts)
        x1=max(x+m.width for i,x,y,m in parts);y1=max(y+m.height for i,x,y,m in parts)
        paint=Image.new('L',(x1-x0,y1-y0))
        for i,x,y,m in parts:paint.paste(m,(x-x0,y-y0),m.point(lambda p:255 if p else 0))
        mask=paint.point(lambda p:255 if p else 0)
        chart['notes'][root]['scene_visual']=dict(offset=[int(x0-notes[root]['x']),int(y0-notes[root]['y'])],size=list(mask.size),
            bits=mask.convert('1').tobytes().hex(),surface=paint.tobytes().hex())
    chart['mawaru_math_style_version']=3
    from neo_math import labels
    labels(data,chart)
