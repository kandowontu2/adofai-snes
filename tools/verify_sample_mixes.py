"""Check every note's sample-clock placement and every reused source hit."""
import json
from pathlib import Path
from hit_sound_assets import selections
from embedded_hit_audio import fingerprint, settings
from verification_data import identity

ROOT = Path(__file__).resolve().parents[1]


def check(base):
    catalog = json.loads((base/'pack.json').read_text())
    sources = json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())
    offsets = json.loads((ROOT/'assets/audio/hit-sound-offsets.json').read_text())
    # Independent source extraction from RDConstants, not generated mix data.
    from import_hitsounds import SOUNDS
    original = json.loads((ROOT/'build/original-hit-offsets.json').read_text())
    assert offsets == {SOUNDS[r['sound']]:r['offset'] for r in original}
    audit = {r['level']:r for r in json.loads((ROOT/'build/all-song-hit-audit.json').read_text())['levels']}
    rows = []
    for level in catalog['levels']:
        chart = json.loads((base/f'level{level}.json').read_text())
        chosen = selections(chart,sources[str(level)])
        expected = {n['step']:(n,s,v) for n,(s,v) in zip(chart['notes'][1:],chosen[1:]) if not n['flags']&8 and s!='None' and v}
        config = settings(level)
        reused = set(config.get('embedded_hit_notes',[]))
        for note in reused:
            match = next(m for m in audit[level]['matches'] if m['note']==note)
            assert abs(match['lag_ms']-config['alignment_samples']/config['alignment_rate']*1000) < .2
        suffixes = ['', '-fast'] if catalog.get('fast_audio_rate') else ['', '-pcm'] if not catalog.get('standalone') else ['']
        variants = []
        for suffix in suffixes:
            report = json.loads((base/f'level{level}{suffix}-hit-mix.json').read_text())
            assert report['fingerprint']==fingerprint(chart)
            assert set(report['reused'])==reused
            inserted = {r['note']:r for r in report['inserted']}
            assert len(inserted)==len(report['inserted'])
            assert set(inserted).isdisjoint(reused)
            assert set(inserted)|reused == set(expected), (level,'missing or duplicate hit')
            rate = report['rate']
            for i,r in inserted.items():
                note,sound,volume = expected[i]
                lead = offsets.get(sound,0)
                if sound==config.get('sample'):
                    lead = -config['alignment_samples']/config['alignment_rate']
                exact = (note['time']-lead)*rate
                assert r['sound']==sound and abs(r['start_sample']-exact)<=.500001
            assert 0 < report['gain'] <= 1 and report['peak'] <= 32700.01
            variants.append(dict(format=suffix or 'brr',rate=rate,inserted=len(inserted),reused=len(reused),gain=report['gain']))
        rows.append(dict(level=level,notes=len(expected),variants=variants))
    result = dict(passed=True,cases=rows,**identity(base/'adofai.sfc'))
    (base/'verification').mkdir(exist_ok=True)
    (base/'verification/sample-mixes.json').write_text(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('base',type=Path)
    args=parser.parse_args();result=check(args.base)
    print('PASS',len(result['cases']),'songs; every hit inserted or reused once at sample precision')
