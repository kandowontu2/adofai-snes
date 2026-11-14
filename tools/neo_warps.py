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


def compile_math(data,chart):
    import numpy as np
    from PIL import Image,ImageChops
    roots=(319,727) if data['code']=='T3EX-X' else (248,555)
    unit=24/data['native_tile_size']
    for section,root in enumerate(roots,1):
        chapter=next((e['data'] for e in data.get('native_chapter_entities',[]) if e['type']=='Mawaru'),{})
        tint=chapter.get(f'math{section}_floorcolor',dict(r=.8 if section==1 else 1,g=.8,b=.8 if section==1 else .2))
        # Real and fake branches share the chapter's tint. Neither the
        # scene-owned alternative nor the real path should reveal an answer.
        for i in range(root,min(root+24,len(chart['notes']))):
            chart['notes'][i]['math_tint']=tint
        decals=[];base=data['native_positions'][root]
        transform=np.array([[unit,0,-unit*base[0]],[0,-unit,unit*base[1]],[0,0,1.]])
        for d in data.get('native_math',[]):
            assigned=d['section']
            if d['kind']=='floor':
                center=np.array(d['matrix'])@[d['size'][0]/2,d['size'][1]/2,1]
                assigned=min((1,2),key=lambda s:min(sum((center[a]-data['native_positions'][r][a])**2 for a in (0,1)) for r in (roots[s-1],roots[s-1]+12)))
            if assigned!=section:continue
            matrix=transform@np.array(d['matrix']);w,h=d['size']
            corners=[matrix@[x,y,1] for x in (0,w) for y in (0,h)]
            x0=int(np.floor(min(p[0] for p in corners)));y0=int(np.floor(min(p[1] for p in corners)))
            x1=int(np.ceil(max(p[0] for p in corners)));y1=int(np.ceil(max(p[1] for p in corners)))
            inverse=np.linalg.inv(matrix)@np.array([[1,0,x0],[0,1,y0],[0,0,1.]])
            mask=Image.frombytes('L',(w,h),bytes(d['alpha']))
            mask=mask.transform((x1-x0,y1-y0),Image.Transform.AFFINE,tuple(inverse[:2,:].flat),Image.Resampling.BILINEAR).point(lambda p:255 if p>=80 else 0)
            decals.append((x0,y0,mask,d['kind']))
        if not decals:continue
        x0=min(x for x,y,m,k in decals);y0=min(y for x,y,m,k in decals)
        x1=max(x+m.width for x,y,m,k in decals);y1=max(y+m.height for x,y,m,k in decals)
        floors=Image.new('L',(x1-x0,y1-y0));text=Image.new('L',floors.size)
        for x,y,m,kind in decals:
            layer=Image.new('L',floors.size);layer.paste(m,(x-x0,y-y0))
            if kind=='text':text=ImageChops.lighter(text,layer)
            else:floors=ImageChops.lighter(floors,layer)
        mask=ImageChops.lighter(floors,text);cutout=ImageChops.multiply(floors,text)
        chart['notes'][root]['scene_visual']=dict(offset=[x0,y0],size=list(mask.size),bits=mask.convert('1').tobytes().hex(),cutout=cutout.convert('1').tobytes().hex(),text=text.convert('1').tobytes().hex())
