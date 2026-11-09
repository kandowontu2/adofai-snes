; Checkpoints are imported from the original effects, including tile offsets.
; Each 14-byte record is trigger, restart floor, song origin, BRR address,
; lead-in end, local beat length, and padding. Audio seek entries use filter 0.
activate_checkpoint:
    lda time_attack
    bne @done
    lda practice
    bne @done
@next:
    ldx checkpoint_next
    cpx checkpoint_bytes
    bcs @done
    lda f:CHECKPOINTS,x
    cmp step
    bcc @activate
    beq @activate
    rts
@activate:
    lda f:CHECKPOINTS+2,x
    cmp checkpoint_floor
    bcc @consume
    beq @consume
    sta checkpoint_floor
    txa
    inc a
    sta checkpoint_record
    lda #75
    sta checkpoint_flash
    jsr save_checkpoint_stats
@consume:
    lda checkpoint_next
    clc
    adc #14
    sta checkpoint_next
    bra @next
@done:
    rts

retry_game:
    lda state
    cmp #2
    bne @full
    lda checkpoint_floor
    bne @checkpoint
@full:
    jmp start_game
@checkpoint:
    stz music_active
    jsr reset_run_stats
    ; Leave the death scene on screen while the new audio ring is filled.
    lda #$80
    jsr spc_command
    ldx checkpoint_record
    dex
    lda f:CHECKPOINTS+4,x
    sta music_origin
    sta elapsed
    sec
    sbc speed_offset
    bpl @clock
    lda #0
@clock:
    sta chart_time
    sta overload_last
    lda f:CHECKPOINTS+6,x
    sta music_ptr
    sep #$20
    .a8
    lda f:CHECKPOINTS+8,x
    sta music_ptr+2
    rep #$20
    .a16
.ifdef MSU_BUILD
    jsr msu_load_checkpoint
    ldx checkpoint_record
    dex
.endif
    lda f:CHECKPOINTS+9,x
    sta checkpoint_ready
    lda f:CHECKPOINTS+11,x
    sta checkpoint_beat
    ; Vanilla counts backward from the next landing, not the checkpoint
    ; tile's arrival.
    lda checkpoint_floor
    inc a
    asl a
    tax
    lda f:NOTE_TIME,x
    sta checkpoint_click_next
    lda #4
    sta checkpoint_clicks_left
    ldy #4
@countdown_start:
    lda checkpoint_click_next
    sec
    sbc checkpoint_beat
    sta checkpoint_click_next
    dey
    bne @countdown_start
    lda checkpoint_floor
    sta step
    inc a
    sta f:SOUND_NOTE
    stz stream_ticks
    stz audio_ticks
    stz packet_seq
    stz music_active
    stz combo
    stz perfects
    stz misses
    stz feedback
    stz feedback_time
    stz last_error
    stz checkpoint_flash
    stz overload
    stz overload_phase
    stz fail_reason
    stz trail_head
    stz trail_count
    inc checkpoints_used
    lda #1
    sta checkpoint_preroll
    ldx #0
@effects:
    stz HIT_TIMES,x
    inx
    inx
    cpx #16
    bne @effects
    jsr reset_motion_cache
.ifdef MSU_BUILD
    jsr restore_pattern_cache
.endif
    lda step
    jsr floor_position
    lda floor_x
    sec
.ifdef MSU_BUILD
    sbc #128
.else
    sbc #96
.endif
    sta cam_x
    lda floor_y
    sec
.ifdef MSU_BUILD
    sbc #96
.else
    sbc #116
.endif
    sta cam_y
.ifdef MSU_BUILD
    lda tick
    sta f:CAMERA_FOLLOW_TICK
.endif
    lda #$FFFF
    sta map_last_x
    sta map_last_y
    sta hud_state
    lda #5460
    sta packets_left
    jsr stream_packets
    jsr restore_checkpoint_stats
    lda #1
    sta state
    jsr draw_hud
    jsr render
    jsr build_track_view
    lda #1
    sta frame_ready
@sync:
    lda frame_ready
    bne @sync
.ifdef MSU_BUILD
    lda pattern_blanked
    beq @audio_start
    sep #$20
    .a8
    lda #$0F
    sta $2100
    rep #$20
    .a16
    stz pattern_blanked
@audio_start:
.endif
    ; Arm the SPC before starting its clock. Rendering cannot postpone or
    ; bunch up the four audible clicks; the main loop only tracks UI state.
    lda checkpoint_beat
    jsr checkpoint_audio_ticks
    sta $2141
    lda #$8D
    jsr spc_command
    lda checkpoint_click_next
    sec
    sbc music_origin
    bpl :+
    lda #0
:
    jsr checkpoint_audio_ticks
    sta $2141
    sep #$20
    .a8
    lda #4
    sta $2143
    rep #$20
    .a16
    lda #$8E
    jsr spc_command
    lda #$85
    jsr spc_command
    lda #1
    sta music_active
    rts

; Convert chart frames to real SPC timer ticks, rounded to the nearest tick.
; speed_scale is chart frames per 250-Hz tick in unsigned 16.16 format.
checkpoint_audio_ticks:
    sta math_hi
    lda speed_scale
    sta math_b
    lsr a
    sta math_lo
    jsr divide32
    lda math_lo
    bne :+
    inc a
:
    rts

; Music-clock scheduling also resumes correctly after pausing the count-in.
update_checkpoint_clicks:
    lda checkpoint_clicks_left
    beq @done
    ; Audible cues belong to the uncalibrated song timeline. Calibration
    ; shifts judgments/visual anticipation, never the sound itself.
    lda elapsed
    cmp checkpoint_click_next
    bcc @done
    dec checkpoint_clicks_left
    lda checkpoint_click_next
    clc
    adc checkpoint_beat
    sta checkpoint_click_next
@done:
    rts

set_difficulty:
    lda difficulty
    asl a
    tax
    lda timing_windows,x
    sta hit_window_real
    dec a
    jsr scale_window
    inc a
    sta hit_window
    lda hit_window_real
    inc a
    jsr scale_window
    inc a
    sta rough_window
    rts
scale_window:
    sep #$20
    .a8
    sta $4202
    lda speed_tenths
    sta $4203
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4216
    sta $4204
    sep #$20
    .a8
    lda #10
    sta $4206
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4214
    rts

; Original fail-bar constants: half a bar per error, cooling by 0.4 per
; base musical beat. Use song-frame deltas so rendering load cannot alter it.
cool_overload:
    lda chart_time
    sec
    sbc overload_last
    sta scratch
    lda chart_time
    sta overload_last
    lda scratch
    beq @done
    bmi @done
@frame:
    lda overload_phase
    clc
    adc #102
    sta overload_phase
    dec scratch
    bne @frame
@cool:
    lda overload_phase
    cmp beat_frames
    bcc @done
    sec
    sbc beat_frames
    sta overload_phase
    lda overload
    beq @cool
    dec overload
    bra @cool
@done:
    rts

charge_overload:
    lda overload
    clc
    adc #128
    sta overload
    cmp #257
    bcc @survived
    lda practice
    bne @practice
    sec
    rts
@practice:
    lda #256
    sta overload
@survived:
    clc
    rts

best_score_index:
    stz scratch
    ldx difficulty
@mode:
    cpx #0
    beq @level
    lda scratch
    clc
    adc #LEVEL_COUNT*2
    sta scratch
    dex
    bra @mode
@level:
    lda selected_level
    asl a
    clc
    adc scratch
    tax
    rts
