"""Deterministic libretro SNES runner for real ROM/controller/audio checks."""
import argparse
import ctypes as C
import json
import os
import re
import struct
import wave
from pathlib import Path
import numpy as np
from PIL import Image
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]
class GameInfo(C.Structure):
    _fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Geometry(C.Structure):
    _fields_=[('base_width',C.c_uint),('base_height',C.c_uint),('max_width',C.c_uint),('max_height',C.c_uint),('aspect_ratio',C.c_float)]
class Timing(C.Structure):
    _fields_=[('fps',C.c_double),('sample_rate',C.c_double)]
class AVInfo(C.Structure):
    _fields_=[('geometry',Geometry),('timing',Timing)]
class RetroVariable(C.Structure):
    _fields_=[('key',C.c_char_p),('value',C.c_char_p)]

class Emulator:
    def __init__(self,core=None,rom=None,mute_taps=False):
        if os.name=='nt': self.dll_dir=os.add_dll_directory(r'C:\Strawberry\c\bin')
        self.core=C.CDLL(str(core or ROOT/'.tools/snes9x/snes9x_libretro.dll'))
        self.buttons=set(); self.video=None; self.audio=[]; self.pixel_format=0
        path=Path(rom or ROOT/'build/adofai.sfc').resolve()
        self.rom_path=path;self.loaded_identity=identity(path)
        self.labels={m[1]:int(m[0],16)&0x1FFFF for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(path.parent/'adofai.lbl').read_text())}
        self.directory=str(path.parent).encode()
        self.mute_taps=mute_taps
        self.options_dirty=bool(mute_taps)
        self.option_reads=[]
        self.frontend_values={b'snes9x_sndchan_3':b'disabled',b'snes9x_sndchan_4':b'disabled',
                              b'snes9x_sndchan_volume_3':b'0',b'snes9x_sndchan_volume_4':b'0'} if mute_taps else {}
        @C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
        def environment(cmd,data):
            if cmd==15:
                variable=C.cast(data,C.POINTER(RetroVariable)).contents
                if variable.key and b'sndchan' in variable.key:self.option_reads.append(variable.key.decode())
                if variable.key in self.frontend_values:
                    variable.value=self.frontend_values[variable.key];return True
                return False
            if cmd==17:
                C.cast(data,C.POINTER(C.c_bool))[0]=self.options_dirty
                self.options_dirty=False;return True
            if cmd in (9,31,30):
                C.cast(data,C.POINTER(C.c_char_p))[0]=self.directory; return True
            if cmd==10:
                self.pixel_format=C.cast(data,C.POINTER(C.c_int))[0]; return True
            if cmd==3:
                C.cast(data,C.POINTER(C.c_bool))[0]=True; return True
            if cmd in (16,18,35,36,37):return True
            return False
        @C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
        def video(data,w,h,pitch):
            if data:self.video=(C.string_at(data,pitch*h),w,h,pitch)
        @C.CFUNCTYPE(None,C.c_int16,C.c_int16)
        def audio(l,r):self.audio.append(struct.pack('<hh',l,r))
        @C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t)
        def batch(data,n):self.audio.append(C.string_at(data,n*4)); return n
        @C.CFUNCTYPE(None)
        def poll():pass
        @C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
        def input_state(port,device,index,button):return int(port==0 and button in self.buttons)
        self.callbacks=[environment,video,audio,batch,poll,input_state]
        for name,cb in zip(['environment','video_refresh','audio_sample','audio_sample_batch','input_poll','input_state'],self.callbacks):
            getattr(self.core,'retro_set_'+name)(cb)
        self.core.retro_init()
        self.core.retro_load_game.argtypes=[C.POINTER(GameInfo)]; self.core.retro_load_game.restype=C.c_bool
        self.rom=C.create_string_buffer(path.read_bytes())
        info=GameInfo(str(path).encode(),C.cast(self.rom,C.c_void_p),len(self.rom)-1,None)
        assert self.core.retro_load_game(C.byref(info)),'Cannot load ROM'
        self.core.retro_run()
        self.core.retro_get_memory_data.restype=C.c_void_p
        self.core.retro_get_memory_size.restype=C.c_size_t
        self.ram=self.core.retro_get_memory_data(2)
        self.sa1='sa1_cache_prepare' in self.labels
        self.cache_ram=self.core.retro_get_memory_data(0) if self.sa1 else self.ram
        addresses=(path.parent/'addresses.inc').read_text() if (path.parent/'addresses.inc').exists() else ''
        self.hud=self.cache_ram+0x800 if re.search(r'^SA1_WRAM_RENDERER\s*=\s*1\s*$',addresses,re.M) else self.ram+0x800
        assert self.ram and self.core.retro_get_memory_size(2)>=128*1024,[(i,self.core.retro_get_memory_size(i)) for i in range(4)]
        av=AVInfo(); self.core.retro_get_system_av_info(C.byref(av)); self.av=av
        self.frames=0
    def read(self,name,signed=False):
        v=C.c_uint16.from_address(self.ram+self.labels[name]).value
        return v-65536 if signed and v>=32768 else v
    def evidence(self):
        assert identity(self.rom_path)==self.loaded_identity,'ROM or MSU data changed during emulation'
        if self.mute_taps:
            for channel in (3,4):
                assert any(key in self.option_reads for key in (f'snes9x_sndchan_{channel}',f'snes9x_sndchan_volume_{channel}')),'Core did not query the percussion channel controls'
        return dict(self.loaded_identity,muted_sound_channels=[3,4] if self.mute_taps else [])
    def snapshot(self):
        names=('tick','state','step','elapsed','combo','best','perfects','misses','practice','autoplay','calibration','timing_error','music_active',
               'selected_level','last_note','chart_time','audio_ticks','commits','skipped_commits','cal_count','cal_sum','cal_error','cal_recommend',
               'nmi_audio_ticks','speed_tenths','time_attack','run_centis','finish_cs','tap_head','tap_tail','tap_overruns','tap_queue_peak','msu_present','msu_pcm','msu_elapsed_frames','msu_track','pattern_peak_queued','pattern_vblank_overruns','camera_zoom','camera_inverse','m7_map_deferrals')
        return {k:self.read(k,k in ('timing_error','calibration','cal_sum','cal_error','cal_recommend','camera_zoom','camera_inverse')) for k in names if k in self.labels}
    def run(self,buttons=()):
        self.buttons=set(buttons); self.core.retro_run(); self.frames+=1
    def capture(self,path):
        if not self.video:return
        blob,w,h,pitch=self.video
        if self.pixel_format==1:
            im=Image.frombytes('RGB',(w,h),blob,'raw','BGRX',pitch)
        else:
            a=np.frombuffer(blob,dtype='<u2').reshape(h,pitch//2)[:,:w]
            if self.pixel_format==2:
                rgb=np.stack([((a>>11)&31)*255//31,((a>>5)&63)*255//63,(a&31)*255//31],-1)
            else:
                rgb=np.stack([((a>>10)&31)*255//31,((a>>5)&31)*255//31,(a&31)*255//31],-1)
            im=Image.fromarray(rgb.astype('uint8'))
        im.save(path)
    def save_audio(self,path):
        with wave.open(str(path),'wb') as f:
            f.setparams((2,2,round(self.av.timing.sample_rate),0,'NONE','not compressed'));f.writeframes(b''.join(self.audio))
    def close(self):
        self.core.retro_unload_game();self.core.retro_deinit()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scenario',choices=['boot','perfect','autoplay','miss','early','late','practice','pause','hold'],default='boot')
    ap.add_argument('--frames',type=int,default=600);ap.add_argument('--core',type=Path);ap.add_argument('--out',type=Path);ap.add_argument('--audio',action='store_true')
    args=ap.parse_args();out=args.out or ROOT/'build/verification'/args.scenario;out.mkdir(parents=True,exist_ok=True)
    em=Emulator(args.core);level=json.loads((ROOT/'build/level.json').read_text());notes=level['notes']
    trace=[];prior=None;started=False;pause_stage=0;pause_frame=0;held_step=None
    try:
        for frame in range(args.frames):
            s=em.snapshot();buttons=[]
            if frame==120 and args.scenario!='boot':
                buttons=[1 if args.scenario=='autoplay' else 9 if args.scenario=='practice' else 3]
                started=True
            if s['state']==1 and started:
                target=notes[min(s['step']+1,167)]['frame']+s['calibration']
                next_elapsed=s['elapsed']+1
                if args.scenario in ('perfect','pause') and target<=next_elapsed<=target+2:buttons=[8]
                if args.scenario=='early' and s['step']==0 and next_elapsed==target-7:buttons=[8]
                if args.scenario=='late' and target+2<=next_elapsed<=target+3:buttons=[8]
                if args.scenario=='hold' and next_elapsed>=notes[1]['frame']:buttons=[8]
                if args.scenario=='pause' and s['step']==12 and pause_stage==0:
                    buttons=[3];pause_stage=1;pause_frame=frame
            if args.scenario=='pause' and s['state']==4 and frame==pause_frame+120:
                buttons=[3];pause_stage=2
            em.run(buttons)
            now=em.snapshot()
            key=(now['state'],now['step'],now['misses'])
            if key!=prior:
                trace.append({'frame':frame,**now});prior=key
            if frame in (90,122,180,240,600,1200,2400,4000,args.frames-1) or (now['state'] in (2,3,4) and key!= (s['state'],s['step'],s['misses'])):
                em.capture(out/f'frame-{frame:05d}.png')
            if frame%1000==0:print('frame',frame,now,flush=True)
        result={'scenario':args.scenario,'core':str(args.core or 'snes9x'),'frames':args.frames,'fps':em.av.timing.fps,
                'sample_rate':em.av.timing.sample_rate,'final':em.snapshot(),'transitions':trace}
        (out/'result.json').write_text(json.dumps(result,indent=2));em.capture(out/'final.png')
        if args.audio:em.save_audio(out/'audio.wav')
        print(json.dumps({k:v for k,v in result.items() if k!='transitions'}),flush=True)
    finally:em.close()

if __name__=='__main__':main()
