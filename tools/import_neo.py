"""Read Neo Cosmos scenes from the user's installed DLC, including native effects.

Generated free-roam cells are separate from the ordered musical floor list.
They must never be sorted into it: their seqIDs repeat those of their region.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
import UnityPy
from UnityPy.files.ObjectReader import get_typetree_node
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

from import_campaign import DEFAULT_GAME
from import_hitsounds import SOUNDS
from neo_catalog import NEO

ROOT = Path(__file__).resolve().parents[1]
TRACK_EFFECTS = {'ffxChangeTrack', 'ffxFloorAppearPlus', 'ffxFloorDisappearPlus',
                 'ffxMoveFloorPlus', 'ffxRecolorFloorPlus'}
CHAPTER_TYPES = {'Mawaru','Mawaru2','Mawaru_Coin','DivineIntervention','LaserSpawner'}


def import_scene(objects, meta, out, all_clips):
    transforms, by_object, game_objects, floors, effects = {}, {}, {}, [], {}
    controllers, conductors, cameras, clips, renderers = [], [], [], {}, {}
    song_clip = None
    chapter_entities=[]
    colliders={}
    classes = Counter()
    for obj, cls in objects:
        classes[cls] += 1
        if cls == 'AudioClip':
            clip = obj.read()
            clips[clip.m_Name] = clip
            continue
        if cls not in {'Transform', 'GameObject', 'scrFloor', 'scrController',
                       'scrConductor', 'scrCamera', 'SpriteRenderer', 'MeshRenderer','BoxCollider2D'} | CHAPTER_TYPES and not cls.startswith('ffx'):
            continue
        d = obj.read_typetree()
        go = d.get('m_GameObject', {}).get('m_PathID')
        if cls in CHAPTER_TYPES:chapter_entities.append((obj.path_id,cls,d))
        if cls=='BoxCollider2D':colliders[go]=d
        if cls == 'Transform':
            transforms[obj.path_id] = d
            by_object[go] = obj.path_id
        elif cls == 'GameObject':
            game_objects[obj.path_id] = d
        elif cls == 'scrFloor':
            floors.append(d)
        elif cls == 'scrController':
            controllers.append(d)
        elif cls == 'scrConductor':
            conductors.append(d)
            for field in ('song', 'song2', 'song3'):
                pointer = getattr(obj.read(), field)
                if pointer.m_PathID:
                    source = pointer.deref().read()
                    if source.m_audioClip.m_PathID:
                        song_clip = source.m_audioClip.deref().read()
                        break
        elif cls == 'scrCamera':
            cameras.append(d)
        elif cls == 'SpriteRenderer':
            renderers[go] = d['m_Color']
        elif cls == 'MeshRenderer' and d.get('m_Materials') and d['m_Materials'][0]['m_PathID']:
            material = obj.read().m_Materials[0].deref().read_typetree()
            color = dict(material['m_SavedProperties']['m_Colors']).get('_Color')
            if color is not None:
                renderers[go] = color
        elif cls.startswith('ffx') and d.get('m_Enabled', 1):
            effects[obj.path_id] = dict(d, type=cls)

    ordered = sorted((f for f in floors if not f.get('freeroamGenerated')), key=lambda f: f['seqID'])
    assert [f['seqID'] for f in ordered] == list(range(len(ordered))), meta['code']
    assert len(conductors) == 1 and len(controllers) == 1, meta['code']
    cond, controller = conductors[0], controllers[0]
    cache = {}

    def world(i):
        if not i:
            return np.eye(4)
        if i not in cache:
            t = transforms[i]
            m = np.eye(4)
            m[:3, :3] = Rotation.from_quat([t['m_LocalRotation'][k] for k in 'xyzw']).as_matrix() @ np.diag([t['m_LocalScale'][k] for k in 'xyz'])
            m[:3, 3] = [t['m_LocalPosition'][k] for k in 'xyz']
            cache[i] = world(t['m_Father']['m_PathID']) @ m
        return cache[i]

    def position(f):
        return world(by_object[f['m_GameObject']['m_PathID']])[:2, 3].tolist()

    # Match Unity component order, including simultaneous camera/track changes.
    ordered_effects = []
    for f in ordered:
        for order, item in enumerate(game_objects[f['m_GameObject']['m_PathID']]['m_Component']):
            pointer = item.get('component', item)
            effect = effects.get(pointer['m_PathID'])
            if effect is not None:
                ordered_effects.append(dict(effect, floor=f['seqID'], component_order=order))
    colors = [dict(color=renderers.get(f['m_GameObject']['m_PathID'], 'a7c2da'),
                   style=f.get('initialTrackStyle', 0), disableGlow=f.get('disableGlow', False)) for f in ordered]
    track = [e for e in ordered_effects if e['type'] in TRACK_EFFECTS]
    for e in track:
        if e['type'] == 'ffxChangeTrack':
            for key in ('color1', 'color2'):
                value = e.get(key, {})
                if isinstance(value, dict) and all(value.get(k, 0) == 0 for k in 'rgba'):
                    e[key] = colors[e['floor']]['color']
    chart = dict(meta, neo_cosmos=True, source='Installed Neo Cosmos scene ' + meta['code'],
                 bpm=cond['bpm'], offset=cond['addoffset'], countdown=cond['countdownTicks'],
                 separate_countdown=bool(cond['separateCountdownTime']), floors=ordered,
                 checkpoints=[dict(floor=e['floor'], tileOffset=e['checkpointTileOffset']) for e in ordered_effects if e['type'] == 'ffxCheckpoint'],
                 native_positions=[position(f) for f in ordered], native_layout_version=2,
                 native_tile_size=controller.get('tileSize', 1.5),
                 native_component_notation=controller.get('useComponentNotationForFx', True),
                 native_controller_stick_to_floor=bool(controller.get('stickToFloor', False)),
                 native_track_effects=track, native_track_initial=[f.get('opacityVal', 1) for f in ordered],
                 native_track_colors=colors, track_color_import=1,
                 hidden_icons=[bool(f.get('hideIcon') or f.get('floorIcon') == 18) for f in ordered],
                 camera_initial=next((c.get('zoomSize', 1.) for c in cameras), 1.),
                 camera_actions=[], native_camera_effects=[e for e in ordered_effects if e['type'] == 'ffxCameraPlus'],
                 native_effects=ordered_effects,
                 freeroam_cells=[dict(f, position=position(f)) for f in floors if f.get('freeroamGenerated')],
                 freeroam_angle_interval=controller.get('freeroamAngleInterval', 90),
                 freeroam_angle_offset=controller.get('freeroamAngleOffset', 0),
                 native_holdsound={k: v for k, v in cond.items() if k.startswith('hold')})
    chart['native_hit_volume']=cond['hitSoundVolume']
    chart['native_countdown_multiplier']=cond.get('countdownSpeedMultiplier',1.)
    chart['native_chapter_entities']=[dict(path_id=i,type=cls,data=d,position=position(d)) for i,cls,d in chapter_entities]
    from neo_warps import extract,extract_math
    chapter=next((d for _,cls,d in chapter_entities if cls=='Mawaru'),None)
    if chapter is not None:
        chart['native_warps']=extract({o.path_id:o for o,_ in objects},chapter,world,by_object)
        chart['native_math']=extract_math({o.path_id:o for o,_ in objects},chapter,world,by_object,meta['code']=='T3EX-X')
    for entity in chart['native_chapter_entities']:
        if entity['type']!='LaserSpawner':continue
        go=entity['data']['m_GameObject']['m_PathID'];t=by_object[go]
        entity['matrix']=world(t).tolist()
        entity['parent_matrix']=world(transforms[t]['m_Father']['m_PathID']).tolist()
        entity['collider']=colliders.get(go)
    (out / f'level{meta["id"]}.json').write_text(json.dumps(chart, indent=2), encoding='utf8')
    clip = song_clip or all_clips.get(meta['code'])
    if clip is None and meta['code'] == 'T2EX-X':
        clip = all_clips.get('T2-X')
    if clip is None:
        raise ValueError(f'Missing music for {meta["code"]}: {list(clips)}')
    chart['native_audio_clip'] = clip.m_Name
    (out / f'level{meta["id"]}.json').write_text(json.dumps(chart, indent=2), encoding='utf8')
    (out / f'{meta["id"]}-X.wav').write_bytes(next(iter(clip.samples.values())))
    hits = dict(hitsound=SOUNDS[cond['hitSound']], hitsoundVolume=cond['hitSoundVolume'] * 100,
                countdownSpeedMultiplier=cond.get('countdownSpeedMultiplier', 1),
                events=[dict(floor=e['floor'], gameSound='Midspin' if e['gameSound'] == 1 else 'Hitsound',
                             hitsound=SOUNDS[e['hitSound']], hitsoundVolume=e['volume'] * 100)
                        for e in ordered_effects if e['type'] == 'ffxSetHitsound'])
    return chart, hits, dict(classes)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game', type=Path, default=Path(DEFAULT_GAME))
    ap.add_argument('--out', type=Path, default=ROOT / 'assets/private')
    args = ap.parse_args()
    bundle = args.game / 'Bundles/neocosmos_scenes_all.bundle'
    if not bundle.exists():
        raise SystemExit('Install Neo Cosmos in your ADOFAI Steam installation first: ' + str(bundle))
    env = UnityPy.load(str(args.game / 'Bundles'))
    gen = TypeTreeGenerator(next(iter(env.objects)).assets_file.unity_version)
    gen.load_local_game(str(args.game))
    env.typetree_generator = gen
    metadata = {m['code']: m for m in NEO}
    scenes = {}
    for o in env.objects:
        if o.type.name == 'AssetBundle':
            for name, key in o.read_typetree().get('m_SceneHashes', []):
                if Path(name).stem in metadata:
                    scenes[key] = metadata[Path(name).stem]
    assert len(scenes) == len(NEO), 'DLC scene catalog is incomplete'
    groups = {key: [] for key in scenes}
    scripts = {}
    all_clips = {o.read().m_Name: o.read() for o in env.objects if o.type.name == 'AudioClip'}
    # Shared assets are grouped with their scene; never merge equal local IDs.
    for obj in env.objects:
        key = obj.assets_file.name.removesuffix('.sharedAssets')
        if key not in groups:
            continue
        cls = obj.type.name
        if cls == 'MonoBehaviour':
            base = obj.read_typetree(nodes=get_typetree_node(114, obj.version), wrap=True, check_read=False)
            if not base.m_Script.m_PathID:
                continue
            script = base.m_Script.deref()
            sid = (script.assets_file.name, script.path_id)
            if sid not in scripts:
                scripts[sid] = script.read().m_ClassName
            cls = scripts[sid]
        groups[key].append((obj, cls))
    args.out.mkdir(parents=True, exist_ok=True)
    hitpath = args.out / 'hitsound-levels.json'
    hits = json.loads(hitpath.read_text()) if hitpath.exists() else {}
    audit = []
    for key, meta in sorted(scenes.items(), key=lambda row: row[1]['id']):
        chart, hitdata, classes = import_scene(groups[key], meta, args.out, all_clips)
        hits[str(meta['id'])] = hitdata
        row = dict(meta, floors=len(chart['floors']), holds=sum(f['holdLength'] >= 0 for f in chart['floors']),
                   freeroam_regions=sum(bool(f['freeroam']) for f in chart['floors']),
                   freeroam_cells=len(chart['freeroam_cells']), classes=classes)
        audit.append(row)
        print(meta['code'], row['floors'], 'floors,', row['holds'], 'holds,', row['freeroam_regions'], 'free-roam regions', flush=True)
    hitpath.write_text(json.dumps(hits, indent=2), encoding='utf8')
    (args.out / 'neo-catalog.json').write_text(json.dumps(dict(bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(), levels=audit), indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
