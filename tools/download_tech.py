"""Download the installed Featured Tech and selected Workshop catalogs.

Uses the owner's running Steam client; does not subscribe or publish anything.
"""
import argparse,ctypes as C,json,os,time
from pathlib import Path
from import_campaign import DEFAULT_GAME

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids',type=int,nargs='+',help='Download only these Workshop items')
    args=parser.parse_args()
    game=Path(DEFAULT_GAME)
    entries=[x for x in json.loads((game/'FeaturedLevels/metadata.json').read_text(encoding='utf-8-sig'))['levels'] if x['type']==1]
    for name in ('featured_catalog.json','firestix_catalog.json'):
        entries.extend(dict(id=m['workshop'],song=m['title']) for m in
                       json.loads(Path(__file__).with_name(name).read_text()))
    os.environ['SteamAppId']='977950';os.environ['SteamGameId']='977950'
    api=C.CDLL(str(game/'A Dance of Fire and Ice_Data/Plugins/x86_64/steam_api64.dll'))
    api.SteamAPI_InitSafe.restype=C.c_bool
    assert api.SteamAPI_InitSafe(),'Start Steam with the account that owns ADOFAI'
    api.SteamAPI_SteamUGC_v020.restype=C.c_void_p
    ugc=api.SteamAPI_SteamUGC_v020()
    download=api.SteamAPI_ISteamUGC_DownloadItem;download.argtypes=[C.c_void_p,C.c_uint64,C.c_bool];download.restype=C.c_bool
    install=api.SteamAPI_ISteamUGC_GetItemInstallInfo;install.argtypes=[C.c_void_p,C.c_uint64,C.POINTER(C.c_uint64),C.c_char_p,C.c_uint32,C.POINTER(C.c_uint32)];install.restype=C.c_bool
    pending=({ident:str(ident) for ident in args.ids} if args.ids else
             {int(x['id']):x['song'] for x in entries})
    try:
        for ident in pending:assert download(ugc,ident,False),ident
        deadline=time.monotonic()+240
        while pending and time.monotonic()<deadline:
            api.SteamAPI_RunCallbacks()
            for ident,title in list(pending.items()):
                folder=C.create_string_buffer(4096);size=C.c_uint64();stamp=C.c_uint32()
                if install(ugc,ident,C.byref(size),folder,len(folder),C.byref(stamp)):
                    print(ident,ascii(title),folder.value.decode(),flush=True);del pending[ident]
            time.sleep(.25)
        assert not pending,('Still downloading',pending)
    finally:api.SteamAPI_Shutdown()

if __name__=='__main__':main()
