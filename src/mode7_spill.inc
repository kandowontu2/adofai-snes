spill_reset:
    lda #0
    sta f:SPILL_VISIBLE
    sta f:SPILL_COUNT
    sta f:SPILL_TAG_COUNT
.ifdef SA1_STREAM_BUILD
    sta f:STREAM_SPILL_CELLS_COUNT
    sta f:STREAM_SPILL_CHR_BYTES
    sta f:STREAM_SPILL_BUFFER_ID
    sta f:STREAM_SPILL_VRAM_ID
    lda #1
    sta f:STREAM_SPILL_PALETTE_DIRTY
    lda #0
.endif
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
    start_dma 32
    txa
    clc
    adc #6
    tax
    dey
    bne @run
    lda #0
    sta f:SPILL_COUNT
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    beq @done
    lda f:STREAM_SPILL_BUFFER_ID
    sta f:STREAM_SPILL_VRAM_ID
.endif
@done:
    rts

spill_palette:
    jsl spill_palette_far
    rts

.segment "NEOCODE"
spill_palette_far:
    rep #$20
    .a16
    phx
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    beq @ordinary
    lda f:SPILL_VISIBLE
    beq @done
    lda f:STREAM_SPILL_PALETTE_DIRTY
    beq @done
    sep #$20
    .a8
    lda #129
    sta $2121
    lda #0
    sta $4350
    lda #$22
    sta $4351
    lda #^STREAM_SPILL_PALETTE
    sta $4354
    rep #$20
    .a16
    lda #.loword(STREAM_SPILL_PALETTE)
    sta $4352
    lda #30
    sta $4355
    start_dma 32
    lda #0
    sta f:STREAM_SPILL_PALETTE_DIRTY
    bra @done
@ordinary:
.endif
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
    plx
    rtl

.segment "CODE"
spill_draw:
    jmp sa1_draw_spills

; Preserve the essential track's allocation while drawing symbols ahead of
; its OBJ cells. Lines are already clipped and counted by the stream worker.
spill_reserve_symbols:
.ifdef SA1_STREAM_BUILD
    jsl spill_reserve_symbols_long
    bcs @done
.endif
    jmp spill_draw
@done:
    rts

spill_after_symbols:
.ifdef SA1_STREAM_BUILD
    jsl spill_release_symbols_long
    bcc @done
    jmp spill_draw
.endif
@done:
    rts

.ifdef SA1_STREAM_BUILD
.segment "NEOCODE"
spill_reserve_symbols_long:
    lda f:STREAM_ENABLED
    beq @ordinary
    lda f:SPILL_VISIBLE
    beq @done
    asl a
    asl a
    eor #$FFFF
    inc a
    clc
    adc #512
    sta sprite_limit
    ldx #0
    sep #$20
    .a8
@reserve:
    lda SPRITE_BUDGET,x
    clc
    adc f:STREAM_SPILL_LINES,x
    sta SPRITE_BUDGET,x
    inx
    cpx #32
    bcc @reserve
    rep #$20
    .a16
@done:
    sec
    rtl
@ordinary:
    clc
    rtl

spill_release_symbols_long:
    lda #512
    sta sprite_limit
    lda f:STREAM_ENABLED
    beq @done
    lda f:SPILL_VISIBLE
    beq @done
    ldx #0
    sep #$20
    .a8
@release:
    lda SPRITE_BUDGET,x
    sec
    sbc f:STREAM_SPILL_LINES,x
    sta SPRITE_BUDGET,x
    inx
    cpx #32
    bcc @release
    rep #$20
    .a16
    sec
    rtl
@done:
    clc
    rtl
.segment "CODE"
.endif
