.ifndef MSU_DATA_VERSION
MSU_DATA_VERSION=12
.endif
; MSU-1 revision 1/2 registers. PCM at 1x; BRR data-port streaming at
; other speeds. Checkpoints select independently authored PCM entry tracks.
msu_detect:
.ifdef ROM_DATA_BUILD
    ; All visual events and compressed music are inside this cartridge.
    stz msu_present
    stz msu_pcm
    sec
    rts
.else
    lda #1
    sta msu_data_busy
    sep #$20
    .a8
    lda $2002
    cmp #'S'
    bne @missing
    lda $2003
    cmp #'-'
    bne @missing
    lda $2004
    cmp #'M'
    bne @missing
    lda $2005
    cmp #'S'
    bne @missing
    lda $2006
    cmp #'U'
    bne @missing
    lda $2007
    cmp #'1'
    bne @missing
    ; Animation snapshots and ROM descriptors must match this data version.
    stz $2000
    stz $2001
    stz $2002
    stz $2003
@wait_data:
    lda $2000
    bit #$80
    bne @wait_data
    ldx #0
@data_version:
    lda $2001
    cmp f:msu_data_signature,x
    bne @missing
    inx
    cpx #14
    bcc @data_version
    rep #$20
    .a16
    lda #1
    sta msu_present
    stz msu_data_busy
    sec
    rts
@missing:
    rep #$20
    .a16
    stz msu_present
    stz msu_data_busy
    clc
    rts
.endif
msu_data_signature:
    .byte "ADOFAI-MSU1",0,MSU_DATA_VERSION,0

prepare_note_margin:
    lda step
    inc a
    asl a
    tax
    lda step
    inc a
    tax
    lda f:NOTE_CCW,x
    and #4
    beq @margin_normal
    lda #800
    bra @margin_ready
@margin_normal:
    lda #100
@margin_ready:
.ifdef NEO_BUILD
    jsl neo_far_note_margin
.endif
    sta input_margin
    cmp #100
    beq @normal
    sta math_b
    lda rough_window
    sta math_a
    jsr multiply_points
    lda #100
    sta math_b
    jsr divide32
    lda math_lo
    bra @store
@normal:
    lda rough_window
@store:
    sta input_rough_window
    rts
; Standalone adaptive builds use the otherwise-unused PCM track words
; for a second stream address, and the unused timeline pointer for seeks.
msu_load_song:
    stz msu_elapsed_frames
    lda selected_level
    asl a
    asl a
    asl a
    sta scratch
    asl a
    clc
    adc scratch
    tax
.ifdef FAST_AUDIO_BUILD
    lda speed_tenths
    cmp #11
    bcc :+
    inx
    inx
    inx
    inx
:
.endif
    lda f:msu_descriptors,x
    sta msu_song_base
    sta msu_seek_offset
    sta msu_stream_cursor
    lda f:msu_descriptors+2,x
    sta msu_song_base+2
    sta msu_seek_offset+2
    sta msu_stream_cursor+2
.ifdef FAST_AUDIO_BUILD
    lda speed_tenths
    cmp #11
    bcc :+
    dex
    dex
    dex
    dex
:
.endif
    lda f:msu_descriptors+4,x
    sta msu_track
    lda f:msu_descriptors+6,x
    sta msu_checkpoint_base
    lda f:msu_descriptors+8,x
    sta animation_base
    lda f:msu_descriptors+10,x
    sta animation_base+2
    lda f:msu_descriptors+12,x
    sta animation_table
    lda f:msu_descriptors+14,x
    sta animation_table+2
    lda f:msu_descriptors+16,x
    sta animation_cells
    lda f:msu_descriptors+18,x
    sta pattern_nodes
    lda f:msu_descriptors+20,x
    sta m7_timeline_base
    lda f:msu_descriptors+22,x
    sta m7_timeline_base+2
    jsr msu_seek_data
    jmp msu_load_track

msu_load_checkpoint:
.ifdef FAST_AUDIO_BUILD
    lda speed_tenths
    cmp #11
    bcc @normal_seek
    lda m7_timeline_base
    sta transfer_ptr
    lda m7_timeline_base+2
    sta transfer_ptr+2
    lda checkpoint_record
    dec a
    ldy #0
@fast_entry:
    cmp #14
    bcc @fast_offset
    sec
    sbc #14
    iny
    iny
    iny
    iny
    bra @fast_entry
@fast_offset:
    lda [transfer_ptr],y
    sta music_ptr
    iny
    iny
    lda [transfer_ptr],y
    sta music_ptr+2
@normal_seek:
.endif
    stz msu_elapsed_frames
    lda music_ptr
    clc
    adc msu_song_base
    sta msu_seek_offset
    sta msu_stream_cursor
    lda music_ptr+2
    and #255
    adc msu_song_base+2
    sta msu_seek_offset+2
    sta msu_stream_cursor+2
    jsr msu_seek_data
    ; X is the checkpoint record byte offset; divide by 14.
    ldx checkpoint_record
    dex
    txa
    ldx #0
@entry:
    cmp #14
    bcc @track
    sec
    sbc #14
    inx
    bra @entry
@track:
    txa
    sta msu_checkpoint_index
    clc
    adc msu_checkpoint_base
    sta msu_track
    jmp msu_load_track

msu_seek_data:
.ifdef ROM_DATA_BUILD
    lda msu_seek_offset
    sta rom_data_ptr
    sep #$20
    .a8
.ifdef SA1_BUILD
    lda msu_seek_offset+2
    and #$70
    lsr a
    lsr a
    lsr a
    lsr a
    sta $2223
    sta f:$40000C
    lda msu_seek_offset+2
    and #$0F
    ora #$F0
.else
    lda msu_seek_offset+2
    cmp #$40
    bcs :+
    ora #$C0
:
.endif
    sta rom_data_ptr+2
    rep #$20
    .a16
    rts
.else
    lda msu_seek_offset
    sta $2000
    lda msu_seek_offset+2
    sta $2002
    sep #$20
    .a8
@busy:
    lda $2000
    bmi @busy
    rep #$20
    .a16
    rts
.endif

msu_load_track:
    stz msu_pcm
.ifndef ROM_DATA_BUILD
    lda speed_tenths
    cmp #10
    bne @done
    lda msu_track
    sta $2004
    sep #$20
    .a8
@busy:
    lda $2000
    bit #$40
    bne @busy
    bit #8
    bne @missing
    lda #196
    sta $2006
    rep #$20
    .a16
    inc msu_pcm
@done:
    rts
@missing:
    rep #$20
    .a16
    rts
.else
    rts
.endif

; Called before the SPC port handshake. Preserve its X/Y convention.
msu_command:
    sta msu_command_saved
    phx
    phy
    lda msu_present
    jeq @done
    lda msu_command_saved
    cmp #$80
    jeq @stop
    lda msu_pcm
    jeq @done
    lda msu_command_saved
    cmp #$81
    beq @start
    cmp #$85
    beq @seek_start
    cmp #$83
    beq @resume
    cmp #$82
    jeq @pause
    cmp #$86
    jne @done
    ; Match the checkpoint's fade-in while the SPC music voice stays muted.
    ; Reading an APU port returns SPC output (the clock), not the volume
    ; just written to its input port. Use the CPU's saved command parameter.
    lda msu_volume
    and #255
    cmp #112
    bcs @full
    sta msu_volume
    lsr a
    clc
    adc msu_volume
    sta msu_volume_scaled
    lda msu_volume
    lsr a
    lsr a
    clc
    adc msu_volume_scaled
    bra @volume
@full:
    ; PCM and SPC percussion are mixed by the host. Reserve the same
    ; practical headroom as BRR instead of driving PCM at full scale.
    lda #196
@volume:
    sep #$20
    .a8
    sta $2006
    stz $2141
    bra @restore
@start:
    sep #$20
    .a8
    lda #196
    sta $2006
    bra @play
@seek_start:
    sep #$20
    .a8
    stz $2006
@play:
    rep #$20
    .a16
    lda #1
    sta msu_elapsed_frames
    sep #$20
    .a8
    lda #1
    sta $2007
    rep #$20
    .a16
    lda #$85
    sta msu_command_saved
    bra @done
@resume:
    sep #$20
    .a8
    lda #1
    sta $2007
    rep #$20
    .a16
    lda #$88
    sta msu_command_saved
    bra @done
@pause:
    sep #$20
    .a8
    stz $2007
    bra @restore
@stop:
    sep #$20
    .a8
    stz $2007
    rep #$20
    .a16
    stz msu_pcm
@restore:
    rep #$20
    .a16
@done:
    ply
    plx
    lda msu_command_saved
    rts
