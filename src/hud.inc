draw_hud:
    lda state
    cmp #1
    jne @refresh
    cmp hud_state
    jne @refresh
    lda step
    jeq @refresh
    cmp hud_last_step
    jne @refresh
    asl a
    tax
    lda f:NOTE_PAUSE,x
.ifdef NEO_BUILD
    and #$3FFF
.endif
    jne @refresh
    lda checkpoint_preroll
    jne @refresh
    lda combo
    cmp hud_last_combo
    jne @refresh
    lda feedback
    cmp hud_last_feedback
    jne @refresh
    lda feedback_time
    beq :+
    lda #1
:
    cmp hud_last_feedback_on
    jne @refresh
    lda checkpoint_flash
    beq :+
    lda #1
:
    cmp hud_last_checkpoint_on
    jne @refresh
    lda overload
    .repeat 6
    lsr a
    .endrepeat
    cmp hud_last_risk
    jne @refresh
    lda last_error
    cmp hud_last_error
    jne @refresh
    lda meter_dirty
    bne @meter_only
    lda meter_count
    beq @unchanged
.ifdef SA1_BUILD
    lda tick
    sec
    sbc meter_next_tick
    bpl @meter_only
.else
    lda tick
    .repeat 4
    lsr a
    .endrepeat
    cmp hud_last_timer
    bne @meter_only
.endif
@unchanged:
    rts
@meter_only:
    ; All displayed counters/feedback above are unchanged. Refresh the
    ; meter at exactly its scheduled fade tick without formatting them again.
    lda #1
    sta hud_dirty
    lda tick
    .repeat 4
    lsr a
    .endrepeat
    sta hud_last_timer
    jmp draw_hit_meter
@refresh:
    lda #1
    sta hud_dirty
    lda step
    sta hud_last_step
    lda combo
    sta hud_last_combo
    lda feedback
    sta hud_last_feedback
    lda feedback_time
    beq :+
    lda #1
:
    sta hud_last_feedback_on
    lda checkpoint_flash
    beq :+
    lda #1
:
    sta hud_last_checkpoint_on
    lda overload
    .repeat 6
    lsr a
    .endrepeat
    sta hud_last_risk
    lda last_error
    sta hud_last_error
    lda tick
    .repeat 4
    lsr a
    .endrepeat
    sta hud_last_timer
    lda state
    cmp hud_state
    jeq @dynamic
.ifdef SA1_BUILD
    lda #1
    sta hud_full_dirty
    lda state
.endif
    sta hud_state
    asl a
    tax
    lda hud_templates,x
    sta text_ptr
    ldx #0
    lda #0
@clear:
    sta HUD,x
    inx
    inx
    cpx #2048
    bne @clear
@record:
    lda (text_ptr)
    cmp #$FFFF
    beq @decoded
    tax
    inc text_ptr
    inc text_ptr
    sep #$20
    .a8
    lda (text_ptr)
    sta hud_decode_attr
    inc text_ptr
    bne :+
    inc text_ptr+1
:
    lda (text_ptr)
    sta hud_decode_count
    inc text_ptr
    bne :+
    inc text_ptr+1
:
@characters:
    lda (text_ptr)
    sta HUD,x
    lda hud_decode_attr
    sta HUD+1,x
    inc text_ptr
    bne :+
    inc text_ptr+1
:
    inx
    inx
    dec hud_decode_count
    bne @characters
    rep #$20
    .a16
    bra @record
@decoded:
    lda state
    bne @static
    jsr draw_menu_list
    jmp @dynamic
@static:
    cmp #7
    jeq draw_settings
    cmp #3
    beq @results
    cmp #8
    bne @regular
@results:
    lda selected_level
    asl a
    tax
    lda level_title_pointers,x
    ldy #2*64+1*2
    jsr put_text
    jmp draw_results
@regular:
    cmp #5
    jeq @dynamic
    cmp #6
    jeq @dynamic
    lda selected_level
    asl a
    tax
    lda level_title_pointers,x
    ldy #1*64+1*2
    jsr put_text
    lda state
    cmp #1
    bne @dynamic
    lda speed_tenths
.ifdef MSU_BUILD
    ldy #26*64+24*2
.else
    ldy #5*64+24*2
.endif
    jsr put_speed
    lda autoplay
    beq @static_practice
    lda #.loword(text_auto)
    bra @static_mode
@static_practice:
    lda practice
    beq @time_attack
    lda #.loword(text_practice)
    bra @static_mode
@time_attack:
    lda time_attack
    beq @dynamic
    lda #.loword(text_time_attack)
@static_mode:
.ifdef MSU_BUILD
    ldy #26*64+3*2
.else
    ldy #5*64+12*2
.endif
    jsr put_text
@dynamic:
    lda state
    cmp #7
    jeq draw_settings
    cmp #3
    beq @results_done
    cmp #8
    bne @other
@results_done:
    rts
@other:
    cmp #0
    jeq @title
    cmp #5
    jeq @calibrate
    cmp #6
    jeq @cal_result
    lda combo
    ldy #3*64+8*2
    jsr put4
    lda best
    ldy #3*64+19*2
    jsr put4
    ldx step
    lda f:NOTE_PROGRESS,x
    and #255
    ldy #3*64+25*2
    jsr put3
    lda state
    cmp #3
    bne @failed
    lda perfects
    ldy #13*64+11*2
    jsr put4
    lda misses
    ldy #13*64+24*2
    jsr put4
    lda autoplay
    bne @demo_clear
    lda checkpoints_used
    jeq @done
    lda #.loword(text_checkpoint_clear)
    ldy #10*64+8*2
    jmp put_text
@demo_clear:
    lda #.loword(text_demo_clear)
    ldy #10*64+8*2
    jmp put_text
@failed:
    cmp #2
    bne @playing
    lda fail_reason
    cmp #2
    beq @overloaded
    lda fail_reason
    bne @late
    lda #.loword(text_too_early)
    bra @reason
@late:
    lda #.loword(text_too_late)
    bra @reason
@overloaded:
    lda #.loword(text_overload)
@reason:
    ldy #22*64+8*2
    jsr put_text
    lda checkpoint_floor
    beq @failure_done
    lda #.loword(text_checkpoint_retry)
    ldy #24*64+2*2
    jsr put_text
@failure_done:
    rts
@playing:
    cmp #4
    jeq @done
@erase_begin:
    ldx #0
    lda #0
@erase:
.ifndef MSU_BUILD
    sta HUD+8*64+10*2,x
    sta HUD+10*64+10*2,x
.endif
    sta HUD+22*64+10*2,x
    inx
    inx
    cpx #24
    bne @erase
@count:
    lda checkpoint_preroll
    jne @count_in
    lda step
    asl a
    tax
    lda f:NOTE_PAUSE,x
.ifdef NEO_BUILD
    and #$3FFF
.endif
    beq @count_in
    clc
    adc f:NOTE_TIME,x
    cmp chart_time
    bcc @count_in
    lda #.loword(text_wait)
.ifdef MSU_BUILD
    ldy #22*64+10*2
.else
    ldy #8*64+10*2
.endif
    jmp put_text
@count_in:
    lda checkpoint_preroll
    beq @initial_count
    lda checkpoint_ready
    bra @ready_time
@initial_count:
    lda step
    bne @feedback
    lda first_hit
@ready_time:
    sec
    sbc chart_time
    bcc @feedback
    beq @feedback
    sta scratch
    lda #.loword(text_ready)
.ifdef MSU_BUILD
    ldy #22*64+10*2
.else
    ldy #8*64+12*2
.endif
    jsr put_text
    lda beat_frames
    ldx checkpoint_preroll
    beq @count_beat
    lda checkpoint_beat
@count_beat:
    sta number
    lda #1
    sta digit
@beat:
    lda scratch
    cmp number
    bcc @count_number
    sec
    sbc number
    sta scratch
    inc digit
    lda digit
    cmp #4
    bcc @beat
@count_number:
    lda digit
    clc
    adc #'0'
    ora #$3C00
.ifdef MSU_BUILD
    sta HUD+22*64+20*2
.else
    sta HUD+10*64+15*2
.endif
    rts
@feedback:
    lda checkpoint_flash
    beq @hit_feedback
    lda #.loword(text_checkpoint)
    ldy #22*64+10*2
    jsr put_text
    bra @meter
@hit_feedback:
    lda feedback_time
    beq @meter
    lda feedback
    dec a
    asl a
    tax
    lda live_judgments,x
    ldy #22*64+10*2
    jsr put_text
@meter:
    jsr draw_hit_meter
@done:
    rts
@title:
    lda menu_selection
    sec
    sbc menu_first
    clc
    adc #6
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    tay
    lda #'>'|$3C00
    sta HUD,y
    iny
    iny
    ldx #30
    sep #$20
    .a8
@highlight:
    lda #$3C
    sta HUD+1,y
    iny
    iny
    dex
    bne @highlight
    rep #$20
    .a16
    lda calibration
    ldy #26*64+12*2
    jsr put_offset
    lda speed_tenths
    ldy #24*64+20*2
    jsr put_speed
    lda #.loword(text_mode_normal)
    ldx autoplay
    beq @mode_practice
    lda #.loword(text_mode_watch)
    bra @mode_show
@mode_practice:
    ldx practice
    beq @mode_show
    lda #.loword(text_mode_practice)
@mode_show:
    ldy #18*64+8*2
    jmp put_text
@calibrate:
    lda cal_count
    ldy #17*64+15*2
    jsr put3
    lda #.loword(text_cal_blank)
    ldy #19*64+10*2
    jsr put_text
    lda feedback_time
    beq @cal_done
    lda #.loword(text_cal_tap)
    ldy #19*64+10*2
    jsr put_text
@cal_done:
    rts
@cal_result:
    lda cal_recommend
    ldy #10*64+11*2
    jmp put_offset

draw_menu_list:
    lda #.loword(menu_root_name)
    ldx menu_depth
    beq @heading
    lda menu_group
    asl a
    tax
    lda menu_set_name_ptrs,x
@heading:
    ldy #3*64+4*2
    jsr put_text
    lda #.loword(menu_open_hint)
    ldx menu_depth
    beq @hint
    lda #.loword(menu_play_hint)
.if MENU_SET_COUNT = 1
    lda #.loword(menu_single_hint)
.endif
@hint:
    ldy #19*64
    jsr put_text
    lda #.loword(menu_controls)
.if MENU_SET_COUNT > 1
    ldx menu_depth
    beq :+
    lda #.loword(menu_back_controls)
:
.endif
    ldy #23*64
    jsr put_text
    lda #.loword(menu_navigation)
    ldy #16*64
    jsr put_text
    stz menu_first
    lda menu_selection
@page:
    cmp #9
    bcc @first
    sec
    sbc #9
    pha
    lda menu_first
    clc
    adc #9
    sta menu_first
    pla
    bra @page
@first:
    lda menu_first
    sta menu_i
    lda #6*64+2*2
    sta menu_row
@line:
    jsr menu_item_count
    cmp menu_i
    beq @done
    bcc @done
    lda menu_i
    jsr menu_title_pointer
    ldy menu_row
    jsr put_text
    lda menu_row
    clc
    adc #64
    sta menu_row
    cmp #15*64+2*2
    bcs @done
    inc menu_i
    bra @line
@done:
    ; Page hints sit outside the nine title rows and their selection cursor.
    lda menu_first
    beq @below
    lda #1|$3C00
    sta HUD+5*64+30*2
@below:
    jsr menu_item_count
    sta scratch
    lda menu_first
    clc
    adc #9
    cmp scratch
    bcs @indicators_done
    lda #2|$3C00
    sta HUD+15*64+30*2
@indicators_done:
    rts

put_text:
.ifdef LEVEL_TITLES_ADDR
    ; Catalog references use $4000+29*index; normal strings remain in ROM.
    cmp #$4000
    bcc @ordinary
    cmp #$4000+LEVEL_COUNT*29
    bcs @ordinary
    sec
    sbc #$4000
    phx
    tax
    sep #$20
    .a8
@title_char:
    lda f:LEVEL_TITLES_ADDR,x
    beq @title_done
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inx
    iny
    iny
    bra @title_char
@title_done:
    rep #$20
    .a16
    plx
    rts
@ordinary:
.endif
    sta text_ptr
    sep #$20
    .a8
@char:
    lda (text_ptr)
    beq @done
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inc text_ptr
    bne @next
    inc text_ptr+1
@next:
    iny
    iny
    bra @char
@done:
    rep #$20
    .a16
    rts
put_offset:
    cmp #0
    bpl @plus
    eor #$FFFF
    inc a
    pha
    lda #'-'|$3800
    sta HUD,y
    pla
    bra @digits
@plus:
    pha
    lda #'+'|$3800
    sta HUD,y
    pla
@digits:
    ldx #0
@tens:
    cmp #10
    bcc @decimal
    sec
    sbc #10
    inx
    bra @tens
@decimal:
    pha
    txa
    clc
    adc #'0'
    ora #$3800
    sta HUD+2,y
    pla
    clc
    adc #'0'
    ora #$3800
    sta HUD+4,y
    rts
put4:
    sta number
    stz digit
@thousands:
    lda number
    cmp #1000
    bcc @th
    sec
    sbc #1000
    sta number
    inc digit
    bra @thousands
@th:
    lda digit
    jsr put_digit
    lda number
put3:
    sta number
    stz digit
@hundreds:
    lda number
    cmp #100
    bcc @h
    sec
    sbc #100
    sta number
    inc digit
    bra @hundreds
@h:
    lda digit
    jsr put_digit
    stz digit
@tens:
    lda number
    cmp #10
    bcc @t
    sec
    sbc #10
    sta number
    inc digit
    bra @tens
@t:
    lda digit
    jsr put_digit
    lda number
put_digit:
    clc
    adc #'0'
    sep #$20
    .a8
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    rep #$20
    .a16
    iny
    iny
    rts

.segment "RODATA"
feedback_text: .word text_empty,text_perfect,text_early,text_late,text_miss,text_very_early,text_very_late
text_empty: .byte 0
text_perfect: .byte "PERFECT",0
text_early: .byte " EARLY ",0
text_late: .byte " LATE  ",0
text_miss: .byte " MISS  ",0
text_ready: .byte "GET READY",0
text_very_early: .byte "VERY EARLY",0
text_very_late: .byte "VERY LATE ",0
text_meter: .byte "--------:--------",0
text_risk: .byte "RISK [----]",0
text_too_early: .byte "   TOO EARLY    ",0
text_too_late: .byte "   TOO LATE     ",0
text_auto: .byte "AUTOPLAY",0
text_practice: .byte "PRACTICE",0
text_demo_clear: .byte "DEMO COMPLETE!  ",0
text_loading: .byte "   LOADING...   ",0
text_cal_tap: .byte "TAP RECEIVED",0,0
text_cal_blank: .byte "            ",0
text_wait: .byte "WAIT FOR IT",0
.segment "CODE"
