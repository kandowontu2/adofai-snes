reset_clock:
    stz note_taps
.ifdef NEO_BUILD
    stz neo_hold_keys
    jsr neo_reset_free
    stz neo_cam_active
    stz neo_return_until
.endif
    stz meter_dirty
    stz meter_next_tick
    stz meter_bitmap_valid
    stz meter_head
    stz meter_count
    lda #64
    sta meter_average
    lda #0
    stz input_sound_mask
    sta f:SOUND_PENDING
    sta f:SOUND_TICKS
    sta f:SOUND_FRAC
    sta f:SOUND_FRAMES
    sta f:SOUND_NOW
    inc a
    sta f:SOUND_NOTE
.ifdef MSU_BUILD
    stz audio_pending_packets
.endif
    stz nmi_audio_ticks
    stz tap_head
    stz tap_tail
    stz tap_overruns
    stz tap_queue_peak
    stz clock_ticks
    stz clock_song_frac
    stz clock_song_frames
    stz clock_fraction
    stz run_centis
    stz run_cs_frac
    rts
reset_run_stats:
    jsr reset_clock
    stz score_lo
    stz score_hi
    stz finish_cs
    stz result_prepared
    ldx #20
@clear:
    stz judgment_counts,x
    dex
    dex
    bpl @clear
    rts

finish_run:
    lda tap_latency
    asl a
    sta $4204
    sep #$20
    .a8
    lda #5
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
    lda run_centis
    sec
    sbc $4214
    sta finish_cs
    lda #3
    sta state
    rts

; Grade in real 8.8 frames, retaining the SPC clock's sub-frame phase.
classify_hit:
    lda autoplay
    beq @human
    lda #4
    rts
@human:
    lda timing_error
    xba
    and #$FF00
    sta judge_signed
    lda tap_frac
    xba
    and #255
    clc
    adc judge_signed
    sta judge_signed
    lda tap_frac
    bpl @signed
    lda judge_signed
    sec
    sbc #256
    sta judge_signed
@signed:
    lda judge_signed
    bpl @absolute
    eor #$FFFF
    inc a
@absolute:
.ifdef MSU_BUILD
    ldx input_margin
    cpx #100
    beq @margin_done
    sta math_a
    lda #100
    sta math_b
    jsr multiply_points
    lda input_margin
    sta math_b
    jsr divide32
    lda math_lo
@margin_done:
.endif
    sta judge_abs
    asl a
    asl a
    clc
    adc judge_abs
    asl a
    sta $4204
    sep #$20
    .a8
    lda speed_tenths
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
    sta judge_abs
    cmp #257
    bcs @pure
    lda #4
    rts
@pure:
    cmp #385
    bcs @ordinary
    lda #3
    ldx judge_signed
    bmi @done
    lda #5
@done:
    rts
@ordinary:
    lda hit_window_real
    dec a
    xba
    cmp judge_abs
    bcc @rough
    lda #2
    ldx judge_signed
    bmi @done
    lda #6
    rts
@rough:
    lda #1
    ldx judge_signed
    bmi @done
    lda #7
    rts

record_judgment:
    sta last_judgment
    inc a
    sta feedback
    lda #20
    sta feedback_time
    lda last_judgment
    cmp #3
    bcc @count
    cmp #6
    bcs @count
    inc perfects
@count:
    asl a
    tax
    inc judgment_counts,x
    lda judgment_weights,x
    clc
    adc score_lo
    sta score_lo
    bcc @note
    inc score_hi
@note:
    lda last_judgment
    cmp #1
    bcc @done
    cmp #8
    bcs @done
    inc a
    pha
    lda step
    inc a
    tax
    pla
    sep #$20
    .a8
    sta f:NOTE_JUDGMENTS,x
    rep #$20
    .a16
@done:
    rts

save_checkpoint_stats:
    ldx #20
@copy:
    lda judgment_counts,x
    sta checkpoint_counts,x
    dex
    dex
    bpl @copy
    lda score_lo
    sta checkpoint_score_lo
    lda score_hi
    sta checkpoint_score_hi
    lda step
    sta checkpoint_rewind
@rewind:
    lda checkpoint_floor
    cmp checkpoint_rewind
    bcs @done
    ldx checkpoint_rewind
    lda f:NOTE_JUDGMENTS,x
    and #255
    beq @previous
    dec a
    asl a
    tax
    dec checkpoint_counts,x
    lda checkpoint_score_lo
    sec
    sbc judgment_weights,x
    sta checkpoint_score_lo
    bcs @previous
    dec checkpoint_score_hi
@previous:
    dec checkpoint_rewind
    bra @rewind
@done:
    rts

restore_checkpoint_stats:
    ldx #20
@copy:
    lda checkpoint_counts,x
    sta judgment_counts,x
    dex
    dex
    bpl @copy
    lda checkpoint_score_lo
    sta score_lo
    lda checkpoint_score_hi
    sta score_hi
    lda judgment_counts+6
    clc
    adc judgment_counts+8
    adc judgment_counts+10
    sta perfects
    rts

update_statistics:
    lda pressed
    bit #SELECT
    beq @back
    jmp return_title
@back:
@retry:
    bit #START
    beq @done
    lda #2
    sta state
    jmp retry_game
@done:
    rts

draw_results:
    stz result_i
    stz result_total
    lda #6*64
    sta result_row
@judgment:
    lda result_i
    asl a
    tax
    lda judgment_names,x
    ldy result_row
    iny
    iny
    jsr put_text
    lda result_i
    asl a
    tax
    lda judgment_counts,x
    clc
    adc result_total
    sta result_total
    lda judgment_counts,x
    sta math_a
    lda judgment_weights,x
    sta math_b
    lda judgment_counts,x
    ldy result_row
    tya
    clc
    adc #16*2
    tay
    lda math_a
    jsr put4
    jsr multiply_points
    lda result_row
    clc
    adc #23*2
    tay
    jsr put6
    lda result_row
    clc
    adc #64
    sta result_row
    inc result_i
    lda result_i
    cmp #11
    bcc @judgment
    lda score_lo
    sta math_lo
    lda score_hi
    sta math_hi
    ldy #18*64+22*2
    jsr put6
    stz math_lo
    stz math_hi
    ldx #100
@percent:
    lda math_lo
    clc
    adc score_lo
    sta math_lo
    lda math_hi
    adc score_hi
    sta math_hi
    dex
    bne @percent
    lda result_total
    bne @divide
    inc a
@divide:
    sta math_b
    jsr divide32
    lda math_lo
    sta $4204
    sep #$20
    .a8
    lda #100
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
    lda $4216
    sta math_a
    lda $4214
    ldy #20*64+22*2
    jsr put3
    lda #'.'|$3C00
    sta HUD,y
    iny
    iny
    lda math_a
    jsr put2
    lda #'%'|$3C00
    sta HUD,y
    lda speed_tenths
    ldy #22*64+25*2
    jsr put_speed
    lda autoplay
    beq @practice
    lda #.loword(text_auto)
    bra @mode
@practice:
    lda practice
    beq @attack
    lda #.loword(text_practice)
    bra @mode
@attack:
    lda time_attack
    beq @checkpoint
    lda #.loword(text_time_attack)
    bra @mode
@checkpoint:
    lda #.loword(text_checkpoints_used)
    ldy #23*64+3*2
    jsr put_text
    lda checkpoints_used
    ldy #23*64+24*2
    jsr put3
    rts
@mode:
    ldy #3*64+8*2
    jsr put_text
@done:
    rts

multiply_points:
    stz math_lo
    stz math_hi
    stz math_rem
    ldx #16
@bit:
    lsr math_a
    bcc @shift
    lda math_lo
    clc
    adc math_b
    sta math_lo
    lda math_hi
    adc math_rem
    sta math_hi
@shift:
    asl math_b
    rol math_rem
    dex
    bne @bit
    rts

divide32:
    stz math_rem
    ldx #32
@bit:
    asl math_lo
    rol math_hi
    rol math_rem
    lda math_rem
    cmp math_b
    bcc @next
    sec
    sbc math_b
    sta math_rem
    inc math_lo
@next:
    dex
    bne @bit
    rts

put6:
    stz math_index
@place:
    stz digit
    ldx math_index
@subtract:
    lda math_hi
    cmp decimal_hi,x
    bcc @write
    bne @enough
    lda math_lo
    cmp decimal_lo,x
    bcc @write
@enough:
    lda math_lo
    sec
    sbc decimal_lo,x
    sta math_lo
    lda math_hi
    sbc decimal_hi,x
    sta math_hi
    inc digit
    bra @subtract
@write:
    lda digit
    jsr put_digit
    inc math_index
    inc math_index
    lda math_index
    cmp #12
    bcc @place
    rts

put2:
    stz digit
@tens:
    cmp #10
    bcc @write
    sec
    sbc #10
    inc digit
    bra @tens
@write:
    pha
    lda digit
    jsr put_digit
    pla
    jmp put_digit

put_time:
    lda finish_cs
    sta $4204
    sep #$20
    .a8
    lda #100
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
    lda $4216
    sta math_a
    lda $4214
    stz math_b
@minutes:
    cmp #60
    bcc @write
    sec
    sbc #60
    inc math_b
    bra @minutes
@write:
    pha
    lda math_b
    jsr put2
    lda #':'|$3C00
    sta HUD,y
    iny
    iny
    pla
    jsr put2
    lda #'.'|$3C00
    sta HUD,y
    iny
    iny
    lda math_a
    jmp put2
