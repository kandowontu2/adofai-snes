"""Readable live math labels, with the original four variants per problem set."""
import json
from pathlib import Path
from make_assets import FPS

ROOT=Path(__file__).resolve().parents[1]
POOLS=json.loads((ROOT/'assets/graphics/math-questions.json').read_text())
POOL_NAMES=tuple(POOLS)
FONT_CHARS='0123456789+-*/()=^SQRT'


def pool(code,group,speed):
    if code=='T3EX-X':return ('3','3c','4','3b')[group]
    if group==0:return 'base0'
    if group==1:return '2' if speed<16 else '1b'
    if group==2:return '3' if speed<13 else '2b' if speed<16 else '2' if speed<20 else '1c'
    return '3c' if speed<13 else '3' if speed<16 else '2b' if speed<20 else '1d'


def labels(data,chart):
    import numpy as np
    from neo_visuals import chapter_time
    roots=(319,331,727,739) if data['code']=='T3EX-X' else (248,260,555,567)
    texts=[d for d in data.get('native_math',[]) if d['kind']=='text']
    chart['neo_math_questions']=[]
    unit=24/data['native_tile_size']
    for group,root in enumerate(roots):
        if len(texts)<group*3+3:continue
        origin=data['native_positions'][root]
        centers=[(np.array(d['matrix'])@[d['size'][0]/2,d['size'][1]/2,1])[:2]
                 for d in texts[group*3:group*3+3]]
        branch=data['native_positions'][root+1]
        correct=min((1,2),key=lambda j:np.linalg.norm(centers[j]-branch))
        positions=[[round((c[0]-origin[0])*unit),round(-(c[1]-origin[1])*unit)]
                   for c in (centers[0],centers[correct],centers[3-correct])]
        start,end=(301,337) if group<2 else (673,713)
        chart['neo_math_questions'].append(dict(root=root,group=group,positions=positions,
            start=round(chapter_time(chart,start)*FPS),end=round(chapter_time(chart,end)*FPS)))


def table_source(out,levels):
    rows=[];starts=[];counts=[];modes=[]
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text());entries=chart.get('neo_math_questions',[])
        starts.append(len(rows)*20);counts.append(len(entries))
        modes.append(32 if chart.get('code')=='T3EX-X' else 0)
        for e in entries:rows.append([e['root'],e['start'],e['end'],*sum(e['positions'],[]),e['group']])
    lines=['neo_math_starts: .word '+','.join(map(str,starts)),
           'neo_math_counts: .word '+','.join(map(str,counts)),
           'neo_math_modes: .word '+','.join(map(str,modes)), 'neo_math_records:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in rows]
    # A fixed stride makes selecting a question and its two answers atomic.
    lines+=['neo_math_pools:']
    for variants in POOLS.values():
        for question,correct,wrong in variants:
            for text in (question+'=',str(correct),str(wrong)):
                raw=text.encode('ascii');assert len(raw)<16
                lines+=['.byte '+','.join(map(str,raw+bytes(16-len(raw))))]
    lines+=['neo_math_pool_choices:']
    for code in ('T3-X','T3EX-X'):
        for speed in (10,13,16,20):
            lines+=['.word '+','.join(str(POOL_NAMES.index(pool(code,g,speed))*192) for g in range(4))]
    lines+=['neo_math_font_tiles: .byte '+','.join(str(234+FONT_CHARS.index(chr(i)) if chr(i) in FONT_CHARS else 0) for i in range(128))]
    return '\n'.join(lines)+'\n'
