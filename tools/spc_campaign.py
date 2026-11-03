"""SPC700 BRR streaming driver with an audio-clocked calibration metronome."""
import math

def encode_drum(pcm):
    """Closed-loop BRR predictors keep the low drum free of quantization hiss."""
    output=bytearray();p=q=0
    for start in range(0,len(pcm),16):
        best=None
        for f in range(4):
            for shift in range(13):
                cp,cq=p,q;error=0;ns=[];scale=(1<<shift)*.5
                for sample in pcm[start:start+16]:
                    pred=cp+((-cp)>>4) if f==1 else cp*2+((-cp*3)>>5)-cq+(cq>>4) if f==2 else cp*2+((-cp*13)>>6)-cq+((cq*3)>>4) if f==3 else 0
                    value=max(-8,min(7,round(((sample>>1)-pred)/scale)))
                    decoded=max(-32768,min(32767,((value<<shift)>>1)+pred))
                    decoded=(((decoded*2+32768)&65535)-32768)>>1
                    error+=((sample>>1)-decoded)**2
                    cq,cp=cp,decoded;ns.append(value&15)
                if best is None or error<best[0]:best=(error,f,shift,cp,cq,ns)
        _,f,shift,p,q,ns=best
        output.append((shift<<4)|(f<<2)|(1 if start+16==len(pcm) else 0))
        output.extend((ns[i]<<4)|ns[i+1] for i in range(0,16,2))
    return output

def assemble(calibration_period=125):
    assert calibration_period%125==0
    calibration_divisor=calibration_period//125
    b=bytearray();labels={};relative=[];absolute=[]
    def e(*x):b.extend(x)
    def lab(n):labels[n]=0x200+len(b)
    def br(op,n):e(op,0);relative.append((len(b)-1,n))
    def jump(n):e(0x5F,0,0);absolute.append((len(b)-2,n))
    def dsp(r,v):e(0x8F,r,0xF2,0x8F,v,0xF3)
    def mov(dp,v):e(0x8F,v,dp)
    def clock_start():
        mov(0xF1,0);mov(0x14,0);mov(0x15,0);mov(0xF5,0);mov(0xF6,0);mov(0xF1,4)
    lab('boot');e(0xCD,0xEF,0xBD);mov(0xF1,0)
    for r,v in [(0x6C,0x20),(0x0C,127),(0x1C,127),(0x2C,0),(0x3C,0),
                (0x4D,0),(0x2D,0),(0x3D,0),(0x5D,7),
                (0,112),(1,112),(2,0),(3,6),(4,0),(5,0),(7,127),
                (0x10,112),(0x11,112),(0x12,0),(0x13,8),(0x14,1),(0x15,0),(0x17,127),(0x5C,255)]:dsp(r,v)
    for voice in (0x20,0x30):
        for r,v in [(0,40),(1,40),(2,0),(3,8),(4,2),(5,0),(7,127)]:dsp(voice+r,v)
    for dp,v in [(0x10,0),(0x11,0x40),(0x12,0),(0x14,0),(0x15,0),(0x16,0),
                 (0x18,0),(0x19,125),(0x1A,0),(0x1B,0),(0x1C,6),(0x1D,calibration_divisor),(0x1E,0),(0xFC,0),(0xF4,0),(0xF5,0),(0xF6,0),(0xF7,0)]:mov(dp,v)
    lab('wait');e(0xE4,0xFF);br(0xF0,'packet_check')
    e(0xC4,0x17,0xAB,0x16,0xFA,0x16,0xF7) # tick delta; odd clock version
    e(0x60,0x84,0x14,0xC4,0x14,0xE4,0x15,0x88,0,0xC4,0x15)
    e(0xFA,0x14,0xF5,0xFA,0x15,0xF6,0xAB,0x16,0xFA,0x16,0xF7)
    e(0xE4,0x18);br(0xF0,'packet_check')
    e(0x80,0xE4,0x19,0xA4,0x17)           # SETC / remaining -= tick delta
    br(0xF0,'beat');br(0xB0,'remaining')
    lab('beat');e(0x60,0x88,125,0xC4,0x19)
    e(0x8B,0x1D);br(0xD0,'packet_check');mov(0x1D,calibration_divisor)
    dsp(0x4C,2);jump('packet_check')
    lab('remaining');e(0xC4,0x19)
    lab('packet_check');e(0xE4,0xF4,0x64,0x12)
    br(0xD0,'new_packet');jump('wait')
    lab('new_packet');e(0xC4,0x12,0x68,0x80);br(0xB0,'command')
    # After a seek, source-file loop flags no longer align with the ARAM ring.
    # Rewrite only BRR headers, using the receiver's actual write position.
    e(0x8D,0,0xE4,0x1E);br(0xD0,'plain_byte')
    e(0xE4,0x1A);br(0xD0,'plain_byte')
    e(0xE4,0x10,0x68,0xEF);br(0xD0,'header')
    e(0xE4,0x11,0x68,0xBF);br(0xD0,'header')
    e(0xE4,0xF5,0x28,0xFC,0x08,3);jump('write_first')
    lab('header');e(0xE4,0xF5,0x28,0xFC);jump('write_first')
    lab('plain_byte');e(0xE4,0xF5)
    lab('write_first');e(0xD7,0x10,0xFC,0xE4,0xF6,0xD7,0x10,0xFC,0xE4,0xF7,0xD7,0x10)
    # All three input bytes are now copied. Release the CPU before pointer
    # maintenance so it can prepare the next packet concurrently.
    e(0xFA,0x12,0xF4)
    e(0xAB,0x1A,0xE4,0x1A,0x68,3);br(0xD0,'next_address');mov(0x1A,0)
    lab('next_address')
    e(0x60,0xE4,0x10,0x88,3,0xC4,0x10,0xE4,0x11,0x88,0,0xC4,0x11)
    e(0xE4,0x1E);br(0xD0,'packet_done')
    e(0xE4,0x11,0x68,0xBF);br(0xD0,'packet_done')
    e(0xE4,0x10,0x68,0xF8);br(0xD0,'packet_done');mov(0x10,0);mov(0x11,0x40)
    lab('packet_done');jump('wait')
    lab('ack');e(0xFA,0x12,0xF4);jump('wait')
    lab('command')
    for value,target in [(0x81,'start'),(0x82,'pause'),(0x83,'resume'),(0x84,'calibrate'),(0x85,'seek_start'),(0x86,'volume'),(0x87,'pitch'),(0x88,'resume_muted'),(0x89,'hit2'),(0x8A,'hit3'),(0x8B,'countdown'),(0x8C,'load_samples')]:
        e(0x68,value);br(0xD0,'check'+str(value));jump(target);lab('check'+str(value))
    dsp(0x5C,255);mov(0xF1,0);mov(0x18,0);mov(0x1A,0);mov(0x1E,0);mov(0x10,0);mov(0x11,0x40);jump('ack')
    lab('start');mov(0x18,0)
    for r,v in [(0x5C,0),(0,112),(1,112)]:dsp(r,v)
    mov(0xF2,2);e(0xFA,0x1B,0xF3);mov(0xF2,3);e(0xFA,0x1C,0xF3);dsp(0x4C,1)
    clock_start();jump('ack')
    lab('seek_start');mov(0x18,0)
    for r,v in [(0x5C,0),(0,0),(1,0)]:dsp(r,v)
    mov(0xF2,2);e(0xFA,0x1B,0xF3);mov(0xF2,3);e(0xFA,0x1C,0xF3);dsp(0x4C,1)
    clock_start();jump('ack')
    lab('volume');mov(0xF2,0);e(0xFA,0xF5,0xF3);mov(0xF2,1);e(0xFA,0xF5,0xF3);jump('ack')
    lab('pitch');e(0xFA,0xF5,0x1B,0xFA,0xF6,0x1C);jump('ack')
    lab('pause')
    for r,v in [(0,0),(1,0),(3,0),(0x10,0),(0x11,0)]:dsp(r,v)
    mov(0xF1,0);jump('ack')
    lab('resume')
    for r,v in [(0,112),(1,112)]:dsp(r,v)
    mov(0xF2,2);e(0xFA,0x1B,0xF3);mov(0xF2,3);e(0xFA,0x1C,0xF3)
    mov(0xF1,4);jump('ack')
    lab('resume_muted')
    mov(0xF2,2);e(0xFA,0x1B,0xF3);mov(0xF2,3);e(0xFA,0x1C,0xF3)
    mov(0xF1,4);jump('ack')
    lab('calibrate');mov(0x18,1);mov(0x19,125)
    mov(0x1D,calibration_divisor)
    for r,v in [(0x5C,255),(0x5C,0),(0,0),(1,0),(0x10,112),(0x11,112),
                (0x12,0),(0x13,8),(0x14,1),(0x15,0),(0x17,127)]:dsp(r,v)
    clock_start();dsp(0x4C,2);jump('ack')
    for name,voice,bit in [('hit2',0x20,4),('hit3',0x30,8)]:
        lab(name)
        for register,port in [(4,0xF5),(0,0xF6),(1,0xF6),(3,0xF7)]:mov(0xF2,voice+register);e(0xFA,port,0xF3)
        dsp(0x4C,bit);jump('ack')
    lab('countdown')
    for r,v in [(0x40,80),(0x41,80),(0x42,0),(0x43,8),(0x44,3),(0x45,0),(0x47,127),(0x4C,16)]:dsp(r,v)
    jump('ack')
    lab('load_samples');mov(0x1E,1);e(0xFA,0xF5,0x10,0xFA,0xF6,0x11);jump('ack')
    for pos,n in relative:
        d=labels[n]-(0x200+pos+1);assert -128<=d<=127,(n,d);b[pos]=d&255
    for pos,n in absolute:b[pos:pos+2]=labels[n].to_bytes(2,'little')
    assert len(b)<0x500,len(b)
    b.extend(bytes(0x500-len(b)))
    b.extend(bytes([0,0x40,0,0x40,0,8,0,8,0,10,0,10,0,12,0,12])) # music, calibration, tap, countdown hat
    b.extend(bytes(0x600-len(b)))
    # Short decaying click, directly encoded with filter 0.
    pcm=[int(math.sin(i*2*math.pi*900/16000)*12000*math.exp(-i/70)) for i in range(320)]
    for start in range(0,len(pcm),16):
        block=pcm[start:start+16];shift=next(s for s in range(13) if max(abs(x) for x in block)<=(7<<s))
        ns=[max(-8,min(7,round(v/(1<<shift))))&15 for v in block]
        b.append((shift<<4)|(1 if start+16==len(pcm) else 0))
        b.extend((ns[i]<<4)|ns[i+1] for i in range(0,16,2))
    b.extend(bytes(0x800-len(b))) # ARAM $0A00, clear of music ring $4000
    # A short wood/kick percussion transient; two alternating voices allow
    # quick rolls and simultaneous presses to overlap without cutting tails.
    pcm=[];phase=0.
    for i in range(512):
        phase+=2*math.pi*(85+220*math.exp(-i/24))/16000
        pcm.append(int(11000*math.sin(phase)*math.exp(-i/75)))
    b.extend(encode_drum(pcm))
    from pathlib import Path
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    rate,pcm=wavfile.read(Path(__file__).resolve().parents[1]/'assets/private/hitsounds/sndHat.wav')
    if pcm.ndim>1:pcm=pcm.astype(float).mean(axis=1)
    pcm=resample_poly(pcm.astype(float),16000,rate)
    pcm=np.clip(pcm,-32768,32767).astype(np.int16).tolist()
    pcm.extend([0]*((-len(pcm))%16))
    b.extend(bytes(0xA00-len(b))) # ARAM $0C00
    b.extend(encode_drum(pcm))
    assert len(b)<0x3E00,'Hit samples overlap the streamed music ring'
    return bytes(b)
