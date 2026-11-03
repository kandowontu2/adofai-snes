"""Import only 1-X's chart and music from a local ADOFAI installation."""
import argparse
import json
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node

DEFAULT_GAME = r'C:\Program Files (x86)\Steam\steamapps\common\A Dance of Fire and Ice'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', type=Path, default=Path(DEFAULT_GAME))
    args = ap.parse_args()
    data = args.game/'A Dance of Fire and Ice_Data'
    out = Path(__file__).resolve().parents[1]/'assets/private'
    out.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(data/'level8'))
    gen = TypeTreeGenerator(env.objects[0].assets_file.unity_version)
    gen.load_local_game(str(args.game))
    env.typetree_generator = gen
    floors = []
    conductor = None
    for o in env.objects:
        if o.type.name != 'MonoBehaviour':
            continue
        base = o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        script = base.m_Script.deref().read()
        if script.m_ClassName == 'scrFloor':
            d = o.read_typetree()
            floors.append({k:d[k] for k in ('seqID','entryangle','exitangle','speed','isCCW','extraBeats','midSpin')})
        elif script.m_ClassName == 'scrConductor':
            conductor = o.read_typetree()
    floors.sort(key=lambda f:f['seqID'])
    assert len(floors)==168 and conductor['bpm']==150, 'Unexpected game version / chart'
    chart = {'title':'A Dance of Fire and Ice','artist':'fizzd','bpm':conductor['bpm'],
             'offset':conductor['addoffset'],'countdown':conductor['countdownTicks'],'floors':floors}
    (out/'level1.json').write_text(json.dumps(chart,indent=2),encoding='utf-8')
    env = UnityPy.load(str(data/'sharedassets1.assets'))
    for o in env.objects:
        if o.type.name == 'AudioClip':
            clip = o.read()
            if clip.m_Name == '1-X':
                samples = clip.samples
                assert len(samples)==1
                (out/'1-X.wav').write_bytes(next(iter(samples.values())))
                break
    else:
        raise RuntimeError('1-X audio was not found')
    print('Imported 167 steps and 1-X music into assets/private.')

if __name__=='__main__':
    main()
