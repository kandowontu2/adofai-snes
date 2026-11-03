"""The installed base game's 32 worlds plus seven official joke variants."""
from import_campaign import TITLES

WORLDS=[dict(id=i+1,code=f'{i+1}-X',title=t) for i,t in enumerate(TITLES)]
EXTRAS=[
 ('B-X','THANKS FOR PLAYING MY GAME',12,None,'B-X'),
 ('XF-X','THIRD WAVE FLIP-FLOP',19,None,'XF-X'),
 ('XC-X','CREDITS',21,None,'XC-X'),
 ('XH-X','FINAL HOPE',22,None,'XH-X'),
 ('PA-X','DISTANCE',23,None,'PA-X'),
 ('XR-X','ROSE GARDEN',25,None,'XR-X'),
 ('RJ-X','FEAR GROWS',28,None,'RJ-X'),
 ('XN-X','TRANS-NEPTUNIAN OBJECT',29,None,'XN-X'),
 ('XM-X','MIKO SKIP',None,3097,'Miko skip - Kiraramagic'),
 ('XS-X','PARTY OF SPIRITS',None,2978,'Party_of_Spirits_ADOFAI_edit'),
 ('AR-X','LIBERTAS',None,2975,'libertas - master'),
 ('XO-X','ONE FORGOTTEN NIGHT',20,None,'XO-X'),
 ('XT-X','OPTIONS',24,None,'XT-X'),
 ('XI-X','IT GO',None,3064,'itgo_fix_q10'),
 ('MN-X','NIGHT WANDER REMIX',26,None,'MN-X'),
 ('ML-X','LA NUIT DE VIF',27,None,'ML-X'),
 ('MO-X','EMOMOMO',None,2982,'MO-X'),
 ('CE-X','DRAMATIC ENTRANCE',None,2985,'dramaticentrance_cut'),
 ('CE-TX','DRAMATIC ENTRANCE TECH',None,3085,'dramaticentrance'),
 ('CI-X','REINCARNATION IDOL GRADUATION',None,3099,'REINCARNATION!! Idol Graduation'),
 ('1J-X','A CURSED DANCE',None,3061,'1-x_but_cursed'),
 ('2J-X','MORE OFFBEATS',None,3002,'OffbeatsButTheresMoreOffbeats'),
 ('3J-X','THE WIND-UP VHS',None,3112,'3-x_vhs_final'),
 ('4J-X','CLASSIC LOVE LETTERS',None,3021,'LoveLettersButIHaveFlashbacksAboutClassicPursuit'),
 ('5J-X','THE WRONG MIDNIGHT TRAIN',None,2994,'MidnightTrainButSomethingIsWrongWithTheTrain'),
 ('6J-X','PULSE GETS FASTER',None,3125,'PulseButEveryTimeYouGoUpOrDownItGetsFaster'),
 ('BJ-X','CURSED BONUS',None,3070,'b-x_cursed_final'),
]
for i,(code,title,scene,text,audio) in enumerate(EXTRAS,13):
    WORLDS.append(dict(id=i,code=code,title=title,scene=scene,text=text,audio=audio))

PACKS={
 'main':dict(title='MAIN WORLDS 1-12',levels=list(range(1,13))),
 'bonus':dict(title='BONUS AND EXTRA WORLDS',levels=[13,14,15,16,18,19]),
 'extra':dict(title='EXTRA WORLDS',levels=[17,20,21,22,23]),
 'crown':dict(title='CROWN ISLAND',levels=[24,25,26]),
 'collab':dict(title='COLLABORATION WORLDS',levels=[27,28,29,30,31,32]),
 'jokes':dict(title='OFFICIAL JOKE WORLDS',levels=list(range(33,40))),
}

def load_game_json(text):
    """Json.NET accepts trailing commas in the official XM-X chart."""
    import json
    quoted=False;escaped=False;out=[]
    for i,c in enumerate(text):
        if quoted:
            out.append(c)
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True;out.append(c)
        elif c==',':
            j=i+1
            while j<len(text) and text[j].isspace():j+=1
            if j==len(text) or text[j] not in ']}':out.append(c)
        else:out.append(c)
    # Legacy Json.NET charts also contain literal newlines in descriptions.
    return json.loads(''.join(out),strict=False)
