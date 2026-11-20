; Live pickup/quiz feedback uses the lower HUD, outside the playfield.
; No question is selected from the prerecorded animation's success route.
OBJECTIVE_HUD_ACTIVE=$079E
.assert OBJECTIVE_HUD_ACTIVE+2 <= $07A0, error, "Objective HUD overlaps planet preview scratch"
.segment "NEOCODE"
.a16
.i16
neo_far_objective_hud:
    phx
    phy
    lda neo_free_mode
    jeq @inactive
    lda neo_free_record
    .repeat 5
    lsr a
    .endrepeat
    tax
    lda f:neo_pickup_ui,x
    jeq @inactive
    sta scratch2
    lda OBJECTIVE_HUD_ACTIVE
    and #1
    bne @clear
    lda #3
    sta OBJECTIVE_HUD_ACTIVE
@clear:
    stz meter_dirty
    stz hud_meter_dirty
    lda #0
    ldx #22*64
@blank:
    sta HUD,x
    inx
    inx
    cpx #26*64
    bcc @blank
    lda scratch2
    cmp #2
    beq @questions
    ldx #neo_objective_help-neo_objective_strings
    ldy #22*64+2
    jsr neo_objective_line
    ldx #neo_objective_counts-neo_objective_strings
    ldy #23*64+2
    jsr neo_objective_line
    ldx #neo_objective_lives-neo_objective_strings
    ldy #24*64+2
    jsr neo_objective_line
    lda neo_pickup_counts
    ldy #23*64+8*2
    jsr neo_objective_number
    lda neo_pickup_counts+2
    ldy #23*64+21*2
    jsr neo_objective_number
    lda neo_pickup_counts+4
    ldy #24*64+9*2
    jsr neo_objective_number
    lda #3
    sec
    sbc neo_pickup_strikes
    bpl :+
    lda #0
:
    ldy #24*64+22*2
    jsr neo_objective_number
    bra @handled
@questions:
    lda neo_free_collected
    cmp #6
    bcc :+
    lda #5
:
    .repeat 5
    asl a
    .endrepeat
    pha
    asl a
    clc
    adc 1,s
    sta scratch
    pla
    lda neo_free_record
    .repeat 5
    lsr a
    .endrepeat
    tax
    lda f:neo_question_text_starts,x
    clc
    adc scratch
    tax
    ldy #22*64
    sep #$20
    .a8
@question_character:
    lda f:neo_question_text,x
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inx
    iny
    iny
    cpy #25*64
    bcc @question_character
    rep #$20
    .a16
    ldx #neo_objective_answered-neo_objective_strings
    ldy #25*64+2
    jsr neo_objective_line
    lda neo_free_collected
    ldy #25*64+11*2
    jsr neo_objective_number
@handled:
    ply
    plx
    sec
    rtl
@inactive:
    lda OBJECTIVE_HUD_ACTIVE
    beq @ordinary
    lda #2
    sta OBJECTIVE_HUD_ACTIVE
    lda #0
    ldx #22*64
@clear_old:
    sta HUD,x
    inx
    inx
    cpx #26*64
    bcc @clear_old
@ordinary:
    ply
    plx
    clc
    rtl

neo_objective_line:
    sep #$20
    .a8
@character:
    lda f:neo_objective_strings,x
    beq @done
    sta HUD,y
    lda #$3C
    sta HUD+1,y
    inx
    iny
    iny
    bra @character
@done:
    rep #$20
    .a16
    rts

neo_objective_number:
    ldx #$3C30
@tens:
    cmp #10
    bcc @digits
    sec
    sbc #10
    inx
    bra @tens
@digits:
    pha
    txa
    sta HUD,y
    pla
    clc
    adc #$3C30
    sta HUD+2,y
    rts
neo_objective_strings:
neo_objective_help: .byte "COLLECT THE REQUESTED AMOUNTS",0
neo_objective_counts: .byte "COINS: 00    STARS: 00",0
neo_objective_lives: .byte "HEARTS: 00    LIVES: 03",0
neo_objective_answered: .byte "ANSWERED: 00/05",0
.segment "CODE"
