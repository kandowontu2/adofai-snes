"""Song-set navigation shared by clean builds, cached builds and UI tests."""
from official_catalog import PACKS, WORLDS
from neo_catalog import NEO
import json
from pathlib import Path
import re

FEATURED=json.loads(Path(__file__).with_name('featured_catalog.json').read_text())
FIRESTIX=json.loads(Path(__file__).with_name('firestix_catalog.json').read_text())
TECH=json.loads(Path(__file__).with_name('tech_catalog.json').read_text())
COMMUNITY=json.loads(Path(__file__).with_name('community_catalog.json').read_text())
YANGSY=json.loads(Path(__file__).with_name('yangsy_catalog.json').read_text())
MAIN_EX=json.loads(Path(__file__).with_name('main_ex_catalog.json').read_text())
MAIN_EX_IDS={m['id'] for m in MAIN_EX}
YANGSY_IDS={m['id'] for m in YANGSY}
CLASSIC_IDS={63,64,*[m['id'] for m in FEATURED if m.get('set')!='featured_tech']}
TECH_IDS={m['id'] for m in TECH}|{m['id'] for m in FEATURED if m.get('set')=='featured_tech'}
FIRESTIX_IDS={m['id'] for m in FIRESTIX}
JOKE_IDS={m['id'] for m in json.loads(Path(__file__).with_name('joke_catalog.json').read_text())}
FEATURED_ORDER={m['id']:(m.get('wave',99),m.get('featured_order',m['id']))
                for m in TECH+COMMUNITY+FEATURED}
WORLD_ORDER={m['code']:m['id'] for m in WORLDS}
JOKE_ORDER=dict(zip(PACKS['jokes']['levels'],(1,2,3,4,5,6,13)))
JOKE_ORDER[39]=13  # Historical frozen packs can still be verified.
for m in FIRESTIX+json.loads(Path(__file__).with_name('joke_catalog.json').read_text()):
    JOKE_ORDER[m['id']]=WORLD_ORDER.get(m.get('artist'),10000+m['id'])


def groups(levels):
    sets=[('MAIN WORLDS',PACKS['main']['levels']),
          ('MAIN EX LEVELS',sorted(MAIN_EX_IDS)),
          ('BONUS WORLDS',PACKS['bonus']['levels']),
          ('EXTRA WORLDS',PACKS['extra']['levels']),
          ('CROWN ISLAND',PACKS['crown']['levels']),
          ('COLLABORATIONS',PACKS['collab']['levels']),
          ('JOKE WORLDS',list(PACKS['jokes']['levels'])+[39]+sorted(FIRESTIX_IDS|JOKE_IDS)),
          ('FEATURED TECH',TECH_IDS),
          ('FEATURED CLASSIC',CLASSIC_IDS),
          ('YANGSY CURSED LEVELS',YANGSY_IDS),
          ('COMMUNITY',[n for n in range(62,1000) if n not in {m['id'] for m in NEO}|CLASSIC_IDS|TECH_IDS|FIRESTIX_IDS|JOKE_IDS|YANGSY_IDS|MAIN_EX_IDS]),
          ('NEO COSMOS',[m['id'] for m in NEO])]
    result=[(name,[i for i,n in enumerate(levels) if n in members]) for name,members in sets]
    result=[row for row in result if row[1]]
    for name,indices in result:
        if name=='JOKE WORLDS':indices.sort(key=lambda i:(JOKE_ORDER[levels[i]],levels[i]))
        elif name=='MAIN EX LEVELS':indices.sort(key=lambda i:levels[i])
        elif name.startswith('FEATURED '):indices.sort(key=lambda i:FEATURED_ORDER[levels[i]])
    assert sorted(i for _,indices in result for i in indices)==list(range(len(levels)))
    return result


def tables(levels):
    sets=groups(levels);flat=[];starts=[]
    for _,indices in sets:starts.append(len(flat)*2);flat.extend(indices)
    result=['; MENU_SET_TABLES',
            'menu_set_starts: .word '+','.join(map(str,starts)),
            'menu_set_counts: .word '+','.join(str(len(indices)) for _,indices in sets),
            'menu_level_indices: .word '+','.join(map(str,flat)),
            'menu_set_name_ptrs: .word '+','.join(f'menu_set_name{i}' for i in range(len(sets)))]
    result += [f'menu_set_name{i}: .byte "{name:<28}",0' for i,(name,_) in enumerate(sets)]
    result += ['menu_root_name: .byte "CHOOSE A SET                ",0',
               'menu_open_hint: .byte "       START OPEN SET           ",0',
               'menu_single_hint:',
               'menu_play_hint: .byte "         START TO PLAY          ",0',
               'menu_controls: .byte "   SELECT CALIBRATE  B OPTIONS   ",0',
               'menu_back_controls: .byte "    SELECT CALIBRATE  B BACK     ",0',
               'menu_navigation: .byte "       UP / DOWN SELECT         ",0']
    return '\n'.join(result)+'\n'


def groups_for_pack(folder):
    """Read the menu shipped in this ROM, not the currently edited catalog."""
    folder=Path(folder)
    text=(folder/'tables.inc').read_text()
    def words(name):
        match=re.search(r'^'+name+r': \.word ([0-9,]+)$',text,re.M)
        if not match:raise ValueError(f'Missing frozen menu table: {name}')
        return list(map(int,match[1].split(',')))
    starts=words('menu_set_starts');counts=words('menu_set_counts');indices=words('menu_level_indices')
    names=re.findall(r'^menu_set_name\d+: \.byte "([^"]+)",0$',text,re.M)
    assert len(starts)==len(counts)==len(names)
    result=[(name.strip(),indices[start//2:start//2+count]) for name,start,count in zip(names,starts,counts)]
    levels=json.loads((folder/'pack.json').read_text())['levels']
    assert sorted(i for _,members in result for i in members)==list(range(len(levels)))
    return result


def write_count(out,levels):
    path=out/'addresses.inc'
    text=path.read_text()
    text=re.sub(r'^MENU_SET_COUNT = .*\n?', '', text, flags=re.M)
    path.write_text(text+f'\nMENU_SET_COUNT = {len(groups(levels))}\n')
