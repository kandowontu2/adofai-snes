; Each rising button edge is a tap, including chords in a single poll.
; The graphics publisher can miss a frame without changing the tap judgment.
pop_tap:
.ifdef NEO_BUILD
    stz tap_release
.endif
    stz tap_latency
    lda pressed
    and #($FFFF-TAP_MASK)
    sta pressed
    lda chart_time
    sta tap_clock
    lda chart_frac
    sta tap_frac
    ldx tap_tail
    cpx tap_head
    jeq @done
    lda audio_ticks
    sec
    sbc tap_stamps,x
    bpl :+
    jmp @done
:
    sta tap_delta
    sta tap_latency
    lda tap_buttons,x
.ifdef NEO_BUILD
    and #2
    sta tap_release
    lda tap_buttons,x
.endif
    and #TAP_MASK
    sta tap_mask_remaining
    dec a
    and tap_mask_remaining
    pha
    lda tap_buttons,x
    and #3
    ora 1,s
    sta tap_buttons,x
    pla
    eor tap_mask_remaining
    ora pressed
    sta pressed
    lda tap_buttons,x
    and #TAP_MASK
    bne @timestamp
    txa
    clc
    adc #2
    and #TAP_QUEUE_MASK
    sta tap_tail
@timestamp:
    lda clock_song_frac
    sec
    sbc speed_offset_frac
    sta tap_frac
    lda clock_song_frames
    sbc speed_offset
    clc
    adc music_origin
    sta tap_clock
@rewind:
    lda tap_delta
    beq @round
    lda tap_frac
    sec
    sbc speed_scale
    sta tap_frac
    bcs @tick
    dec tap_clock
@tick:
    dec tap_delta
    bra @rewind
@round:
    lda tap_frac
    bpl @clamp
    inc tap_clock
@clamp:
    lda tap_clock
    cmp #$8000
    bcc @done
    stz tap_clock
@done:
    rts

 ; Schedule percussion on the uncalibrated music clock, independently of
; input and render progress. All working state is private to the NMI.
service_tap_sounds:
.ifdef HITS_IN_MUSIC
    ; Scheduled percussion shares the decoded music samples. No frame-timed
    ; DSP trigger can duplicate it, drift, or bunch up during a render stall.
    rts
.else
    lda input_sound_mask
    beq :+
    rts
:
    inc input_sound_mask
    phx
    phy
    lda state
    cmp #1
    jne @done
    lda music_active
    jeq @done
.ifdef SA1_BUILD
    ; Some source tracks already contain their note percussion. Their missing
    ; intro hits are mixed into the audio at build time, never fired twice.
    lda selected_level
    asl a
    tax
    lda hit_music_embedded,x
    jne @done
.endif
    lda nmi_audio_ticks
    sta f:SOUND_NOW
    sec
    sbc f:SOUND_TICKS
    tax
    lda f:SOUND_NOW
    sta f:SOUND_TICKS
@tick:
    cpx #0
    beq @elapsed
    lda f:SOUND_FRAC
    clc
    adc speed_scale
    sta f:SOUND_FRAC
    bcc :+
    lda f:SOUND_FRAMES
    inc a
    sta f:SOUND_FRAMES
:
    dex
    bra @tick
@elapsed:
.ifdef MSU_BUILD
    lda msu_pcm
    beq @compressed
    lda msu_elapsed_frames
    bra @origin
@compressed:
.endif
    lda f:SOUND_FRAC
    clc
    adc #$8000
    lda f:SOUND_FRAMES
    adc #0
@origin:
    clc
    adc music_origin
    sta f:SOUND_NOW
.ifdef MSU_BUILD
    lda apu_busy
    beq :+
    lda #1
    sta f:SOUND_PENDING
    bra @done
:
.endif
    lda #0
    sta f:SOUND_PENDING
    ; Bound command traffic in pathological charts without dropping notes.
    ldy #8
@note:
    lda f:SOUND_NOTE
    cmp last_note
    bcc :+
    bne @done
:
    asl a
    tax
.ifdef SA1_BUILD
    ; A track-specific music alignment correction affects percussion only.
    ; Do not apply input/display calibration to the audible music clock.
    phx
    lda selected_level
    asl a
    tax
.ifdef MSU_BUILD
    lda msu_pcm
    beq @compressed_sound_lead
    lda f:SOUND_NOW
    clc
    adc hit_pcm_lead_frames,x
    bra @sound_deadline
@compressed_sound_lead:
.endif
    lda f:SOUND_NOW
    clc
    adc hit_music_lead_frames,x
@sound_deadline:
    plx
.else
    lda f:SOUND_NOW
.endif
    cmp f:NOTE_TIME,x
    bcc @done
    lda f:SOUND_NOTE
    tax
    lda f:NOTE_FLAGS,x
    and #8
    bne @advance
    phy
    jsr play_hit_sound
    ply
@advance:
    lda f:SOUND_NOTE
    inc a
    sta f:SOUND_NOTE
    dey
    bne @note
@done:
    ply
    plx
    stz input_sound_mask
    rts
.endif

get_chart_time:
    ; Autoplay shares the music output path. Manual input/display latency
    ; compensation must not shift its landings or percussion off the song.
    lda autoplay
    beq @manual_offset
    lda clock_song_frac
    sta chart_frac
    lda clock_song_frames
    clc
    adc music_origin
    bra @autoplay_round
@manual_offset:
    lda clock_song_frac
    sec
    sbc speed_offset_frac
    sta chart_frac
    lda clock_song_frames
    sbc speed_offset
    clc
    adc music_origin
@autoplay_round:
    ldx chart_frac
    bpl @round
    inc a
@round:
    cmp #$8000
    bcc @store
    lda #0
@store:
    sta chart_time
    rts
