"""Extract original hit/countdown samples from the user's installed game."""
import argparse
from pathlib import Path
import UnityPy
from import_campaign import DEFAULT_GAME

NAMES=('Hat','Kick','Shaker','Sizzle','Chuck','ShakerLoud','Hammer','KickChroma',
       'SnareAcoustic2','Sidestick','Stick','ReverbClack','Squareshot','PowerDown',
       'PowerUp','KickHouse','KickRupture','HatHouse','SnareHouse','SnareVapor',
       'ClapHit','ClapHitEcho','ReverbClap','FireTile','IceTile','VehiclePositive',
       'VehicleNegative','CymbalCrash')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,default=Path(DEFAULT_GAME));args=ap.parse_args()
    out=Path(__file__).resolve().parents[1]/'assets/private/hitsounds';out.mkdir(parents=True,exist_ok=True)
    env=UnityPy.load(str(args.game/'A Dance of Fire and Ice_Data/resources.assets'))
    found=set()
    for obj in env.objects:
        if obj.type.name!='AudioClip':continue
        clip=obj.read()
        if clip.m_Name not in {'snd'+n for n in NAMES}:continue
        (out/(clip.m_Name+'.wav')).write_bytes(next(iter(clip.samples.values())))
        found.add(clip.m_Name[3:])
    assert found==set(NAMES),('Missing original samples',set(NAMES)-found)
    print('Imported',len(found),'original hit/countdown sounds')

if __name__=='__main__':main()
