.if .defined(SA1_BUILD) .and .defined(NEO_BUILD)
.segment "NEOCODE"
; Coarse eight-line bins can reject a symbol whose actual scanlines fit.
; On that rare path, count exact intervals for OAM and the reserved track.
; Scratch is the unused CPU WRAM below the relocated fast-NMI code.
EXACT_COUNTS=$0620
EXACT_TILES=$06C0
EXACT_Y=$0768
EXACT_HEIGHT=$076A
EXACT_SIZE=$076C
EXACT_START=$076E
EXACT_END=$0770
EXACT_OBJECTS=$0772
EXACT_SLIVERS=$0774
EXACT_LEFT=$0776

sprite_exact_room:
    lda object_small
    jne @no
    lda sprite_attr
    cmp #$32
    jcc @no
    cmp #$37
    jcs @no
    lda sprite_tile
    cmp #32
    jcc @no
    cmp #112
    jcs @no
    phx
    phy
    lda #32
    sta EXACT_Y
    lda #144
    sta EXACT_HEIGHT
    ldx #$140
@clear:
    stz EXACT_COUNTS,x
    dex
    dex
    bpl @clear
    ldx #0
@oam:
    cpx oam_pos
    bcs @reserved
    phx
    txa
    and #12
    lsr a
    tay
    lda xhigh_masks,y
    asl a
    sta EXACT_SIZE
    txa
    .repeat 4
    lsr a
    .endrepeat
    tay
    lda OAM+512,y
    and EXACT_SIZE
    beq @small
    ldy #16
    bra @size_ready
@small:
    ldy #8
@size_ready:
    lda OAM+1,x
    and #255
    jsr sprite_exact_interval
    plx
    inx
    inx
    inx
    inx
    bra @oam
@reserved:
.ifdef SA1_STREAM_BUILD
    lda sprite_limit
    cmp #512
    beq @prefix
    lda f:SPILL_VISIBLE
    sta EXACT_LEFT
    beq @prefix
    ldx #0
@spill:
    phx
    lda f:SPILL_OAM_OUT+1,x
    and #255
    ldy #8
    jsr sprite_exact_interval
    plx
    inx
    inx
    inx
    inx
    dec EXACT_LEFT
    bne @spill
.endif
@prefix:
    ; Include the candidate in the same whole-playfield hardware proof.
    lda sprite_y
    ldy #16
    jsr sprite_exact_interval
    stz EXACT_OBJECTS
    stz EXACT_SLIVERS
    ldx #0
    sep #$20
    .a8
@line:
    lda EXACT_OBJECTS
    clc
    adc EXACT_COUNTS,x
    sta EXACT_OBJECTS
    cmp #33
    bcs @reject
    lda EXACT_SLIVERS
    clc
    adc EXACT_TILES,x
    sta EXACT_SLIVERS
    cmp #35
    bcs @reject
    inx
    cpx #144
    bcc @line
    rep #$20
    .a16
.ifdef SA1_STREAM_BUILD
    lda sprite_limit
    cmp #512
    beq :+
    lda #1
    sta f:STREAM_SPILL_EXACT
:
.endif
    ply
    plx
    sec
    rtl
@reject:
    rep #$20
    .a16
    ply
    plx
@no:
    clc
    rtl

; A=top, Y=size. Difference arrays turn each sprite into two writes;
; one final 16-line prefix scan proves both hardware limits.
sprite_exact_interval:
    sty EXACT_SIZE
    sec
    sbc EXACT_Y
    sta EXACT_START
    clc
    adc EXACT_SIZE
    beq @done
    bmi @done
    cmp EXACT_HEIGHT
    bcc :+
    lda EXACT_HEIGHT
:
    sta EXACT_END
    lda EXACT_START
    bpl :+
    lda #0
:
    cmp EXACT_HEIGHT
    bcs @done
    tax
    sep #$20
    .a8
    lda EXACT_COUNTS,x
    inc a
    sta EXACT_COUNTS,x
    rep #$20
    .a16
    lda EXACT_SIZE
    .repeat 3
    lsr a
    .endrepeat
    sta EXACT_SIZE
    sep #$20
    .a8
    clc
    adc EXACT_TILES,x
    sta EXACT_TILES,x
    rep #$20
    .a16
    ldx EXACT_END
    sep #$20
    .a8
    lda EXACT_COUNTS,x
    dec a
    sta EXACT_COUNTS,x
    lda EXACT_TILES,x
    sec
    sbc EXACT_SIZE
    sta EXACT_TILES,x
    rep #$20
    .a16
@done:
    rts
.segment "CODE"
.endif
