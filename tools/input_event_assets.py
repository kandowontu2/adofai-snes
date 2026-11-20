"""Authored left/right action filters; no render-clock dependence."""
import json
from pathlib import Path
from make_assets import FPS
from track_motion import enabled
ROOT=Path(__file__).resolve().parents[1]
ACTION_MASKS={'Action1':0x0f20,'Action2':0xc0d0}

def schedule(data,chart):
 actions=[a for a in data.get('featured_actions',[]) if a.get('eventType')=='SetInputEvent' and enabled(a.get('active',True))]
 events=[]
 for order,a in enumerate(actions):
  if a.get('state','Down')!='Down':continue
  if a.get('target') not in ACTION_MASKS or a.get('targetEventTag','NONE') not in ('','NONE') or a.get('eventTag','') not in ('','NONE'):
   raise ValueError(('Unsupported input callback',a))
  n=chart['notes'][a['floor']]
  frame=max(0,round((n['time']+a.get('angleOffset',0)/180*60/data['bpm']/n['speed'])*FPS))
  events.append((frame,order,ACTION_MASKS[a['target']],enabled(a.get('ignoreInput',False))))
 rows=[];mask=0
 for t,order,bits,ignore in sorted(events):
  mask=(mask|bits) if ignore else (mask&~bits)
  if rows and rows[-1][0]==t:rows[-1]=(t,mask)
  else:rows.append((t,mask))
 return rows

def tables(folder,levels):
 from pack_sources import source_path
 rows=[];starts=[];ends=[]
 for n in levels:
  starts.append(len(rows)*4)
  path=source_path(folder,n)
  data=json.loads(path.read_text()) if n>=75 and path.exists() else {}
  if any(a.get('eventType')=='SetInputEvent' for a in data.get('featured_actions',[])):
   rows+=schedule(data,json.loads((Path(folder)/f'level{n}.json').read_text()))
  ends.append(len(rows)*4)
 if not rows:return ''
 return '\n.ifdef NEO_BUILD\n.segment "NEOCODE"\n.else\n.segment "RODATA"\n.endif\ninput_event_starts: .word '+','.join(map(str,starts))+'\ninput_event_ends: .word '+','.join(map(str,ends))+'\ninput_event_rows: .word '+','.join(str(v) for row in rows for v in row)+'\n.segment "RODATA"\n'
