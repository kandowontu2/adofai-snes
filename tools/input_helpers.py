"""Drive the actual options menu in emulator checks."""
def select_level(em,level_id):
    """Choose a global song ID through set submenus (or a legacy flat list)."""
    import json
    from menu_sets import groups
    levels=json.loads((em.rom_path.parent/'pack.json').read_text())['levels']
    index=levels.index(level_id)
    if 'menu_depth' not in em.labels:
        while em.read('selected_level')!=index:press(em,5)
        return
    sets=groups(levels)
    group=next(i for i,(_,indices) in enumerate(sets) if index in indices)
    if em.read('menu_depth') and em.read('menu_group')!=group:press(em,0)
    if not em.read('menu_depth'):
        while em.read('menu_selection')!=group:press(em,5)
        press(em,3)
    selection=sets[group][1].index(index)
    while em.read('menu_selection')!=selection:press(em,5)
    assert em.read('selected_level')==index

def press(em,button):
    em.run([button])
    for _ in range(3):em.run()

def wait(em,predicate,limit=300):
    for _ in range(limit):
        if predicate():return
        em.run()
    raise AssertionError(em.snapshot())

def configure(em,speed=10,time_attack=False,fire=None,ice=None,calibration=None):
    if 'menu_depth' in em.labels and em.read('state')==0 and em.read('menu_depth'):
        import json
        from menu_sets import groups
        if len(groups(json.loads((em.rom_path.parent/'pack.json').read_text())['levels']))>1:press(em,0)
    press(em,0);wait(em,lambda:em.read('state')==7)
    for _ in range(6):
        if em.read('settings_row')==0:break
        press(em,4)
    assert em.read('settings_row')==0,'Options did not return to the first row'
    if bool(em.read('time_attack'))!=bool(time_attack):press(em,7)
    press(em,5)
    while em.read('speed_tenths')!=speed:press(em,7 if em.read('speed_tenths')<speed else 6)
    press(em,5);press(em,5)
    if fire is not None:
        while em.read('fire_color')!=fire:press(em,7)
    press(em,5)
    if ice is not None:
        while em.read('ice_color')!=ice:press(em,7)
    if calibration is not None:
        press(em,5)
        for _ in range(61):
            current=em.read('calibration',True)
            if current==calibration:break
            press(em,7 if current<calibration else 6)
        assert em.read('calibration',True)==calibration,'Calibration adjustment did not reach the requested value'
    press(em,3);wait(em,lambda:em.read('state')==0)

def verify_checkpoint_results(em):
    """Check normal results text in WRAM and in the committed PPU map."""
    import ctypes as C
    for _ in range(8):em.run()
    row=C.string_at(em.ram+0x800+23*64,64)
    text=''.join(chr(row[i]) if row[i] else ' ' for i in range(0,64,2))
    assert text[3:19]=='CHECKPOINTS USED',repr(text)
    assert text[24:27]==f'{em.read("checkpoints_used"):03d}',repr(text)
    vram=em.core.retro_get_memory_data(3)
    assert C.string_at(vram+0xf000+23*64,64)==row,'Checkpoint result not published to PPU'
    return text.strip()
