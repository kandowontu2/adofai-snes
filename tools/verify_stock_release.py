"""Recover exact-build release evidence and run final sequential regressions."""
import argparse,concurrent.futures,json,subprocess,sys
from pathlib import Path
from verification_data import identity,freeze_data_identity
from run_mesen_campaign import suite_digest
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/stock-refresh-master'
V=BASE/'verification'
def run(tool,*args):
    subprocess.run([sys.executable,str(ROOT/'tools'/tool),*map(str,args)],cwd=ROOT,check=True)
def read(path):return json.loads(path.read_text())
def bound(path,frozen):
    d=read(path)
    assert d.get('passed') and all(d.get(k)==v for k,v in frozen.items()),str(path)
    return d
def regressions(frozen,ids,workers=1):
    run('verify_menu_mode_mesen.py','--pack',BASE.name)
    run('verify_msu_header_mesen.py','--pack',BASE.name)
    sequence=[65,70,67,94,144,1]
    pairs=list(zip(sequence,sequence[1:]))
    for first,second in ((286,68),(287,1),(288,289),(296,62),(292,294),(294,296),(63,68),(65,74)):
        if first in ids and second in ids:
            pairs.append((ids.index(first)+1,ids.index(second)+1))
    # Keep both charts in the same emulator session for each transition,
    # without registering six simultaneous copies of the hardware probes.
    def check_pair(pair):
        first,second=pair
        path=V/f'sequence-{first}-{second}/manifest.json'
        prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_sequence.py','--pack',BASE.name,'--levels',first,second)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(check_pair,pairs):pass
    for n in (75,251):
        run('run_mesen_campaign.py','--pack',BASE.name,'--levels',ids.index(n)+1,'--prepare-only')
        run('verify_decoration_hitboxes_mesen.py','--pack',BASE,'--level-id',n)
    assert identity(BASE/'adofai.sfc')==frozen
    result=dict(**frozen,passed=True,suite_digest=suite_digest(),sequence_pairs=pairs,hazards=[75,251])
    (V/'release-regressions.json').write_text(json.dumps(result,indent=2))
    return result

def main():
    global BASE,V
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',default='stock-refresh-master')
    parser.add_argument('--regressions-only',action='store_true')
    parser.add_argument('--catalog-only',action='store_true',help='Validate all exact-build replay evidence before running independent release features')
    parser.add_argument('--regression-workers',type=int,default=1,help='Independent emulator processes for consecutive-level pairs')
    args=parser.parse_args();BASE=ROOT/'build/packs'/args.pack;V=BASE/'verification'
    frozen=identity(BASE/'adofai.sfc',fresh=True);ids=read(BASE/'pack.json')['levels'];rows=[]
    freeze_data_identity(BASE/'adofai.sfc',frozen)
    assert len(ids)==len(set(ids)) and ids
    if args.regressions_only:
        regressions(frozen,ids,args.regression_workers)
        print('RELEASE REGRESSIONS PASS; CATALOG STILL REQUIRED',flush=True)
        return
    for local,n in enumerate(ids,1):
        folder=V/f'mesen-{local}-autoplay'
        m=bound(folder/'manifest.json',frozen)
        assert (folder/'result.txt').read_text().endswith('PASS\n')
        assert m['suite_digest']==suite_digest(),f'Replay oracle stale: {n}'
        chart=read(BASE/f'level{n}.json')
        if chart.get('mode1_tracks')==3 and 'EXTENDED_CHART_BUILD = 1' in (BASE/'addresses.inc').read_text():
            jobs=folder/'snapshot-icon-jobs.txt'
            assert jobs.exists() and int(jobs.read_text())>=100,('Missing independent snapshot icon coverage',n)
        if 253<=n<=283:
            import re
            geometry=(folder/'triplet-geometry.txt').read_text()
            count=re.search(r'oriented_triangles=(\d+)',geometry)
            assert geometry.startswith('PASS ') and count and int(count[1])>0,('Missing live triplet geometry coverage',n)
            memory=(folder/'twirl-stream-memory.txt').read_text()
            assert memory.startswith('PASS checks=') and int(memory.split('=')[1])>0,('Missing twirl/stream isolation coverage',n)
            if n==256:
                handoffs=re.search(r'twirl_handoffs=(\d+)',geometry)
                assert handoffs and int(handoffs[1])>=7,'Missing live twirl handoff coverage'
        pp=folder/'ppu-verification.json'
        if not pp.exists():run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',folder)
        bound(pp,frozen)
        rows.append(dict(id=n,local=local,passed=True,validation_suite_digest=m['suite_digest']))
    report=dict(**frozen,passed=True,complete=True,suite_digest=suite_digest(),results=rows)
    (V/'catalog/results.json').write_text(json.dumps(report,indent=2))
    print(f'CATALOG {len(ids)} PASS',flush=True)
    if args.catalog_only:
        assert identity(BASE/'adofai.sfc',fresh=True)==frozen
        return
    import re
    for n in (69,74,253):
        if n not in ids:continue
        p=V/f'mesen-{ids.index(n)+1}-autoplay/planet-previews.txt'
        match=re.search(r'PASS circles=(\d+) dashes=(\d+)',p.read_text())
        assert match and int(match[1])>0 and int(match[2])==9*int(match[1]),('Missing three-planet guide coverage',n)
    path=V/'release-regressions.json'
    previous=read(path) if path.exists() else {}
    if not (previous.get('passed') and previous.get('suite_digest')==suite_digest()
            and all(previous.get(k)==v for k,v in frozen.items())):
        previous=regressions(frozen,ids,args.regression_workers)
    features=[]
    if 'REFERENCE_SNAPSHOT_SEEDS = 1' in (BASE/'addresses.inc').read_text():
        path=V/'snapshot-storage.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_snapshot_storage.py','--pack',BASE.name)
        bound(path,frozen);features.append('snapshot-storage.json')
    if 'SYMBOL_SCALE_BUILD = 1' in (BASE/'addresses.inc').read_text():
        path=V/'symbol-scale-boot/verification.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_symbol_scale_boot_mesen.py','--pack',BASE.name)
        bound(path,frozen);features.append('symbol-scale-boot/verification.json')
    if 256 in ids:
        path=V/'twirl-memory-negative.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_twirl_memory_negative.py','--pack',BASE.name)
        bound(path,frozen);features.append('twirl-memory-negative.json')
    if 285 in ids:
        bound(V/'symbol-performance.json',frozen);features.append('symbol-performance.json')
        path=V/'snapshot-icon-negative.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_snapshot_icons_negative.py','--pack',BASE.name)
        bound(path,frozen);features.append('snapshot-icon-negative.json')
    if 288 in ids:
        path=V/'four-orb-visibility.json';prior=read(path) if path.exists() else {}
        alternate=V/'four-orb-visibility-vfx-off.json';other=read(alternate) if alternate.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())
                and other.get('passed') and other.get('suite_digest')==suite_digest()
                and all(other.get(k)==v for k,v in frozen.items())):
            run('verify_four_orb_release.py','--pack',BASE.name)
        bound(path,frozen);features.append('four-orb-visibility.json')
        bound(alternate,frozen);features.append('four-orb-visibility-vfx-off.json')
    if any(read(BASE/f'level{n}.json').get('mawaru_headings') for n in ids if n in (68,73)):
        path=V/'neo-headings.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_neo_headings_release.py','--pack',BASE.name)
        bound(path,frozen);features.append('neo-headings.json')
    for level,tool,report in (
            (140,'verify_coordinate_dma_mesen.py','coordinate-dma/verification.json'),
            (284,'verify_overclocked_rules.py','overclocked-rules.json'),
            (284,'verify_compressed_overclocked.py','overclocked-compressed/verification.json'),
            (280,'verify_triple_maze.py','triple-third-planet-collision/verification.json')):
        if level not in ids:continue
        path=V/report;prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_campaign.py','--pack',BASE.name,'--levels',ids.index(level)+1,'--prepare-only')
            run(tool,'--pack',BASE.name)
        bound(path,frozen);features.append(report)
    if 284 in ids:
        local=ids.index(284)+1
        path=V/f'mesen-checkpoints-{local}/manifest.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_campaign.py','--pack',BASE.name,'--levels',local,'--checkpoints','--sampled-graphics')
        bound(path,frozen)
        run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',path.parent)
        features.append(str(path.relative_to(V)))
    for n in (50,63,285,287,288,289,290,291,292,293,294,295,296):
        if n not in ids:continue
        local=ids.index(n)+1
        path=V/f'mesen-{local}/manifest.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_campaign.py','--pack',BASE.name,'--levels',local,'--sampled-graphics')
        bound(path,frozen)
        run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',path.parent)
        features.append(str(path.relative_to(V)))
        if not read(BASE/f'level{n}.json')['checkpoints']:continue
        path=V/f'mesen-checkpoints-{local}/manifest.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_campaign.py','--pack',BASE.name,'--levels',local,'--checkpoints','--sampled-graphics')
        bound(path,frozen)
        run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',path.parent)
        features.append(str(path.relative_to(V)))
    for n in (291,292,293,294,295,296):
        if n not in ids:continue
        path=V/f'compressed-{n}/verification.json';prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and all(prior.get(k)==v for k,v in frozen.items())):
            run('verify_compressed_overclocked.py','--pack',BASE.name,'--level-id',n)
        bound(path,frozen)
        run('verify_mesen_ppu.py','--pack',BASE.name,'--level',ids.index(n)+1,'--folder',path.parent)
        features.append(str(path.relative_to(V)))
    if 62 in ids:
        local=ids.index(62)+1;path=V/f'mesen-checkpoints-{local}/manifest.json'
        prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_campaign.py','--pack',BASE.name,'--levels',local,'--checkpoints','--sampled-graphics')
        bound(path,frozen)
        run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',path.parent)
        features.append(str(path.relative_to(V)))
    assert identity(BASE/'adofai.sfc',fresh=True)==frozen
    (V/'release-gates.json').write_text(json.dumps(dict(previous,catalog=len(ids),features=features),indent=2))
    print('RELEASE GATES PASS',flush=True)
if __name__=='__main__':main()
