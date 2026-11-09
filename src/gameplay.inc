return_title:
    lda #$80
    jsr spc_command
    lda state
    cmp #7
    beq @keep_mode
    stz autoplay
    stz practice
@keep_mode:
    stz state
    stz music_active
    rts

update_title:
    lda pressed
    bit #$8000
    beq @calibrate
.if MENU_SET_COUNT > 1
    lda menu_depth
    beq @options
    stz menu_depth
    lda menu_group
    sta menu_selection
    lda #$FFFF
    sta hud_state
    rts
@options:
.endif
    lda #7
    sta state
    rts
@calibrate:
    stz cal_return
    lda pressed
    bit #SELECT
    beq @up
    jmp start_calibration
@up:
    bit #$0800
    beq @down
    lda menu_selection
    bne @previous
    jsr menu_item_count
    sta menu_selection
@previous:
    dec menu_selection
    jsr menu_sync_song
    lda #$FFFF
    sta hud_state
@down:
    lda pressed
    bit #$0400
    beq @left
    inc menu_selection
    jsr menu_item_count
    cmp menu_selection
    bne @changed
    stz menu_selection
@changed:
    jsr menu_sync_song
    lda #$FFFF
    sta hud_state
@left:
    lda pressed
    bit #$0200
    beq @right
    lda calibration
    cmp #.loword(-CALIBRATION_LIMIT)
    beq @right
    dec calibration
@right:
    lda pressed
    bit #$0100
    beq @mode
    lda calibration
    cmp #CALIBRATION_LIMIT
    beq @mode
    inc calibration
@mode:
    lda pressed
    bit #$0020
    beq @faster
    lda speed_tenths
    cmp #5
    beq @faster
    dec speed_tenths
    jsr prepare_speed
@faster:
    lda pressed
    bit #$0010
    beq @start_mode
    lda speed_tenths
    cmp #40
    beq @start_mode
    inc speed_tenths
    jsr prepare_speed
@start_mode:
    lda pressed
    bit #$4000
    beq @practice
    stz practice
    lda autoplay
    eor #1
    sta autoplay
@practice:
    lda pressed
    bit #$0040
    beq @normal
    stz autoplay
    lda practice
    eor #1
    sta practice
@normal:
    lda pressed
    bit #START
    beq @done
    lda menu_depth
    bne @play
    lda menu_selection
    sta menu_group
    stz menu_selection
    inc menu_depth
    jsr menu_sync_song
    lda #$FFFF
    sta hud_state
    rts
@play:
    jmp start_game
@done:
    rts

init_menu:
    stz menu_group
    stz menu_selection
.if MENU_SET_COUNT = 1
    lda #1
    sta menu_depth
.else
    stz menu_depth
.endif
    jmp menu_sync_song

menu_item_count:
    lda menu_depth
    bne @songs
    lda #MENU_SET_COUNT
    rts
@songs:
    lda menu_group
    asl a
    tax
    lda menu_set_counts,x
    rts

; A is a row within the current set. Return the actual chart index.
menu_song_index:
    asl a
    pha
    lda menu_group
    asl a
    tax
    pla
    clc
    adc menu_set_starts,x
    tax
    lda menu_level_indices,x
    rts

menu_sync_song:
    lda menu_depth
    beq @done
    lda menu_selection
    jsr menu_song_index
    sta selected_level
@done:
    rts

menu_title_pointer:
    pha
    lda menu_depth
    bne @song
    pla
    asl a
    tax
    lda menu_set_name_ptrs,x
    rts
@song:
    pla
    jsr menu_song_index
    asl a
    tax
    lda level_title_pointers,x
    rts

update_game:
    lda pressed
    bit #SELECT
    beq @pause
    jmp start_game
@pause:
    bit #START
    beq @run
    lda #$82
    jsr spc_command
    lda #4
    sta state
    rts
@run:
    jsr read_audio_clock
    ; One corrected musical clock for judgment, orbit, and count-in. Keep
    ; elapsed raw for streaming/song-tail control and emulator diagnostics.
    jsr get_chart_time
    jsr update_checkpoint_clicks
    jsr cool_overload
    jsr stream_frame
    lda checkpoint_flash
    beq @preroll
    dec checkpoint_flash
@preroll:
    lda checkpoint_preroll
    beq @feedback_clock
    lda chart_time
    cmp checkpoint_ready
    bcc @fade
    stz checkpoint_preroll
    lda #112
    bra @volume
@fade:
    ; Keep the backing track below the count-in, including its final click.
    ; Normal music level returns when the checkpoint becomes playable.
    lda elapsed
    sec
    sbc music_origin
    asl a
    cmp #56
    bcc @volume
    lda #56
@volume:
.ifdef MSU_BUILD
    sta msu_volume
.endif
    sep #$20
    .a8
    sta $2141
    rep #$20
    .a16
    lda #$86
    jsr spc_command
    lda checkpoint_preroll
    beq @feedback_clock
    rts
@feedback_clock:
    lda feedback_time
    beq @timing
    dec feedback_time
@timing:
    jsr pop_tap
@next_note:
.ifdef MSU_BUILD
    jsr prepare_note_margin
.endif
    lda step
    inc a
    asl a
    tax
    lda tap_clock
    sec
    sbc f:NOTE_TIME,x
    sta timing_error
    lda step
    inc a
    tax
    lda f:NOTE_FLAGS,x
    and #8
    beq @manual
    lda timing_error
    bpl @automatic
    lda pressed
    and #TAP_MASK
    jeq @done
.ifdef MSU_BUILD
    lda input_rough_window
.else
    lda rough_window
.endif
    dec a
    eor #$FFFF
    inc a
    sta scratch
    lda timing_error
    cmp scratch
    bcc @human
@automatic:
    ; Midspin/automatic floors consume no tap and add no score. A press
    ; within the window remains available for the real landing after it.
    inc step
    jsr activate_checkpoint
    lda step
    cmp last_note
    bcc @next_note
    jmp finish_run
@manual:
    lda autoplay
    beq @human
    lda timing_error
    bpl :+
    jmp @done
:
    stz timing_error
    jsr hit
    lda state
    cmp #1
    jne @done
    jmp @timing
@human:
    lda step
    asl a
    tax
    lda f:NOTE_PAUSE,x
    beq @input
    clc
    adc f:NOTE_TIME,x
    cmp tap_clock
    bcc @input
    rts
@input:
    lda pressed
    and #TAP_MASK
    beq @late
    lda step
    bne @judge
    lda first_hit
    sec
    sbc #9
    cmp tap_clock
    bcs @done
@judge:
    lda timing_error
    bpl @positive
    eor #$FFFF
    inc a
@positive:
.ifdef MSU_BUILD
    cmp input_rough_window
.else
    cmp rough_window
.endif
    bcs @bad_tap
    jsr hit
    lda state
    cmp #1
    jne @done
    jmp @timing
@bad_tap:
    lda timing_error
    bmi @early_fail
    bra @late_fail
@early_fail:
    stz fail_reason
    jsr charge_overload
    bcs @overload_fail
    lda #0
    jsr record_judgment
    lda timing_error
    sta last_error
    lda #20
    sta feedback_time
    rts
@overload_fail:
    lda #2
    sta fail_reason
    jmp fail
@late:
    lda timing_error
    bmi @done
.ifdef MSU_BUILD
    cmp input_rough_window
.else
    cmp rough_window
.endif
    bcc @done
@late_fail:
    lda #1
    sta fail_reason
    lda practice
    beq @fail
    inc misses
    stz combo
    lda timing_error
    sta last_error
    lda #9
    jsr record_judgment
    lda #24
    sta feedback_time
    jmp advance
@fail:
    jmp fail
@done:
    rts

hit:
    jsr classify_hit
    sta last_judgment
    ; Counted Early/Late landings succeed in the original game. Only
    ; unmatched extra taps charge the overload bar.
@accepted:
    lda step
    inc a
    and #7
    asl a
    tax
    lda chart_time
    inc a
    sta HIT_TIMES,x
    lda timing_error
    sta last_error
    jsr meter_add_hit
    inc combo
    lda autoplay
    bne @grade
    lda combo
    cmp best
    bcc @grade
    sta best
    pha
    jsr best_score_index
    pla
    sta BEST_SCORES,x
@grade:
    lda last_judgment
    jsr record_judgment
advance:
    inc step
    jsr activate_checkpoint
    lda step
    cmp last_note
    bcc @done
    jmp finish_run
@done:
    rts
fail:
    inc misses
    lda run_centis
    sta finish_cs
    lda fail_reason
    cmp #2
    beq @overload
    lda pressed
    and #TAP_MASK
    beq @miss
    lda #8
    bra @record
@overload:
    lda #10
    bra @record
@miss:
    lda #9
@record:
    jsr record_judgment
    lda #2
    sta state
    lda #$82
    jsr spc_command
    stz music_active
    rts

update_tail:
    lda music_active
    beq @done
    jsr read_audio_clock
    lda elapsed
    cmp song_end
    bcc @stream
    lda #$82
    jsr spc_command
    stz music_active
@done:
    rts
@stream:
    jmp stream_frame

start_calibration:
    jsr reset_clock
    stz music_origin
    lda #$80
    jsr spc_command
    stz cal_count
    stz cal_sum
    stz cal_recommend
    stz cal_phase
    stz cal_error
    stz feedback_time
    stz elapsed
    lda #$FFFF
    sta cal_last_beat
.ifdef MSU_BUILD
    lda calibration
    clc
    adc #CALIBRATION_LIMIT
    asl a
    tax
    lda calibration_centers,x
    sta f:CALIBRATION_CENTER
.endif
    lda #5
    sta state
    lda #$84
    jsr spc_command
    lda #1
    sta music_active
    rts

; Use the same input-poll timestamps as gameplay and the original 120-BPM
; click. Resolve the nearest beat around the current offset setting.
update_calibration:
    lda pressed
    bit #SELECT
    beq @retry
    jmp return_calibration
@retry:
    bit #START
    beq @run
    jmp start_calibration
@run:
    jsr read_audio_clock
    lda feedback_time
    beq @measure
    dec feedback_time
@measure:
.ifdef MSU_BUILD
    ldx tap_tail
    cpx tap_head
    jeq @done
    lda tap_stamps,x
    sta cal_phase
    lda tap_buttons,x
    sta scratch2
    dec a
    and scratch2
    sta tap_buttons,x
    bne @tap_ready
    txa
    clc
    adc #2
    and #TAP_QUEUE_MASK
    sta tap_tail
@tap_ready:
.else
    lda audio_ticks
    sta cal_phase
.endif
    stz cal_beat
@divide:
    lda cal_phase
    cmp #CALIBRATION_PERIOD
    bcc @phase
    sec
    sbc #CALIBRATION_PERIOD
    sta cal_phase
    inc cal_beat
    bra @divide
@phase:
.ifndef MSU_BUILD
    lda pressed
    and #TAP_MASK
    beq @done
.endif
    lda cal_phase
.ifdef MSU_BUILD
    ; Keep the full manual range. Fast calibration refines the existing
    ; offset instead of jumping to another equivalent half-second beat.
    sec
    sbc f:CALIBRATION_CENTER
@positive_phase:
    bpl @relative_phase
    clc
    adc #CALIBRATION_PERIOD
    bra @positive_phase
@relative_phase:
    cmp #CALIBRATION_PERIOD
    bcc @normalized_phase
    sec
    sbc #CALIBRATION_PERIOD
    bra @relative_phase
@normalized_phase:
.endif
    cmp #CALIBRATION_HALF
    bcc @nearest
    sec
    sbc #CALIBRATION_PERIOD
    inc cal_beat
@nearest:
.ifdef MSU_BUILD
    clc
    adc f:CALIBRATION_CENTER
    sec
    sbc #33
.endif
    sta cal_error
    lda #8
    sta feedback_time
    lda cal_error
    clc
    adc cal_sum
    sta cal_sum
.ifdef MSU_BUILD
    lda cal_count
    asl a
    tax
    lda cal_error
    clc
    adc #256
    sta f:CALIBRATION_SAMPLES,x
.endif
    inc cal_count
    lda cal_count
    cmp #16
    bcs @complete
.ifdef MSU_BUILD
    jmp @measure
.else
    rts
.endif
@complete:
.ifdef MSU_BUILD
    jsr trim_calibration_samples
    lda cal_sum
    .repeat 2
    cmp #$8000
    ror a
    .endrepeat
.else
    lda cal_sum
.endif
    clc
    adc #CALIBRATION_RESULT_BIAS
    tax
    lda cal_results,x
    and #$FF
    cmp #128
    bcc @result
    ora #$FF00
@result:
    sta cal_recommend
    lda #$80
    jsr spc_command
    stz music_active
    lda #6
    sta state
@done:
    rts

update_cal_result:
    lda pressed
    bit #SELECT
    beq @retry
    jmp return_calibration
@retry:
    bit #$0040
    beq @left
    jmp start_calibration
@left:
    bit #$0200
    beq @right
    lda cal_recommend
    cmp #.loword(-CALIBRATION_LIMIT)
    beq @right
    dec cal_recommend
@right:
    lda pressed
    bit #$0100
    beq @apply
    lda cal_recommend
    cmp #CALIBRATION_LIMIT
    beq @apply
    inc cal_recommend
@apply:
    lda pressed
    bit #$1080
    beq @done
    lda cal_recommend
    sta calibration
    jmp return_calibration
@done:
    rts

.ifdef MSU_BUILD
; Drop the two earliest and two latest of sixteen acknowledged taps. One
; startup transient or stray tap must not pull the whole recommendation.
trim_calibration_samples:
    ldy #30
@pass:
    ldx #0
@pair:
    lda f:CALIBRATION_SAMPLES,x
    cmp f:CALIBRATION_SAMPLES+2,x
    bcc @ordered
    pha
    lda f:CALIBRATION_SAMPLES+2,x
    sta f:CALIBRATION_SAMPLES,x
    pla
    sta f:CALIBRATION_SAMPLES+2,x
@ordered:
    inx
    inx
    sty scratch2
    cpx scratch2
    bcc @pair
    dey
    dey
    bne @pass
    stz cal_sum
    ldx #4
@sum:
    lda f:CALIBRATION_SAMPLES,x
    sec
    sbc #256
    clc
    adc cal_sum
    sta cal_sum
    inx
    inx
    cpx #28
    bcc @sum
    rts
.endif
