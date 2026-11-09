; Straight hit-error meter: recent ticks, centered perfect line, moving mean.
; Positions are normalized to the current counted timing window.
meter_add_hit:
    lda #64
    ldx autoplay
    bne @position
    lda judge_signed
    bpl :+
    eor #$FFFF
    inc a
:
    ; classify_hit retained the signed sub-frame input phase in 8.8.
    ; Divide by four to obtain error * 64 without losing whole frames.
    lsr a
    lsr a
    sta $4204
    sep #$20
    .a8
.ifdef MSU_BUILD
    lda input_rough_window
.else
    lda rough_window
.endif
    bne :+
    inc a
:
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
    cmp #65
    bcc :+
    lda #64
:
    ldx judge_signed
    bpl :+
    eor #$FFFF
    inc a
:
    clc
    adc #64
@position:
    ldx meter_head
    sta meter_positions,x
    sta scratch
    lda tick
    sta meter_times,x
    lda last_judgment
    sta meter_grades,x
    txa
    clc
    adc #2
    and #31
    sta meter_head
    lda meter_count
    cmp #16
    bcs :+
    inc meter_count
:
    ; Vanilla smooths its average with sensitivity 0.2.
    lda meter_average
    asl a
    asl a
    clc
    adc scratch
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
    lda $4214
    sta meter_average
    rts

draw_hit_meter:
    lda meter_count
    beq @background
    lda meter_head
    dec a
    dec a
    and #31
    tax
    lda tick
    sec
    sbc meter_times,x
    cmp #180
    bcc @background
    stz meter_count
@background:
    ldx #0
@bar:
    lda meter_bar,x
    sta HUD+24*64+7*2,x
    lda #0
    sta HUD+25*64+7*2,x
    inx
    inx
    cpx #34
    bne @bar
    lda meter_count
    beq @done
    sta digit
    asl a
    sta scratch
    lda meter_head
    sec
    sbc scratch
    and #31
    sta number
@tick:
    ldx number
    lda tick
    sec
    sbc meter_times,x
    cmp #180
    bcs @next
    pha
    lda meter_grades,x
    asl a
    tay
    lda meter_colors,y
    sta scratch2
    pla
    cmp #120
    bcc :+
    lda #$3000
    sta scratch2
:
    lda meter_positions,x
    jsr meter_column
    and #7
    clc
    adc #8
    ora scratch2
    sta HUD+24*64+7*2,y
@next:
    lda number
    inc a
    inc a
    and #31
    sta number
    dec digit
    bne @tick
    lda meter_average
    jsr meter_column
    and #7
    clc
    adc #16
    ora #$3C00
    sta HUD+25*64+7*2,y
@done:
    rts
meter_column:
    pha
    lsr a
    lsr a
    lsr a
    asl a
    tay
    pla
    rts
meter_bar:
    .word $3003,$3003,$3003,$3403,$3403,$3403,$3C03,$3C03,$3C04
    .word $3C03,$3C03,$3403,$3403,$3403,$3003,$3003,$3003
meter_colors:
    .word $3800,$3800,$3400,$3C00,$3C00,$3C00,$3400,$3800,$3800,$3000,$3000
