spc_upload:
    sep #$20
    .a8
@ready:
    lda $2140
    cmp #$AA
    bne @ready
    lda $2141
    cmp #$BB
    bne @ready
    ldx #$0200
    stx $2142
    lda #1
    sta $2141
    lda #$CC
    sta $2140
@accept:
    cmp $2140
    bne @accept
    ldy #0
@byte:
.ifdef SPC_DRIVER_ADDR
    tyx
    lda f:SPC_DRIVER_ADDR,x
.else
    lda spc_image,y
.endif
    sta $2141
    tya
    sta $2140
@echo:
    cmp $2140
    bne @echo
    iny
.ifdef SPC_DRIVER_ADDR
    cpy #SPC_DRIVER_BYTES
.else
    cpy #spc_image_end-spc_image
.endif
    bne @byte
    ldx #$0200
    stx $2142
    stz $2141
    tya
    inc a
    sta $2140
@boot:
    lda $2140
    bne @boot
    rep #$20
    .a16
.ifdef MSU_BUILD
    ; Channel 1 is reserved for three-byte SPC stream packets. Keep its
    ; fixed destination separate from graphics and MSU/WRAM DMA channels.
    lda #$4104
    sta $4310
    sep #$20
    .a8
    lda #.bankbyte(AUDIO_FIFO)
    sta $4314
    rep #$20
    .a16
.endif
    rts
play_hit_sound:
.ifdef HIT_SOUND_BANKS
    phx
    phy
    lda transfer_ptr
    pha
    lda transfer_ptr+2
    pha
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    tax
    lda f:HIT_SOUND_DESCRIPTORS_ADDR,x
    sta transfer_ptr
    sep #$20
    .a8
    lda f:HIT_SOUND_DESCRIPTORS_ADDR+2,x
    sta transfer_ptr+2
    rep #$20
    .a16
    lda f:SOUND_NOTE
    asl a
    tay
    lda [transfer_ptr],y
    pha
    and #$FF00
    beq @silent
    pla
    jsr prepare_hit_command
    sep #$20
    .a8
    pha
    and #31
    sta $2141
    pla
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    bne :+
    lda #8
:
    sta $2143
    xba
    ; Leave mixing headroom for the song plus two overlapping tap voices.
    ; The DSP clips their sum before its master-volume control.
    lsr a
    sta $2142
    rep #$20
    .a16
    pla
    sta transfer_ptr+2
    pla
    sta transfer_ptr
    ply
    plx
    bra @command
@silent:
    pla
    pla
    sta transfer_ptr+2
    pla
    sta transfer_ptr
    ply
    plx
    rts
.else
    jsr prepare_hit_command
    sep #$20
    .a8
    lda #2
    sta $2141
    lda #40
    sta $2142
    lda #8
    sta $2143
    rep #$20
    .a16
.endif
@command:
    lda f:HIT_SOUND_COUNT
    inc a
    sta f:HIT_SOUND_COUNT
    lda f:HIT_SOUND_COMMAND
    and #1
    eor #1
    sta f:HIT_SOUND_COMMAND
    clc
    adc #$89
    jmp spc_command

; Finish a queued stream packet before reusing its argument ports.
prepare_hit_command:
.ifdef MSU_BUILD
    pha
    lda #1
    sta apu_busy
    lda f:AUDIO_PACKET_INFLIGHT
    beq @ready
    sep #$20
    .a8
@wait:
    lda $2140
    cmp packet_seq
    bne @wait
    rep #$20
    .a16
    lda #0
    sta f:AUDIO_PACKET_INFLIGHT
@ready:
    pla
.endif
    rts

.ifdef HIT_SOUND_BANKS
load_hit_bank:
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    tax
    lda f:HIT_SOUND_DESCRIPTORS_ADDR+3,x
    sta transfer_ptr
    sep #$20
    .a8
    lda f:HIT_SOUND_DESCRIPTORS_ADDR+5,x
    sta transfer_ptr+2
    rep #$20
    .a16
    jsr prepare_hit_command
    lda #$0710
    sta $2141
    lda #$8C
    jsr spc_command
    lda #38
    sta packets_left
    jsr upload_hit_packets
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    tax
    lda f:HIT_SOUND_DESCRIPTORS_ADDR+6,x
    beq @second_region
    sta packets_left
    jsr prepare_hit_command
    lda #$1200
    sta $2141
    lda #$8C
    jsr spc_command
    jsr upload_hit_packets
@second_region:
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    tax
    lda f:HIT_SOUND_DESCRIPTORS_ADDR+8,x
    beq @loaded
    sta packets_left
    jsr prepare_hit_command
    lda #$C000
    sta $2141
    lda #$8C
    jsr spc_command
    jsr upload_hit_packets
@loaded:
    lda #$80
    jmp spc_command

upload_hit_packets:
    sep #$20
    .a8
    ldy #0
@packet:
    lda [transfer_ptr],y
    sta $2141
    iny
    lda [transfer_ptr],y
    sta $2142
    iny
    lda [transfer_ptr],y
    sta $2143
    iny
    lda packet_seq
    inc a
    and #$7F
    sta packet_seq
    sta $2140
@ack:
    cmp $2140
    bne @ack
    rep #$20
    .a16
    dec packets_left
    beq @done
    sep #$20
    .a8
    bra @packet
@done:
    .a16
    tya
    clc
    adc transfer_ptr
    sta transfer_ptr
    rts
.endif
spc_command:
.ifdef MSU_BUILD
    pha
    lda #1
    sta apu_busy
    pla
    pha
    lda f:AUDIO_PACKET_INFLIGHT
    beq @command_ready
    sep #$20
    .a8
@packet_ack:
    lda $2140
    cmp packet_seq
    bne @packet_ack
    rep #$20
    .a16
    lda #0
    sta f:AUDIO_PACKET_INFLIGHT
@command_ready:
    pla
    cmp #$80
    beq @reset_fifo
    cmp #$84
    beq @reset_fifo
    cmp #$85
    bne @keep_fifo
@reset_fifo:
    pha
    lda #0
    sta f:AUDIO_FIFO_HEAD
    sta f:AUDIO_FIFO_TAIL
    pla
@keep_fifo:
    jsr msu_command
.endif
    sep #$20
    .a8
    sta $2140
@ack:
    cmp $2140
    bne @ack
    rep #$20
    .a16
.ifdef MSU_BUILD
    stz apu_busy
.endif
    rts
stream_packets:
    lda packets_left
    jeq @done
.ifdef MSU_BUILD
    lda msu_stream_cursor
    sta msu_seek_offset
    lda msu_stream_cursor+2
    sta msu_seek_offset+2
    lda packets_left
    sta scratch
    asl a
    clc
    adc scratch
    clc
    adc msu_stream_cursor
    sta msu_stream_cursor
    bcc @stream_address
    inc msu_stream_cursor+2
@stream_address:
    jsr msu_seek_data
.endif
    sep #$20
    .a8
@packet:
.ifdef MSU_BUILD
    data_read8
    sta $2141
    data_read8
    sta $2142
    data_read8
    sta $2143
.else
    ldy #0
    lda [music_ptr],y
    sta $2141
    iny
    lda [music_ptr],y
    sta $2142
    iny
    lda [music_ptr],y
    sta $2143
.endif
    lda packet_seq
    inc a
    and #$7F
    sta packet_seq
    sta $2140
@ack:
    cmp $2140
    bne @ack
    rep #$20
    .a16
    lda music_ptr
    clc
    adc #3
    sta music_ptr
    sep #$20
    .a8
    bcc @no_bank
    inc music_ptr+2
@no_bank:
    rep #$20
    .a16
    dec packets_left
    beq @done
    sep #$20
    .a8
    bra @packet
@done:
    rep #$20
    .a16
    rts
stream_frame:
.ifdef MSU_BUILD
    ; Refill between animation transfers too. A busy MSU data port may
    ; suppress an NMI refill; cooperative servicing drains that backlog.
    jmp msu_audio_tick
.else
    lda audio_ticks
    sec
    sbc stream_ticks
    sta scratch
    stz packets_left
@tick:
    lda scratch
    beq @ready
    lda clock_fraction
    clc
    adc speed_stream
    pha
    and #511
    sta clock_fraction
    pla
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    clc
    adc packets_left
    sta packets_left
    dec scratch
    bra @tick
@ready:
    lda audio_ticks
    sta stream_ticks
    jmp stream_packets
.endif
read_audio_clock:
    sep #$20
    .a8
@snapshot:
    lda $2143
    bit #1
    bne @snapshot
    sta clock_version
    rep #$20
    .a16
    lda $2141
    sta audio_ticks
    sep #$20
    .a8
    lda $2143
    cmp clock_version
    bne @snapshot
    rep #$20
    .a16
    lda audio_ticks
    sec
    sbc clock_ticks
    sta scratch
    lda audio_ticks
    sta clock_ticks
@tick:
    lda scratch
    beq @elapsed
    lda speed_scale
    ldx state
    cpx #5
    bne @scale
    lda #15754
@scale:
    clc
    adc clock_song_frac
    sta clock_song_frac
    bcc @centis
    inc clock_song_frames
@centis:
    lda run_cs_frac
    clc
    adc #2
    cmp #5
    bcc @fraction
    sec
    sbc #5
    inc run_centis
@fraction:
    sta run_cs_frac
    dec scratch
    bra @tick
@elapsed:
.ifdef MSU_BUILD
    lda msu_pcm
    beq @spc_elapsed
    ; The MSU DAC and SPC crystal are independent. PCM uses the NTSC video
    ; clock; applying the SPC's slight pitch drift would desync long songs.
    lda msu_elapsed_frames
    sta clock_song_frames
    stz clock_song_frac
    sta math_a
    lda #10000
    sta math_b
    jsr multiply_points
    lda #6010
    sta math_b
    jsr divide32
    lda math_lo
    sta run_centis
@spc_elapsed:
.endif
    lda clock_song_frac
    clc
    adc #$8000
    lda clock_song_frames
    adc #0
    clc
    adc music_origin
    sta elapsed
    rts
.ifdef MSU_BUILD

msu_audio_tick:
.ifdef NEO_BUILD
    ; A nested NMI must not reprogram DMA 0 underneath an early scene
    ; upload. The IRQ tail performs this refill after all PPU work ends.
    lda f:EARLY_IRQ_RUNNING
    jne @done
.endif
    lda music_active
    jeq @done
    lda msu_pcm
    jne @done
    lda apu_busy
    jne @done
    lda msu_data_busy
    jne @done
    lda state
    cmp #1
    beq @active
    cmp #3
    jne @done
@active:
    lda scratch
    sta audio_saved_scratch
    lda scratch2
    sta audio_saved_scratch2
    lda #1
    sta msu_data_busy
    lda nmi_audio_ticks
    sec
    sbc stream_ticks
    sta scratch
    lda nmi_audio_ticks
    sta stream_ticks
@tick:
    lda scratch
    beq @packets
    lda clock_fraction
    clc
    adc speed_stream
    pha
    and #511
    sta clock_fraction
    pla
    .repeat 9
    lsr a
    .endrepeat
    clc
    adc audio_pending_packets
    sta audio_pending_packets
    dec scratch
    bra @tick
@packets:
    lda audio_pending_packets
    cmp #91
    bcc @budget
    lda #90
@budget:
    sta f:AUDIO_FIFO_PACKETS
    asl a
    clc
    adc f:AUDIO_FIFO_PACKETS
    sta f:AUDIO_FIFO_BYTES
    lda f:AUDIO_FIFO_TAIL
    sec
    sbc f:AUDIO_FIFO_HEAD
    dec a
    and #1023
    sta f:AUDIO_FIFO_FREE
@space:
    lda f:AUDIO_FIFO_BYTES
    cmp f:AUDIO_FIFO_FREE
    bcc @fill
    beq @fill
    sec
    sbc #3
    sta f:AUDIO_FIFO_BYTES
    lda f:AUDIO_FIFO_PACKETS
    dec a
    sta f:AUDIO_FIFO_PACKETS
    bra @space
@fill:
    lda audio_pending_packets
    sec
    sbc f:AUDIO_FIFO_PACKETS
    sta audio_pending_packets
    lda f:AUDIO_FIFO_BYTES
    beq @restore
    lda transfer_len
    pha
    lda transfer_dest
    pha
    lda transfer_wbank
    pha
    lda msu_stream_cursor
    sta msu_seek_offset
    clc
    adc f:AUDIO_FIFO_BYTES
    sta msu_stream_cursor
    lda msu_stream_cursor+2
    sta msu_seek_offset+2
    adc #0
    sta msu_stream_cursor+2
    jsr msu_seek_data
@dma:
    lda #1024
    sec
    sbc f:AUDIO_FIFO_HEAD
    cmp f:AUDIO_FIFO_BYTES
    bcc :+
    lda f:AUDIO_FIFO_BYTES
:
    sta transfer_len
    lda f:AUDIO_FIFO_HEAD
    clc
    adc #.loword(AUDIO_FIFO)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda f:AUDIO_FIFO_HEAD
    clc
    adc transfer_len
    and #1023
    sta f:AUDIO_FIFO_HEAD
    lda f:AUDIO_FIFO_BYTES
    sec
    sbc transfer_len
    sta f:AUDIO_FIFO_BYTES
    bne @dma
    pla
    sta transfer_wbank
    pla
    sta transfer_dest
    pla
    sta transfer_len
@restore:
    lda #1
    sta animation_seek_dirty
    lda audio_saved_scratch
    sta scratch
    lda audio_saved_scratch2
    sta scratch2
    ; Keep NMI out until the main-thread caller's scratch is restored.
    stz msu_data_busy
@done:
    rts

; Send one packet when the SPC is ready, then return to useful CPU work.
; The producer commits FIFO bytes before advancing HEAD. Ports and the
; consumer cursor are protected against an interrupting command/refill.
.ifdef SA1_BUILD
.segment "FASTWRAM"
.endif
audio_pump:
    php
    rep #$20
    .a16
    pha
    lda music_active
    jeq audio_pump_exit
    lda msu_pcm
    jne audio_pump_exit
    lda apu_busy
    jne audio_pump_exit
    lda f:AUDIO_PACKET_INFLIGHT
    beq @ready
    sep #$20
    .a8
    lda $2140
    cmp packet_seq
    jne audio_pump_done8
    rep #$20
    .a16
    lda #0
    sta f:AUDIO_PACKET_INFLIGHT
@ready:
    lda f:AUDIO_FIFO_HEAD
    sec
    sbc f:AUDIO_FIFO_TAIL
    and #1023
    cmp #3
    jcc audio_pump_exit
    ; Polls that cannot send never touch X. Save it once for the whole
    ; drain, rather than paying a stack round trip on every idle poll.
    phx
@send:
    lda #1
    sta apu_busy
    lda f:AUDIO_FIFO_TAIL
    tax
    cpx #1021
    bcs @wrapped_packet
    clc
    adc #.loword(AUDIO_FIFO)
    sta $4312
    lda #3
    sta $4315
    sep #$20
    .a8
    lda #2
    sta $420B
    rep #$20
    .a16
    txa
    clc
    adc #3
    tax
    bra @packet_loaded
@wrapped_packet:
    sep #$20
    .a8
    lda f:AUDIO_FIFO,x
    sta $2141
    inx
    cpx #1024
    bcc :+
    ldx #0
:
    lda f:AUDIO_FIFO,x
    sta $2142
    inx
    cpx #1024
    bcc :+
    ldx #0
:
    lda f:AUDIO_FIFO,x
    sta $2143
    inx
    cpx #1024
    bcc :+
    ldx #0
:
    rep #$20
    .a16
@packet_loaded:
    txa
    sta f:AUDIO_FIFO_TAIL
    lda #1
    sta f:AUDIO_PACKET_INFLIGHT
    sep #$20
    .a8
    lda packet_seq
    inc a
    and #$7F
    sta packet_seq
    sta $2140
    rep #$20
    .a16
    ; A long graphics batch must not build an ever-growing transport
    ; delay. Drain excess queued audio with bounded handshake waits;
    ; ordinary packets still overlap useful CPU work.
    lda f:AUDIO_FIFO_HEAD
    sec
    sbc f:AUDIO_FIFO_TAIL
    and #1023
    cmp #192
    bcc @sent
    sep #$20
    .a8
@catch_up:
    lda $2140
    cmp packet_seq
    bne @catch_up
    rep #$20
    .a16
    lda #0
    sta f:AUDIO_PACKET_INFLIGHT
    ; The threshold above guarantees at least one complete packet.
    ; NMI can append to this FIFO but cannot consume its tail.
    jmp @send
@sent:
    ; Keep command ownership through catch-up ACK waits. An input-poll
    ; sound must never replace the packet ACK while this loop awaits it.
    stz apu_busy
    plx
    ; A note due during the packet handshake runs as soon as ports are free.
    lda f:SOUND_PENDING
    beq audio_pump_exit
    jsr service_tap_sounds
audio_pump_exit:
    pla
    plp
    rts
audio_pump_done8:
    rep #$20
    .a16
    bra audio_pump_exit
.endif

.segment "CODE"
