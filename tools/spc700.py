"""Assemble the tiny SPC700 streaming receiver using explicit opcode forms.

The CPU sends three bytes in ports 1..3, then changes port 0. The SPC copies
them into a 32760-byte BRR ring and echoes port 0 only after the write.
Commands use bit 7; data packet sequence numbers use only bits 0..6.
"""
from pathlib import Path

def assemble():
    code=bytearray(); labels={}; fix=[]; absolute=[]
    def emit(*bs): code.extend(bs)
    def label(n): labels[n]=len(code)+0x200
    def branch(op,n):
        emit(op,0); fix.append((len(code)-1,n))
    def jump(n):
        emit(0x5F,0,0); absolute.append((len(code)-2,n))
    def dsp(reg,value): emit(0x8F,reg,0xF2,0x8F,value,0xF3)
    label('boot')
    emit(0xCD,0xEF,0xBD)                       # MOV X,#$EF / MOV SP,X
    emit(0x8F,0,0xF1)                         # Disable timers and IPL ROM
    dsp(0x6C,0x20)                            # Echo writes off; DSP running
    dsp(0x0C,0x7F); dsp(0x1C,0x7F)           # Master left/right
    dsp(0x2C,0); dsp(0x3C,0); dsp(0x4D,0)    # No echo or echo voices
    dsp(0x2D,0); dsp(0x3D,0); dsp(0x5D,4)    # No pitch mod/noise; DIR=$0400
    dsp(0x00,0x70); dsp(0x01,0x70)            # Voice 0 left/right
    dsp(0x02,0); dsp(0x03,8)                  # Pitch=$0800 = 16000 Hz
    dsp(0x04,0); dsp(0x05,0); dsp(0x07,0x7F) # SRCN=0; direct GAIN
    dsp(0x5C,0xFF)                            # All voices off
    emit(0x8F,0,0x10,0x8F,0x40,0x11)        # Ring write pointer $4000
    emit(0x8F,0,0x12,0x8F,0,0xF4)           # Sequence=0; ready echo
    emit(0x8F,0,0xFC)                        # Timer 2: 256/64000 Hz = 4 ms
    emit(0x8F,0,0x14,0x8F,0,0x15,0x8F,0,0x16)
    emit(0x8F,0,0xF5,0x8F,0,0xF6,0x8F,0,0xF7)
    label('wait')
    # Publish the audio clock through the SPC->CPU ports. These are separate
    # from the CPU->SPC ports used by the incoming BRR packet. Port 3 is an
    # even/odd version counter so the CPU can read an atomic 16-bit snapshot.
    emit(0xE4,0xFF)                          # Timer 2 read-to-clear counter
    branch(0xF0,'packet_check')
    emit(0xAB,0x16,0xFA,0x16,0xF7)          # Begin seqlock write (odd)
    emit(0x60,0x84,0x14,0xC4,0x14)          # ADD A,$14 / MOV $14,A
    emit(0xE4,0x15,0x88,0,0xC4,0x15)
    emit(0xFA,0x14,0xF5,0xFA,0x15,0xF6)
    emit(0xAB,0x16,0xFA,0x16,0xF7)          # End seqlock write (even)
    label('packet_check')
    emit(0xE4,0xF4,0x64,0x12)                # MOV A,$F4 / CMP A,$12
    branch(0xF0,'wait')
    emit(0xC4,0x12,0x68,0x80)                # Save packet; CMP A,#$80
    branch(0xB0,'command')
    emit(0x8D,0,0xE4,0xF5,0xD7,0x10)        # Y=0; MOV A,$F5 / MOV [$10]+Y,A
    emit(0xFC,0xE4,0xF6,0xD7,0x10)
    emit(0xFC,0xE4,0xF7,0xD7,0x10)
    emit(0x60,0xE4,0x10,0x88,3,0xC4,0x10)   # ADD write pointer,3
    emit(0xE4,0x11,0x88,0,0xC4,0x11)
    emit(0xE4,0x11,0x68,0xBF)
    branch(0xD0,'ack')
    emit(0xE4,0x10,0x68,0xF8)
    branch(0xD0,'ack')
    emit(0x8F,0,0x10,0x8F,0x40,0x11)
    label('ack')
    emit(0xFA,0x12,0xF4)                     # MOV $F4,$12 (source first opcode)
    branch(0x2F,'wait')
    label('command')
    emit(0x68,0x81); branch(0xF0,'start')
    emit(0x68,0x83); branch(0xF0,'resume')
    emit(0x68,0x82); branch(0xF0,'pause')
    # STOP/RESET ($80) silences DSP and resets ring pointer.
    dsp(0x5C,0xFF)
    emit(0x8F,0,0xF1)
    emit(0x8F,0,0x10,0x8F,0x40,0x11)
    jump('ack')
    label('start')
    dsp(0x5C,0); dsp(0x02,0); dsp(0x03,8)
    dsp(0x00,0x70); dsp(0x01,0x70); dsp(0x4C,1)
    emit(0x8F,0,0x14,0x8F,0,0x15)
    emit(0x8F,0,0xF5,0x8F,0,0xF6,0x8F,4,0xF1)
    jump('ack')
    label('pause')
    dsp(0x00,0); dsp(0x01,0); dsp(0x03,0)
    emit(0x8F,0,0xF1)
    jump('ack')
    label('resume')
    dsp(0x03,8); dsp(0x00,0x70); dsp(0x01,0x70)
    emit(0x8F,4,0xF1)
    jump('ack')
    for pos,n in fix:
        delta=labels[n]-(0x200+pos+1)
        assert -128<=delta<=127,(n,delta)
        code[pos]=delta&255
    for pos,n in absolute:
        code[pos:pos+2]=labels[n].to_bytes(2,'little')
    assert len(code)<0x200
    code.extend(bytes(0x200-len(code)))
    code.extend(bytes([0,0x40,0,0x40]))         # Sample 0 start/loop=$4000
    return code

if __name__=='__main__':
    Path('build/spc.bin').write_bytes(assemble())
