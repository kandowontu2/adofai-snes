.ifdef SA1_BUILD
; Each hit keeps its own timestamp. Coincident marks composite by brightness.
METER_HISTORY=$401000
METER_PIXELS=$401800
METER_LAST_PIXELS=$401840
METER_BITMAP=$7FDE00
METER_CAPACITY=512
METER_BYTES=METER_CAPACITY*4
meter_add_hit:
    lda #64
    ldx autoplay
    bne @position
    lda judge_signed
    bpl :+
    eor #$FFFF
    inc a
:
    lsr a
    lsr a
    sta $4204
    sep #$20
    .a8
    lda input_rough_window
    bne :+
    inc a
:
    sta $4206
    .repeat 8
    nop
    .endrepeat
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
    pha
    ldx meter_count
    beq @uniform
    cmp meter_uniform
    beq @uniform
    lda #$FFFF
@uniform:
    sta meter_uniform
    pla
    sta meter_average ; compatibility label: now the latest hit, not a mean
    ldx meter_head
    sta f:METER_HISTORY,x
    lda tick
    sta f:METER_HISTORY+2,x
    txa
    clc
    adc #4
    and #METER_BYTES-1
    sta meter_head
    lda meter_count
    cmp #METER_CAPACITY
    bcs :+
    inc meter_count
:
    lda #1
    sta meter_dirty
    rts

draw_hit_meter:
    lda meter_dirty
    bne @redraw
    lda tick
    sec
    sbc meter_next_tick
    bpl @redraw
    rts
@redraw:
    ; A fresh coincident hit only renews the already-bright marker. Its
    ; individual record is retained, but no glyph/map work is necessary.
    lda meter_dirty
    beq @compose
    lda meter_bitmap_valid
    beq @compose
    lda meter_uniform_bright
    beq @compose
    lda meter_uniform
    cmp #$FFFF
    beq @compose
    cmp meter_last_uniform
    bne @compose
    lda tick
    sec
    sbc meter_next_tick
    bpl @compose
    stz meter_dirty
    lda tick
    clc
    adc #60
    sta meter_next_tick
    rts
@compose:
    stz meter_uniform_bright
    lda meter_uniform
    sta meter_last_uniform
    stz meter_dirty
    lda tick
    clc
    adc #60
    sta meter_next_tick
    lda meter_count
    asl a
    asl a
    sta scratch
    lda meter_head
    sec
    sbc scratch
    and #METER_BYTES-1
    sta number
@expire:
    lda meter_count
    beq @clear
    ldx number
    lda tick
    sec
    sbc f:METER_HISTORY+2,x
    cmp #180
    bcc @clear
    dec meter_count
    txa
    clc
    adc #4
    and #METER_BYTES-1
    sta number
    bra @expire
@clear:
    ldx #32
    lda #0
:
    sta f:METER_PIXELS,x
    dex
    dex
    bpl :-
    lda meter_count
    sta digit
    jeq @raster
    lda meter_uniform
    cmp #$FFFF
    beq @hit
    ; Coincident ticks are visually covered by the newest one. Keep every
    ; record, but only compose the newest until their positions diverge.
    lda meter_head
    sec
    sbc #4
    and #METER_BYTES-1
    sta number
    lda #1
    sta digit
@hit:
    ldx number
    lda tick
    sec
    sbc f:METER_HISTORY+2,x
    ldy #32
    cmp #60
    bcc @first
    ldy #16
    cmp #120
    bcc @second
    ldy #0
    lda #180
    bra @deadline
@first:
    lda #1
    sta meter_uniform_bright
    lda #60
    bra @deadline
@second:
    lda #120
@deadline:
    clc
    adc f:METER_HISTORY+2,x
    sta scratch
    sec
    sbc meter_next_tick
    bpl :+
    lda scratch
    sta meter_next_tick
:
    lda f:METER_HISTORY,x
    pha
    and #7
    asl a
    tax
    lda meter_erase_masks,x
    sta scratch
    txa
    sty scratch2
    clc
    adc scratch2
    tax
    lda meter_shade_masks,x
    sta scratch2
    pla
    lsr a
    lsr a
    lsr a
    asl a
    tax
    lda f:METER_PIXELS,x
    and scratch
    ora scratch2
    sta f:METER_PIXELS,x
    lda number
    clc
    adc #4
    and #METER_BYTES-1
    sta number
    dec digit
    bne @hit
@raster:
    ; One packed two-plane word per glyph, instead of scanning 136 columns.
    ldx #0
    stz number
@tile:
    lda f:METER_PIXELS,x
    sta scratch
    cmp f:METER_LAST_PIXELS,x
    bne @changed
    lda meter_bitmap_valid
    jne @next_tile
@changed:
    lda #1
    sta meter_bitmap_dirty
    lda scratch
    sta f:METER_LAST_PIXELS,x
    phx
    ldx number
    ; Editable CHR tile 8 supplies the tick's vertical silhouette; tile 3
    ; supplies the baseline. Only the per-column age/color is procedural.
    .repeat 8, row
    lda f:FONT_ADDR+8*16+row*2
    and #$8080
    beq :+
    lda scratch
:
    ora f:FONT_ADDR+3*16+row*2
    sta f:METER_BITMAP+row*2,x
    .endrepeat
    plx
@next_tile:
    lda number
    clc
    adc #16
    sta number
    inx
    inx
    cpx #34
    jcc @tile
    lda #1
    sta meter_bitmap_valid
    ; Editable CHR tile 4 supplies the static perfect-timing reference.
    ldx #128
    .repeat 8, row
    lda f:METER_BITMAP+row*2,x
    ora f:FONT_ADDR+4*16+row*2
    sta f:METER_BITMAP+row*2,x
    .endrepeat
    lda #1
    sta hud_meter_dirty
    ldx #0
    lda #$3C80
@map:
    sta HUD+24*64+7*2,x
    pha
    lda #0
    sta HUD+25*64+7*2,x
    pla
    inc a
    inx
    inx
    cpx #34
    bcc @map
    lda meter_count
    beq @done
    lda meter_average
    pha
    lsr a
    lsr a
    lsr a
    asl a
    tay
    pla
    and #7
    clc
    adc #16
    ora #$3C00
    sta HUD+25*64+7*2,y
@done:
    rts
meter_erase_masks:
    .word $7F7F,$BFBF,$DFDF,$EFEF,$F7F7,$FBFB,$FDFD,$FEFE
meter_shade_masks:
    .word $0080,$0040,$0020,$0010,$0008,$0004,$0002,$0001
    .word $8000,$4000,$2000,$1000,$0800,$0400,$0200,$0100
    .word $8080,$4040,$2020,$1010,$0808,$0404,$0202,$0101
.else
.include "hit_meter_legacy.inc"
.endif
