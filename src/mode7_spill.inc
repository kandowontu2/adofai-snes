spill_reset:
    lda #0
    sta f:SPILL_VISIBLE
    sta f:SPILL_COUNT
    sta f:SPILL_TAG_COUNT
    ldx #0
@mask:
    sta f:SPILL_OLD,x
    sta f:SPILL_NEW,x
    inx
    inx
    cpx #128
    bcc @mask
    lda #$FFFF
    ldx #0
@tags:
    sta f:SPILL_TAGS,x
    sta f:SPILL_DEADLINES,x
    inx
    inx
    cpx #256
    bcc @tags
    lda #0
    rts

.segment "CODE"
spill_upload:
    lda f:SPILL_COUNT
    jeq @done
    sta f:SPILL_QUEUE_INDEX
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4350
    lda #$18
    sta $4351
    lda #.bankbyte(SPILL_CHR)
    sta $4354
    rep #$20
    .a16
    lda f:SPILL_COUNT
    sta f:SPILL_TAG_COUNT
    lda f:SPILL_RUN_COUNT
    tay
    ldx #0
@run:
    lda f:SPILL_RUNS,x
    sta $2116
    lda f:SPILL_RUNS+2,x
    sta $4352
    lda f:SPILL_RUNS+4,x
    sta $4355
    lda #$C020
    sta $420B
    txa
    clc
    adc #6
    tax
    dey
    bne @run
    lda #0
    sta f:SPILL_COUNT
@done:
    rts

spill_palette:
    lda f:M7_BITMAP_ENABLED
    beq @done
    sep #$20
    .a8
    lda #129
    sta $2121
    rep #$20
    .a16
    lda f:TRACK_PALETTE
    sep #$20
    .a8
    sta $2122
    xba
    sta $2122
    lda #131
    sta $2121
    rep #$20
    .a16
    lda f:TRACK_PALETTE+2
    sep #$20
    .a8
    sta $2122
    xba
    sta $2122
    rep #$20
    .a16
@done:
    rts

.segment "CODE"
spill_draw:
    jmp sa1_draw_spills
