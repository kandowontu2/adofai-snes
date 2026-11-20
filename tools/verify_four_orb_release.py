"""Check all four scripted planets in actual MesenCE screenshots."""
import argparse,csv,json,math,subprocess,sys
from pathlib import Path
from PIL import Image
from verification_data import identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]
BODY_ORACLE_VERSION=2


def largest_component(points):
    remaining=set(points);largest=[]
    while remaining:
        pending=[remaining.pop()];component=[]
        while pending:
            x,y=pending.pop();component.append((x,y))
            for adjacent in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if adjacent in remaining:
                    remaining.remove(adjacent);pending.append(adjacent)
        if len(component)>len(largest):largest=component
    return largest

def inspect(path):
    image=Image.open(path).convert('RGB')
    assert image.size==(256,224),image.size
    points={c:[] for c in ('red','green','blue','yellow')}
    for y in range(16,176):
        for x in range(256):
            r,g,b=image.getpixel((x,y))
            c=('red' if r>180 and g<100 and b<100 else
               'green' if g>180 and r<100 and b<100 else
               'blue' if b>160 and g<200 and r<100 else
               'yellow' if r>180 and g>140 and b<100 else None)
            if c:points[c].append((x,y))
    centers={};body_pixels={};ignored_pixels={}
    for color,pixels in points.items():
        # The red count symbol on a nearby tile is also bright red. Its
        # separate small dots must not pull the planet's centroid sideways.
        body=largest_component(pixels)
        assert len(body)>=30,(path,color,'planet missing/clipped',len(body))
        centers[color]=[sum(p[i] for p in body)/len(body) for i in (0,1)]
        body_pixels[color]=len(body);ignored_pixels[color]=len(pixels)-len(body)
    values=list(centers.values())
    diameter=max(math.dist(a,b) for a in values for b in values)
    nearest=min(math.dist(a,(128,104)) for a in values)
    # Native 12% scale: ~24px sides, ~34px diagonal, around the
    # current landing tile. Unscaled pivots put the group ~100px away.
    assert 25<=diameter<=45,(path,'four-orb orbit radius',diameter,centers)
    assert nearest<=36,(path,'four-orb group detached from playfield',nearest,centers)
    return dict(centers=centers,diameter=diameter,nearest=nearest,body_pixels=body_pixels,ignored_pixels=ignored_pixels)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack
    ids=json.loads((base/'pack.json').read_text())['levels'];local=ids.index(288)+1
    chart=json.loads((base/'level288.json').read_text());frozen=identity(base/'adofai.sfc')
    # The authored entry first shows two planets, then a black-to-blue
    # insertion. Check all four colors after that transition.
    steps=(53,54,55,60,81,101,121,161,201,241,257)
    times=[chart['notes'][n]['frame'] for n in steps]
    for off in (False,True):
        suffix='-vfx-off' if off else ''
        subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',args.pack,
                        '--levels',str(local),'--autoplay','--sampled-graphics',
                        *(['--vfx-off'] if off else []),'--capture-times',*map(str,times)],check=True)
        folder=base/f'verification/mesen-{local}-autoplay{suffix}'
        presented={int(row[0]):int(row[1]) for row in csv.reader((folder/'screen-capture-times.csv').open())}
        samples=[dict(step=n,requested=t,presented=presented[t],**inspect(folder/f'screen-{t}.png'))
                 for n,t in zip(steps,times)]
        subprocess.run([sys.executable,str(ROOT/'tools/verify_mesen_ppu.py'),'--pack',args.pack,
                        '--level',str(local),'--folder',str(folder)],check=True)
        assert identity(base/'adofai.sfc')==frozen
        result=dict(passed=True,**frozen,suite_digest=suite_digest(),body_oracle_version=BODY_ORACLE_VERSION,samples=samples,vfx_off=off)
        (base/f'verification/four-orb-visibility{suffix}.json').write_text(json.dumps(result,indent=2))
        print('FOUR-ORB VISIBILITY PASS',len(samples),'VFX OFF' if off else 'VFX ON',flush=True)

if __name__=='__main__':main()
