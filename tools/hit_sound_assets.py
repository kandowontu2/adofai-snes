"""Original per-floor sound selection and cartridge-resident SPC sample banks."""
import hashlib,json,math,struct,subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1]

def sample(name,rate):
    source=ROOT/f'assets/private/hitsounds/snd{name}.wav'
    key=hashlib.sha256(source.read_bytes()+str(rate).encode()+b'v1').hexdigest()[:16]
    out=ROOT/'build/hit-samples';out.mkdir(exist_ok=True)
    target=out/f'{name}-{key}.brr'
    if target.exists():return target.read_bytes()
    hz,pcm=wavfile.read(source)
    if pcm.ndim>1:pcm=pcm.astype(float).mean(axis=1)
    pcm=resample_poly(pcm.astype(float),rate,hz)
    pcm=np.pad(pcm,(0,(-len(pcm))%16))
    raw=target.with_suffix('.raw');np.clip(pcm,-32768,32767).astype('<i2').tofile(raw)
    subprocess.run([str(ROOT/'.tools/brr_encode.exe'),str(raw),str(target)],check=True,capture_output=True)
    b=bytearray(target.read_bytes())
    for i in range(0,len(b),9):b[i]&=252
    b[-9]|=1;target.write_bytes(b);raw.unlink()
    return bytes(b)

def selections(chart,source):
    events={}
    for event in source['events']:events[event['floor']]=event
    normal=mid=source['hitsound'];volume=source['hitsoundVolume'];use_mid=False;set_mid=False
    result=[]
    for i,note in enumerate(chart['notes']):
        e=events.get(i) if i else None
        if e:
            if e.get('gameSound')=='Midspin':use_mid=True;mid=e['hitsound']
            else:
                normal=e['hitsound']
                if not set_mid:set_mid=True;mid=normal
            volume=e['hitsoundVolume']
        sound=mid if i and chart['notes'][i-1]['flags']&16 and use_mid else normal
        if normal=='None':sound='None'
        result.append((sound,max(0,min(127,round(volume*.76)))))
    # A manual input may arrive before the automatic midspin has advanced
    # the gameplay cursor. It still belongs to the following hittable floor.
    for i in range(len(result)-2,-1,-1):
        if chart['notes'][i]['flags']&8:result[i]=result[i+1]
    return result

def compile_bank(chart,source):
    selected=selections(chart,source);names=sorted({n for n,v in selected if n!='None'})
    assert len(names)<=28
    choices=(16000,12000,8000,6000,4000);quality={n:0 for n in names}
    while True:
        samples={n:sample(n,choices[quality[n]]) for n in names};regions=[[0x1200,0x4000],[0xC000,0xFFFF]];positions={}
        for name in sorted(names,key=lambda n:-len(samples[n])):
            for r in regions:
                if r[0]+len(samples[name])<=r[1]:positions[name]=r[0];r[0]+=len(samples[name]);break
            else:break
        if len(positions)==len(names):break
        candidates=[n for n in names if quality[n]+1<len(choices)]
        if not candidates:raise ValueError(('Original hit sounds do not fit SPC RAM',chart['id'],names))
        quality[max(candidates,key=lambda n:len(samples[n]))]+=1
    bank=bytearray(0xEDFF);directory=bytearray(114);slots={name:4+i for i,name in enumerate(names)}
    for name in names:
        at=positions[name];data=samples[name];bank[at-0x1200:at-0x1200+len(data)]=data
        struct.pack_into('<HH',directory,(slots[name]-4)*4,at,at)
    notes=bytearray()
    for name,volume in selected:
        rate=choices[quality[name]] if name in quality else 16000
        notes+=bytes([slots.get(name,2)|((rate//2000&7)<<5),0 if name=='None' else volume])
    chunks=[]
    for start,end in ((0x1200,regions[0][0]),(0xC000,regions[1][0])):
        data=bytes(bank[start-0x1200:end-0x1200]);chunks.append(data+bytes((-len(data))%3))
    return bytes(notes),bytes(directory)+b''.join(chunks),dict(rates_hz={n:choices[quality[n]] for n in names},sounds=names,bytes=sum(map(len,samples.values())),packet_counts=[len(c)//3 for c in chunks])

def add_assets(assets,charts,out):
    path=ROOT/'assets/private/hitsound-levels.json'
    if not path.exists():return False
    sources=json.loads(path.read_text());report=[]
    for chart in charts:
        n=chart['id'];notes,bank,row=compile_bank(chart,sources[str(n)])
        assets[f'hitnotes{n}']=notes;assets[f'hitbank{n}']=bank;report.append(dict(id=n,**row))
    assets['hitdescriptors']=bytes(16*len(charts))
    (out/'hit-sounds.json').write_text(json.dumps(report,indent=2))
    return True
