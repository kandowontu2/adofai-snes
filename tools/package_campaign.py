"""Package all native official-world cartridges and their verification."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from official_catalog import PACKS
from presentation_assets import COLOR_NAMES,JUDGMENTS,WEIGHTS
ROOT=Path(__file__).resolve().parents[1]
FILES={'main':'adofai-main-worlds.sfc','bonus':'adofai-bonus-worlds.sfc',
       'extra':'adofai-extra-worlds.sfc','crown':'adofai-crown-island.sfc',
       'collab':'adofai-collaboration-worlds.sfc','jokes':'adofai-joke-worlds.sfc'}

def collect_verification():
    worlds=[]
    for pack,meta in PACKS.items():
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        for local,n in enumerate(meta['levels'],1):
            chart=json.loads((base/f'level{n}.json').read_text());v=base/'verification'
            controller=json.loads((v/f'perfect-{local}/result.json').read_text())
            watch=json.loads((v/f'watch-{local}/result.json').read_text())
            audio=json.loads((v/f'perfect-{local}/audio-check.json').read_text())
            render=json.loads((v/f'render-{local}.json').read_text())
            mesen=json.loads((v/f'mesen-{local}/manifest.json').read_text())
            for result in (controller,watch,audio,render):assert result['rom_sha256']==digest,('Stale check',chart['code'])
            assert mesen['sha256']==digest,('Stale Mesen check',chart['code'])
            assert (v/f'mesen-{local}/result.txt').read_text().endswith('PASS\n')
            for result in (controller,watch):
                end=result['final'];assert end['state']==3 and end['step']==chart['steps'] and end['combo']==chart['hits'] and end['misses']==0
                assert sum(result['judgments'])==chart['hits']
                assert result['score']==sum(c*w for c,w in zip(result['judgments'],WEIGHTS))
            assert audio['comparison_window_seconds']==2
            assert min(x['correlation'] for x in audio['windows'])>.9 and abs(audio['drift_ms'])<20
            assert render['max_objects_per_line']<=17 and render['ppu_chr_match'] and render['trails'] and render['tile_flashes']
            checkpoint_count=len(chart['checkpoints'])
            if checkpoint_count:
                checkpoint=json.loads((v/f'checkpoints-{local}/result.json').read_text())
                assert checkpoint['rom_sha256']==digest and checkpoint['death_scene_frozen']
                assert len(checkpoint['checkpoints'])==checkpoint_count and checkpoint['final']['state']==3
                skipped=sum(sum(not(n['flags']&8) for n in chart['notes'][c['trigger']+1:c['floor']+1]) for c in chart['checkpoints'] if c['floor']>c['trigger'])
                assert sum(checkpoint['judgments'])==chart['hits']-skipped
                independent=json.loads((v/f'mesen-checkpoints-{local}/manifest.json').read_text())
                assert independent['sha256']==digest
                assert (v/f'mesen-checkpoints-{local}/result.txt').read_text().endswith('PASS\n')
                for cp in checkpoint['checkpoints']:
                    assert min(w['correlation'] for w in cp['audio_windows'])>.9
                    assert max(abs(w['offset_ms']) for w in cp['audio_windows'])<30
            worlds.append(dict(code=chart['code'],pack=pack,hits=chart['hits'],rom_sha256=digest,
                               checkpoint_retries=checkpoint_count,
                               controller_combo=controller['final']['combo'],controller_misses=0,
                               controller_score=controller['score'],controller_judgments=dict(zip(JUDGMENTS,controller['judgments'])),
                               autoplay_combo=watch['final']['combo'],audio_drift_ms=audio['drift_ms'],
                               minimum_audio_correlation=min(x['correlation'] for x in audio['windows']),
                               render_samples=render['cache_samples'],max_objects_per_line=render['max_objects_per_line'],
                               mesen=mesen['summary']))
    assert len(worlds)==39
    speeds=json.loads((ROOT/'build/speed-verification/result.json').read_text())
    main_digest=worlds[0]['rom_sha256']
    assert json.loads((ROOT/'build/campaign/verification/preview.json').read_text())['rom_sha256']==main_digest
    assert json.loads((ROOT/'build/campaign/verification/preview.json').read_text())['visibility_rom_sha256']==next(w['rom_sha256'] for w in worlds if w['pack']=='crown')
    assert speeds['rom_sha256']==main_digest and [r['speed'] for r in speeds['speeds']]==[n/10 for n in range(5,21)]
    for row in speeds['speeds']:
        assert row['rom_sha256']==main_digest and row['combo']==167 and row['misses']==0
        assert row['minimum_correlation']>.9 and abs(row['drift_ms'])<20
    independent_speeds=[]
    for pack,level,speed in [('main',1,5),('main',1,11),('main',1,20),('main',9,20),('jokes',3,5)]:
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        folder=base/f'verification/mesen-{level}-speed-{speed:02d}-attack'
        manifest=json.loads((folder/'manifest.json').read_text());report=(folder/'result.txt').read_text()
        assert manifest['sha256']==hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        assert report.endswith('PASS\n') and f'speed={speed} attack=1 judgment_count=' in report
        independent_speeds.append(manifest)
    stress=[]
    for name,pack in [('long-clock-verification','jokes'),('fast-track-verification','main')]:
        folder=ROOT/'build'/name
        result=json.loads((folder/'result.json').read_text());audio=json.loads((folder/'audio-check.json').read_text())
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        assert result['rom_sha256']==audio['rom_sha256']==digest
        assert result['final']['state']==3 and result['final']['misses']==0
        assert min(x['correlation'] for x in audio['windows'])>.9 and abs(audio['drift_ms'])<20
        ticks=[r['nmi_audio_ticks'] for r in result['transitions'] if r['music_active']]
        wrapped=any(b-a<-32768 for a,b in zip(ticks,ticks[1:]))
        if name=='long-clock-verification':assert wrapped
        stress.append(dict(code=result['code'],speed=result['speed_tenths']/10,rom_sha256=digest,
                           combo=result['final']['combo'],misses=0,finish_seconds=result['finish_centis']/100,
                           clock_rollover=wrapped,audio_drift_ms=audio['drift_ms']))
    return dict(verified=True,worlds=worlds,audio_rate_hz=12000,hardware_tested=False,
                checkpoint_retries=sum(w['checkpoint_retries'] for w in worlds),
                timing_modes=['Strict','Normal','Looser'],death_scene='frozen playfield',
                regression_tests=36,track_outline_pixels=1,orb_trail='continuous fading streak',
                tile_visibility=dict(triggers=['AnimateTrack','MoveTrack opacity','native floor effects'],fade_levels=3,clock='SPC700 timer',checkpoint_seek=True),
                menu_cursor_and_text='all six cartridges checked in WRAM, PPU, and captured pixels',
                orb_colors=COLOR_NAMES,independent_orb_colors=True,time_attack=True,
                judgments=[dict(name=n,points=w) for n,w in zip(JUDGMENTS,WEIGHTS)],
                speed_settings=speeds['speeds'],independent_speed_checks=independent_speeds,speed_stress_checks=stress,
                overload_recovery='0.4 bars per base beat; 0.5 bars per rough/extra tap')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--require-verified',action='store_true');args=ap.parse_args()
    try:verification=collect_verification()
    except (AssertionError,KeyError,FileNotFoundError):
        if args.require_verified:raise
        verification=dict(verified=False)
    out=ROOT/'dist';out.mkdir(exist_ok=True);roms=[]
    for pack,name in FILES.items():
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        source=base/'adofai.sfc';data=source.read_bytes()
        assert len(data)==0x800000 and sum(data)&65535==int.from_bytes(data[0x40FFDE:0x40FFE0],'little')
        shutil.copyfile(source,out/name)
        roms.append(dict(pack=pack,file=name,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),worlds=PACKS[pack]['levels']))
    shutil.copyfile(ROOT/'README.md',out/'README.txt')
    (out/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in roms))
    verification['roms']=roms
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    for source,name in [('official-preview.png','preview.png'),('effects.gif','preview.gif'),('menu.png','menu.png'),('visibility.png','visibility.png'),('visibility.gif','visibility.gif'),
                        ('options.png','options.png'),('results.png','results.png'),
                        ('calibration-tap.png','calibration.png'),('checkpoints-3/death.png','checkpoint-death.png'),
                        ('checkpoints-3/retry.png','checkpoint-retry.png')]:
        p=ROOT/'build/campaign/verification'/source
        if p.exists():shutil.copyfile(p,out/name)
    extras=['README.txt','SHA256SUMS.txt','verification.json','preview.png','preview.gif','menu.png','visibility.png','visibility.gif','options.png','results.png','calibration.png','checkpoint-death.png','checkpoint-retry.png']
    with zipfile.ZipFile(out/'adofai-official-worlds.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in list(FILES.values())+extras:
            if (out/name).exists():z.write(out/name,name)
    with zipfile.ZipFile(out/'adofai-official-worlds.zip') as z:assert z.testzip() is None
    with zipfile.ZipFile(out/'adofai-main-worlds.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in [FILES['main'],'README.txt','preview.png','preview.gif','menu.png','options.png','results.png','checkpoint-death.png','checkpoint-retry.png']:
            if (out/name).exists():z.write(out/name,name)
        z.writestr('SHA256SUMS.txt',roms[0]['sha256']+'  '+FILES['main']+'\n')
    # Keep the historical default ROM path pointed at the current main build.
    for name in ('adofai.sfc','adofai.lbl','adofai.map'):
        shutil.copyfile(ROOT/'build/campaign'/name,ROOT/'build'/name)
    print('Packaged',len(roms),'ROMs; verified worlds:',len(verification.get('worlds',[])))
    print(out/'adofai-official-worlds.zip')

if __name__=='__main__':main()
