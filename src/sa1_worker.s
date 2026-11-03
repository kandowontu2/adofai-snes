; Executed by the cartridge's SA-1, with its own stack and temporary state.
SA1_WORKER=1
.include "sa1_layout.inc"
.include "sa1_symbols.inc"
.segment "CODE"
.a16
.i16
    jmp worker_reset
    jmp worker_irq
worker_reset:
    sei
    clc
    xce
    sep #$20
    .a8
    lda #$80
    sta f:$002227
    sta f:$00220A
    lda #$FF
    sta f:$00222A
    lda #0
    sta f:$002225
    sta f:$002250
    rep #$30
    .a16
    ldx #$07FF
    txs
    lda #0
    tcd
    pea $4040
    plb
    plb
    lda #1
    sta f:$400002
worker_wait:
    cli
    wai
    bra worker_wait
worker_irq:
    sei
    rep #$30
    .a16
    .i16
    ldx #$07FF
    txs
    lda f:$400000
    pha
    lda #0
    sta f:$400000
    sep #$20
    .a8
    lda #$80
    sta f:$00220B
    rep #$20
    .a16
    pla
    cmp #2
    beq @project
    cmp #3
    beq @commit
    jsr mode7_cache_prepare
    bra @complete
@commit:
    jsr mode7_cache_commit
    bra @complete
@project:
    jsr worker_project
@complete:
    lda f:$400008
    inc a
    sta f:$400008
    lda #1
    sta f:$400002
    bra worker_wait

audio_pump:
mode7_game_service:
mode7_visible_patterns:
    rts
mode7_floor8:
    .repeat 3
    cmp #$8000
    ror a
    .endrepeat
    rts
mode7_pattern_destination:
    cmp #224
    bcs @high
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    rts
@high:
    sec
    sbc #224
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_CHR_HIGH)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    rts
.include "mode7_cache.inc"

; Four signed multiplications on SA-1 replace the SNES's byte products.
; Projection jobs finish before the map job starts, so the arithmetic
; unit and these shared inputs have one owner at a time.
worker_project:
    lda f:M7_PROJECT_COS
    tax
    lda f:ROT_X
    jsr worker_multiply
    sta f:ROT_SUM
    lda f:M7_PROJECT_SIN
    tax
    lda f:ROT_Y
    jsr worker_multiply
    eor #$FFFF
    inc a
    clc
    adc f:ROT_SUM
    sta f:$40002C
    lda f:ROT_X
    jsr worker_multiply
    sta f:ROT_SUM
    lda f:M7_PROJECT_COS
    tax
    lda f:ROT_Y
    jsr worker_multiply
    clc
    adc f:ROT_SUM
    sta f:$40002E
    rts
worker_multiply:
    sta f:$002251
    txa
    sta f:$002253
    nop
    nop
    sep #$20
    .a8
    lda f:$002306
    clc
    adc #128
    rep #$20
    .a16
    lda f:$002307
    adc #0
    rts
