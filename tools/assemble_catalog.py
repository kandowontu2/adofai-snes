"""Assemble a master from complete per-song catalog renders, without PCM."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def ready_renders(ids,rendered,wait):
    pending=list(ids);deadline=time.monotonic()+24*3600;announced=None
    while pending:
        ready=[]
        for n in pending:
            path=rendered/str(n)/'result.json'
            if path.exists() and json.loads(path.read_text()).get('passed'):ready.append(n)
        if not ready:
            assert wait,('Incomplete renders',pending)
            assert time.monotonic()<deadline,('Render wait expired',pending)
            if announced!=pending:
                print('WAITING FOR RENDERS',pending,flush=True);announced=list(pending)
            time.sleep(3);continue
        for n in ready:
            pending.remove(n);yield n


def assemble(catalog, rendered, out, levels=None, imports=None,wait=False,storage_plan=None,stage_only=False):
    ids=levels or json.loads(catalog.read_text())['levels']
    out.mkdir(parents=True,exist_ok=True)
    assert not (out/'adofai.sfc').exists(),'Use a fresh output directory to preserve verified builds'
    pack=dict(title='ADOFAI COMPLETE MASTER',levels=ids,code='master',release_ready=False,native_packet_compression=True)
    omitted=set()
    if storage_plan:
        plan=json.loads(storage_plan.read_text());assert plan['passed'] and plan['levels']==ids
        omitted={r['id'] for r in plan['omitted_scenery']}
        pack['omitted_optional_scenery']=sorted(omitted)
        shutil.copyfile(storage_plan,out/'storage-plan.json')
    (out/'pack.json').write_text(json.dumps(pack,indent=2))
    frozen=out/'source-imports';frozen.mkdir(exist_ok=True)
    for n in ready_renders(ids,rendered,wait):
        folder=rendered/str(n)
        receipt=json.loads((folder/'result.json').read_text())
        assert receipt['passed'] and receipt['id']==n
        imported=folder/'source-level.json'
        if not imported.exists():imported=(imports or rendered.parent/'raw')/str(n)/'source-level.json'
        assert hashlib.sha256(imported.read_bytes()).hexdigest()==receipt['source_sha256'],(n,'Imported source changed after rendering')
        if storage_plan:assert plan['source_sha256'][str(n)]==receipt['source_sha256'],(n,'Storage plan belongs to a different imported chart')
        shutil.copyfile(imported,frozen/f'level{n}.json')
        on=folder/('off' if n in omitted else 'on')
        assert n not in omitted or 'off' in receipt['variants']
        for path in on.iterdir():
            if path.suffix in ('.bin','.brr') or path.name in (
                    f'level{n}.json',f'level{n}-audio.json',f'level{n}-hit-mix.json'):
                shutil.copyfile(path,out/path.name)
        # Older render receipts predate audio-cache forwarding. Recover the
        # raw compiler's stamp only when it describes these exact BRR bytes;
        # encode_music still validates its waveform, timing and sample hashes.
        raw=(imports or rendered.parent/'raw')/str(n)
        if (raw/f'level{n}.brr').exists() and (raw/f'level{n}.brr').read_bytes()==(out/f'level{n}.brr').read_bytes():
            for name in (f'level{n}-audio.json',f'level{n}-hit-mix.json'):
                if (raw/name).exists() and not (out/name).exists():shutil.copyfile(raw/name,out/name)
        chart=json.loads((out/f'level{n}.json').read_text())
        if n in omitted:
            assert chart['decoration_vfx_off'] and n not in (68,73)
            chart['optional_scenery_omitted']='master_data_budget'
            (out/f'level{n}.json').write_text(json.dumps(chart,indent=2))
        assert chart['mode1_snapshot'] and chart['snapshot_map_top']==16 and not chart.get('snapshot_preview')
        if 'off' in receipt['variants'] and n not in omitted:
            assert n not in (68,73),'T3 gameplay effects cannot be optional'
            off=folder/'off';reference=out/f'vfx-off-{n}';reference.mkdir(exist_ok=True)
            alternate_source=reference/'source-imports';alternate_source.mkdir(exist_ok=True)
            shutil.copyfile(imported,alternate_source/f'level{n}.json')
            for path in off.iterdir():
                if path.suffix=='.bin' or path.name==f'level{n}.json':
                    shutil.copyfile(path,reference/path.name)
            meta=json.loads((reference/f'level{n}.json').read_text())
            for field in ('notes','checkpoints','hits','steps','duration'):
                assert chart[field]==meta[field],(n,field,'VFX changed gameplay')
            alt={key:meta[key] for key in ('stream_packets','mode1_glyph_count','wide_snapshot_atlas','snapshot_frames','snapshot_map_top')}
            alt.update(verification_source=reference.name,compact_snapshot_seeds=0)
            chart['vfx_off']=alt
            for prefix in ('stream_index','stream_data','mode1_seeds'):
                shutil.copyfile(off/f'{prefix}{n}.bin',out/f'{prefix}_vfx_off{n}.bin')
            (out/f'level{n}.json').write_text(json.dumps(chart,indent=2))
    shutil.copyfile(catalog,out/'source-import-report.json')
    if stage_only:
        # Plan the same lossless seed/pose representation used by build_sa1,
        # rather than counting the renderer's uncompressed restart atlases.
        from compact_snapshot_seeds import patch_pack as compact_seeds
        from snapshot_sharing import patch_pack as share_snapshots
        from snapshot_seed_references import patch_pack as reference_seeds
        print('Preparing lossless restart data',flush=True)
        print('Restart atlas bytes saved:',compact_seeds(out),flush=True)
        print('Repeated pose bytes saved:',share_snapshots(out),flush=True)
        print('Restart-reference bytes saved:',reference_seeds(out),flush=True)
        print('STAGED',len(ids),'CHARTS; generate a storage plan before assembling',flush=True)
        return
    subprocess.run([sys.executable,str(ROOT/'tools/build_sa1.py'),'--source',str(out),'--out',str(out),'--no-pcm'],cwd=ROOT,check=True)
    print('ASSEMBLED',len(ids),'CHARTS',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--rendered',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--levels',type=int,nargs='+')
    parser.add_argument('--imports',type=Path,help='Raw per-level imports when older render receipts lack a frozen source copy')
    parser.add_argument('--wait-for-renders',action='store_true',help='Stage completed songs while the remaining render jobs finish')
    parser.add_argument('--storage-plan',type=Path,help='Optional scenery budget from plan_catalog_storage.py; gameplay caches remain complete')
    parser.add_argument('--stage-only',action='store_true',help='Prepare source assets for storage planning without building ROM/MSU files')
    args=parser.parse_args()
    assemble(args.catalog,args.rendered,args.out,args.levels,args.imports,args.wait_for_renders,args.storage_plan,args.stage_only)
