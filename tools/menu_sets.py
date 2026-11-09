"""Song-set navigation shared by clean builds, cached builds and UI tests."""
from official_catalog import PACKS
import re


def groups(levels):
    sets=[('MAIN WORLDS',PACKS['main']['levels']),
          ('BONUS WORLDS',PACKS['bonus']['levels']),
          ('EXTRA WORLDS',PACKS['extra']['levels']),
          ('CROWN ISLAND',PACKS['crown']['levels']),
          ('COLLABORATIONS',PACKS['collab']['levels']),
          ('JOKE WORLDS',PACKS['jokes']['levels']),
          ('FEATURED TECH',range(40,62)),
          ('COMMUNITY',range(62,1000))]
    result=[(name,[i for i,n in enumerate(levels) if n in members]) for name,members in sets]
    result=[row for row in result if row[1]]
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
               'menu_play_hint: .byte "         START TO PLAY          ",0',
               'menu_single_hint: .byte "         START TO PLAY          ",0',
               'menu_controls: .byte "   SELECT CALIBRATE  B OPTIONS   ",0',
               'menu_back_controls: .byte "    SELECT CALIBRATE  B BACK     ",0',
               'menu_navigation: .byte "       UP / DOWN SELECT         ",0']
    return '\n'.join(result)+'\n'


def write_count(out,levels):
    path=out/'addresses.inc'
    text=path.read_text()
    text=re.sub(r'^MENU_SET_COUNT = .*\n?', '', text, flags=re.M)
    path.write_text(text+f'\nMENU_SET_COUNT = {len(groups(levels))}\n')
