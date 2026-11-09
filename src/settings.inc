prepare_speed:
    lda speed_tenths
    sec
    sbc #5
    asl a
    tax
    lda speed_pitches,x
    sta speed_pitch
    asl a
    clc
    adc speed_pitch
    sta speed_stream
.ifdef FAST_AUDIO_BUILD
    lda audio_speed_streams,x
    sta speed_stream
.endif
    lda speed_scales,x
    sta speed_scale
    ; Calculate the signed 16.16 calibration offset instead of storing a
    ; large speed-by-calibration table in the executable ROM bank.
    lda calibration
.ifdef MSU_BUILD
    clc
    adc #8
.endif
    pha
    bpl :+
    eor #$FFFF
    inc a
:
    sta math_a
    lda speed_pitch
    sta math_b
    jsr multiply_points
    lda #1536
    sta math_b
    jsr divide32
    lda math_lo
    sta speed_offset
    lda math_rem
    sta math_hi
    lda #768
    sta math_lo
    jsr divide32
    lda math_lo
    sta speed_offset_frac
    pla
    bpl :+
    lda #0
    sec
    sbc speed_offset_frac
    sta speed_offset_frac
    lda #0
    sbc speed_offset
    sta speed_offset
:
    jmp set_difficulty

apply_audio_speed:
.ifdef FAST_AUDIO_BUILD
    lda speed_tenths
    sec
    sbc #5
    asl a
    tax
    lda audio_speed_pitches,x
.else
    lda speed_pitch
.endif
    sta $2141
    lda #$87
    jmp spc_command

update_orb_colors:
    lda fire_color
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
@fire:
    lda orb_colors,x
    sta orb_palette,y
    inx
    inx
    iny
    iny
    cpy #32
    bne @fire
    lda ice_color
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
@ice:
    lda orb_colors,x
    sta orb_palette,y
    inx
    inx
    iny
    iny
    cpy #64
    bne @ice
    lda #1
    sta palette_dirty
    rts

update_settings:
    lda pressed
    bit #$B000
    beq @up
    jmp return_title
@up:
    bit #$0800
    beq @down
    lda settings_row
    bne @previous
    lda #6
    sta settings_row
@previous:
    dec settings_row
@down:
    lda pressed
    bit #$0400
    beq @adjust
    inc settings_row
    lda settings_row
    cmp #6
    bcc @adjust
    stz settings_row
@adjust:
    lda #1
    sta scratch2
    lda pressed
    bit #$0220
    beq @right
    lda #$FFFF
    sta scratch2
    bra @change
@right:
    bit #$0110
    bne @change
    bit #$0080
    jeq @done
    lda settings_row
    cmp #5
    bne @change
    lda #7
    sta cal_return
    jmp start_calibration
@change:
    lda settings_row
    bne @speed
    lda time_attack
    eor #1
    sta time_attack
    rts
@speed:
    cmp #1
    bne @timing
    lda speed_tenths
    clc
    adc scratch2
    cmp #5
    bcc @done
    cmp #41
    bcs @done
    sta speed_tenths
    jmp prepare_speed
@timing:
    cmp #2
    bne @colors
    lda difficulty
    clc
    adc scratch2
    bpl @difficulty_positive
    lda #2
@difficulty_positive:
    cmp #3
    bcc @difficulty_set
    lda #0
@difficulty_set:
    sta difficulty
    jmp set_difficulty
@colors:
    cmp #5
    beq @offset
    cmp #3
    bne @ice
    lda fire_color
    clc
    adc scratch2
    and #7
    sta fire_color
    jmp update_orb_colors
@ice:
    lda ice_color
    clc
    adc scratch2
    and #7
    sta ice_color
    jmp update_orb_colors
@offset:
    lda calibration
    clc
    adc scratch2
    cmp #.loword(-CALIBRATION_LIMIT)
    bcs @offset_set
    cmp #CALIBRATION_LIMIT+1
    bcs @done
@offset_set:
    sta calibration
    jmp prepare_speed
@done:
    rts

draw_settings:
    ldx #0
    lda #0
@clear_arrows:
    sta HUD+6*64+2,x
    txa
    clc
    adc #128
    tax
    lda #0
    cpx #768
    bcc @clear_arrows
    lda settings_row
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    clc
    adc #6*64+2
    tay
    lda #'>'|$3C00
    sta HUD,y
    lda time_attack
    beq @off
    lda #.loword(text_on)
    bra @time
@off:
    lda #.loword(text_off)
@time:
    ldy #6*64+23*2
    jsr put_text
    lda speed_tenths
    ldy #8*64+23*2
    jsr put_speed
    lda difficulty
    asl a
    tax
    lda difficulty_text,x
    ldy #10*64+23*2
    jsr put_text
    lda fire_color
    asl a
    tax
    lda color_pointers,x
    ldy #12*64+23*2
    jsr put_text
    lda ice_color
    asl a
    tax
    lda color_pointers,x
    ldy #14*64+23*2
    jsr put_text
    lda calibration
    ldy #16*64+23*2
    jmp put_offset

put_speed:
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
    jsr put_digit
    lda #'.'|$3C00
    sta HUD,y
    iny
    iny
    pla
    jsr put_digit
    lda #'X'|$3C00
    sta HUD,y
    rts

return_calibration:
    lda #$80
    jsr spc_command
    stz music_active
    lda cal_return
    sta state
    lda #$FFFF
    sta hud_state
    jmp prepare_speed

.segment "RODATA"
text_on: .byte "ON ",0
text_off: .byte "OFF",0
text_time_attack: .byte "TIME ATTACK",0
.segment "CODE"
