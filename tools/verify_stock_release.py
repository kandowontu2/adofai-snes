"""Recover exact-build release evidence and run final sequential regressions."""
import argparse,json,subprocess,sys
from pathlib import Path
from verification_data import identity
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
def regressions(frozen,ids):
    run('verify_menu_mode_mesen.py','--pack',BASE.name)
    run('verify_msu_header_mesen.py','--pack',BASE.name)
    sequence=[65,70,67,94,144,1]
    pairs=list(zip(sequence,sequence[1:]))
    # Keep both charts in the same emulator session for each transition,
    # without registering six simultaneous copies of the hardware probes.
    for first,second in pairs:
        path=V/f'sequence-{first}-{second}/manifest.json'
        prior=read(path) if path.exists() else {}
        if not (prior.get('passed') and prior.get('suite_digest')==suite_digest()
                and all(prior.get(k)==v for k,v in frozen.items())):
            run('run_mesen_sequence.py','--pack',BASE.name,'--levels',first,second)
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
    args=parser.parse_args();BASE=ROOT/'build/packs'/args.pack;V=BASE/'verification'
    frozen=identity(BASE/'adofai.sfc');ids=read(BASE/'pack.json')['levels'];rows=[]
    assert len(ids)==len(set(ids)) and ids
    if args.regressions_only:
        regressions(frozen,ids)
        print('RELEASE REGRESSIONS PASS; CATALOG STILL REQUIRED',flush=True)
        return
    for local,n in enumerate(ids,1):
        folder=V/f'mesen-{local}-autoplay'
        m=bound(folder/'manifest.json',frozen)
        assert (folder/'result.txt').read_text().endswith('PASS\n')
        assert m['suite_digest']==suite_digest(),f'Replay oracle stale: {n}'
        pp=folder/'ppu-verification.json'
        if not pp.exists():run('verify_mesen_ppu.py','--pack',BASE.name,'--level',local,'--folder',folder)
        bound(pp,frozen)
        rows.append(dict(id=n,local=local,passed=True,validation_suite_digest=m['suite_digest']))
    report=dict(**frozen,passed=True,complete=True,suite_digest=suite_digest(),results=rows)
    (V/'catalog/results.json').write_text(json.dumps(report,indent=2))
    print(f'CATALOG {len(ids)} PASS',flush=True)
    path=V/'release-regressions.json'
    previous=read(path) if path.exists() else {}
    if not (previous.get('passed') and previous.get('suite_digest')==suite_digest()
            and all(previous.get(k)==v for k,v in frozen.items())):
        previous=regressions(frozen,ids)
    features=[]
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
        bound(path,frozen);features.append(str(path.relative_to(V)))
    assert identity(BASE/'adofai.sfc')==frozen
    (V/'release-gates.json').write_text(json.dumps(dict(previous,catalog=len(ids),features=features),indent=2))
    print('RELEASE GATES PASS',flush=True)
if __name__=='__main__':main()
