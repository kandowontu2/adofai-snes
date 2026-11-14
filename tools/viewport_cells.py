"""Cells sampled by the game's Mode 7 register setup, including truncation.

The PPU truncates each origin product to six fractional bits separately.
See Snes9x tileimpl.h, DrawTileNormal, for an independent implementation:
https://github.com/snes9xgit/snes9x/blob/master/tileimpl.h
"""
import numpy as np


def sampled_pixels(x, y, c, s, center=104, bottom=176, top=32):
    columns=np.arange(256,dtype=np.int64)[None,:]
    lines=np.arange(top+1,bottom+1,dtype=np.int64)[:,None]
    px=x+128+((c*columns+((-128*c)&~63)+((s*lines)&~63)+((-(center+1)*s)&~63))>>8)
    py=y+center+((-s*columns+((128*s)&~63)+((c*lines)&~63)+((-(center+1)*c)&~63))>>8)
    return np.broadcast_arrays(px,py)


def sampled_cells(x,y,c,s,center=104,bottom=176,top=32):
    px,py=sampled_pixels(x,y,c,s,center,bottom,top)
    packed=((px//8)&65535)+((py//8)<<16)
    return {(int(v&65535) if (v&65535)<32768 else int(v&65535)-65536,int(v>>16))
            for v in np.unique(packed).tolist()}


def pixel_masks(x,y,c,s,center=104,bottom=176,top=32):
    px,py=sampled_pixels(x,y,c,s,center,bottom,top)
    packed=(((px//8)&65535)+((py//8)<<16)).ravel()
    keys,indices=np.unique(packed,return_inverse=True)
    bits=np.left_shift(np.uint64(1),((px&7)+8*(py&7)).ravel().astype(np.uint64))
    masks=np.zeros(len(keys),dtype=np.uint64)
    np.bitwise_or.at(masks,indices,bits)
    return {(int(v&65535) if (v&65535)<32768 else int(v&65535)-65536,int(v>>16)):int(mask)
            for v,mask in zip(keys.tolist(),masks.tolist())}


def share_clipped_patterns(chart,tiles,history):
    """Share boundary patterns only when every sampled pixel is identical."""
    from collections import defaultdict,Counter
    from functools import lru_cache
    events=defaultdict(dict)
    for cell,rows in history.items():
        for frame,value in rows:events[frame][cell]=value
    cameras={f:(x,y) for f,x,y in chart['camera_follow_versions']}
    rotations={f:(c,s) for f,c,s in chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[]))}
    values=[int.from_bytes(t,'little') for t in tiles]
    lookup={raw:i for i,raw in enumerate(tiles)}
    @lru_cache(maxsize=4096)
    def byte_mask(bits):return int.from_bytes(bytes(255 if bits>>i&1 else 0 for i in range(64)),'little')
    live={};previous={};result={};camera=cameras[0];rotation=(256,0);shared=0
    for frame in sorted(set(events)|set(cameras)|set(rotations)):
        if frame>=chart['notes'][-1]['frame']:break
        live.update(events.get(frame,{}));camera=cameras.get(frame,camera);rotation=rotations.get(frame,rotation)
        masks=pixel_masks(*camera,*rotation,chart.get('viewport_center_y',96),chart.get('viewport_bottom',160),chart.get('viewport_top',32))
        uses=defaultdict(int);counts=Counter()
        for cell,p in live.items():
            if p and cell in masks:uses[p]|=masks[cell];counts[p]+=1
        aliases={p:p for p in uses}
        original_masks=dict(uses)
        # Projected OBJ can retain overflow without changing its pixels.
        # Leave headroom there instead of synthesizing a different partial
        # bitmap for nearly every camera frame at a saturated BG atlas.
        capacity=288 if chart.get('projected_pattern_overflow') else 255
        if len(uses)>capacity:
            # Prefer existing complete patterns. Never alter sampled colors.
            for p in sorted(uses,key=lambda p:uses[p].bit_count()):
                if len(set(aliases.values()))<=capacity:break
                if aliases[p]!=p:continue
                mask=byte_mask(uses[p])
                for q in sorted(set(aliases.values())-{p},key=lambda q:-counts[q]):
                    if not ((values[p]^values[q])&mask):
                        aliases={old:(q if target==p else target) for old,target in aliases.items()}
                        uses[q]|=uses[p];counts[q]+=counts[p];shared+=1;break
                if aliases[p]!=p:continue
                # Two clipped cells can share a new bitmap even when neither
                # complete source bitmap matches. Only their sampled overlap
                # must agree; preserve both sets of visible pixels exactly.
                for q in sorted(set(aliases.values())-{p},key=lambda q:uses[q].bit_count()):
                    overlap=byte_mask(uses[p]&uses[q])
                    if (values[p]^values[q])&overlap:continue
                    merged=(values[q]&~mask)|(values[p]&mask)
                    raw=merged.to_bytes(64,'little')
                    if raw not in lookup:
                        lookup[raw]=len(tiles);tiles.append(raw);values.append(merged)
                    target=lookup[raw]
                    aliases={old:(target if v in (p,q) else v) for old,v in aliases.items()}
                    uses[target]=uses[p]|uses[q]|uses.get(target,0);counts[target]=counts[p]+counts[q]+(counts[target] if target not in (p,q) else 0);shared+=1;break
            assert all(not ((values[p]^values[target])&byte_mask(original_masks[p])) for p,target in aliases.items()),'Boundary sharing changed a sampled pixel'
        current={cell:aliases[p] for cell,p in live.items() if p and cell in masks}
        for cell in previous.keys()|current.keys():
            value=current.get(cell,0)
            if value!=previous.get(cell,0):result.setdefault(cell,[]).append((frame,value))
        previous=current
    chart['clipped_pattern_shares']=shared
    print(chart['code'],shared,'pixel-exact boundary pattern shares',flush=True)
    return result
