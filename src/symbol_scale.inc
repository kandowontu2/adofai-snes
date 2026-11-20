; Four source CHR symbols share a size cache. No per-object resampling.
; Snapshots use the invisible right-hand BG1 map at VRAM $7400..$77FF.
; The four legacy, non-Neo charts borrow the otherwise unused Neo OBJ bank.
.segment "NEOCODE"
symbol_scale_reset:
    lda #16
    sta f:SYMBOL_SCALE_SIZE
    sta f:SYMBOL_SCALE_BOX
    sta f:SYMBOL_SCALE_LOADED
    lda #14
    sta f:SYMBOL_SCALE_GAP
    lda #0
    sta f:SYMBOL_SCALE_CENTER
    sta f:SYMBOL_SCALE_PENDING
    sta f:SYMBOL_SCALE_BYTES
    ; A previous legacy chart can have borrowed the meteor/math artwork.
    jsl neo_math_load_graphics
    rtl

symbol_scale_update:
    lda #16
    ldx state
    beq @size
    lda camera_inverse
    beq @size
    bpl :+
    eor #$FFFF
    inc a
:
    clc
    adc #8
    .repeat 4
    lsr a
    .endrepeat
    bne :+
    inc a
:
    cmp #33
    bcc @size
    lda #32
@size:
    sta f:SYMBOL_SCALE_SIZE
    cmp #0
    bne :+
    sta f:SYMBOL_SCALE_GAP
    sta f:SYMBOL_SCALE_PENDING
    rtl
:
    dec a
    tax
    lda f:symbol_scale_gaps,x
    and #255
    sta f:SYMBOL_SCALE_GAP
    lda #16
    sta f:SYMBOL_SCALE_BOX
    lda #0
    sta f:SYMBOL_SCALE_CENTER
    sta f:SYMBOL_SCALE_PENDING
    lda f:SYMBOL_SCALE_SIZE
    cmp #16
    jeq @done
    cmp #9
    bcs @large
    lda #8
    sta f:SYMBOL_SCALE_BOX
    lda #4
    bra @center
@large:
    cmp #17
    bcc @art
    lda #32
    sta f:SYMBOL_SCALE_BOX
    lda #$FFF8
@center:
    sta f:SYMBOL_SCALE_CENTER
@art:
    lda #64
    sta f:SYMBOL_SCALE_BASE
    lda #$7400
    sta f:SYMBOL_SCALE_VRAM
    lda f:STREAM_MODE1
    cmp #3
    beq @cache
    lda #192
    sta f:SYMBOL_SCALE_BASE
    lda #$7C00
    sta f:SYMBOL_SCALE_VRAM
@cache:
    ; One lookup setup per frame replaces per-icon format/attribute work.
    lda f:SYMBOL_SCALE_BOX
    lsr a
    lsr a
    lsr a
    sta f:SYMBOL_SCALE_STEP
    lda f:SYMBOL_SCALE_BASE
    ora #$3300
    sta f:SYMBOL_SCALE_TILES
    clc
    adc f:SYMBOL_SCALE_STEP
    eor #$0600
    sta f:SYMBOL_SCALE_TILES+2
    clc
    adc f:SYMBOL_SCALE_STEP
    eor #$0600
    sta f:SYMBOL_SCALE_TILES+4
    clc
    adc f:SYMBOL_SCALE_STEP
    eor #$0600
    sta f:SYMBOL_SCALE_TILES+6
    lda f:SYMBOL_SCALE_SIZE
    cmp f:SYMBOL_SCALE_LOADED
    beq @done
    dec a
    asl a
    asl a
    tax
    lda f:SYMBOL_SCALE_FRAMES_ADDR,x
    clc
    adc #.loword(SYMBOL_SCALE_FRAMES_ADDR)
    sta f:SYMBOL_SCALE_SOURCE
    lda #.bankbyte(SYMBOL_SCALE_FRAMES_ADDR)
    adc #0
    sta f:SYMBOL_SCALE_SOURCE+2
    lda f:SYMBOL_SCALE_FRAMES_ADDR+2,x
    sta f:SYMBOL_SCALE_BYTES
    lda #1
    sta f:SYMBOL_SCALE_PENDING
@done:
    rtl
symbol_scale_gaps:
    .repeat 32,I
    .byte ((I+1)*14+8)/16
    .endrepeat

; Called only when the complete OAM/map frame is published, never prefetch.
symbol_scale_upload:
    lda f:SYMBOL_SCALE_PENDING
    beq @done
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda f:SYMBOL_SCALE_SOURCE+2
    sta $4304
    rep #$20
    .a16
    lda f:SYMBOL_SCALE_VRAM
    sta $2116
    lda f:SYMBOL_SCALE_SOURCE
    sta $4302
    lda f:SYMBOL_SCALE_BYTES
    cmp #512
    bne @one
    ; The two 8-tile rows retain the OBJ sheet's 16-tile row stride.
    lda #256
    sta $4305
    start_dma 1
    lda f:SYMBOL_SCALE_VRAM
    clc
    adc #$100
    sta $2116
    lda f:SYMBOL_SCALE_SOURCE
    clc
    adc #256
    sta $4302
    lda #256
@one:
    sta $4305
    start_dma 1
    lda f:SYMBOL_SCALE_SIZE
    sta f:SYMBOL_SCALE_LOADED
    lda #0
    sta f:SYMBOL_SCALE_PENDING
@done:
    rtl

; Sparse/legacy CPU path. Keep the original tile center and caller state.
symbol_scale_draw:
    lda f:SYMBOL_SCALE_SIZE
    bne :+
    rtl
:
    cmp #16
    bne @scaled
    jml neo_call_sprite
@scaled:
    phx
    lda sprite_x
    pha
    lda sprite_y
    pha
    lda sprite_tile
    pha
    lda sprite_attr
    pha
    lda #0
    sta object_small
    lda f:SYMBOL_SCALE_BOX
    cmp #8
    bne :+
    inc object_small
:
    lda 3,s
    sec
    sbc #32
    tax
    lda f:SYMBOL_SCALE_TILES,x
    and #255
    sta sprite_tile
    lda f:SYMBOL_SCALE_TILES,x
    xba
    and #255
    sta sprite_attr
    lda 7,s
    clc
    adc f:SYMBOL_SCALE_CENTER
    sta sprite_x
    lda 5,s
    clc
    adc f:SYMBOL_SCALE_CENTER
    sta sprite_y
    jsl neo_call_sprite
    lda f:SYMBOL_SCALE_BOX
    cmp #32
    bne @restore
    inc sprite_tile
    inc sprite_tile
    lda sprite_x
    clc
    adc #16
    sta sprite_x
    jsl neo_call_sprite
    lda sprite_tile
    clc
    adc #30
    sta sprite_tile
    lda sprite_x
    sec
    sbc #16
    sta sprite_x
    lda sprite_y
    clc
    adc #16
    sta sprite_y
    jsl neo_call_sprite
    inc sprite_tile
    inc sprite_tile
    lda sprite_x
    clc
    adc #16
    sta sprite_x
    jsl neo_call_sprite
@restore:
    pla
    sta sprite_attr
    pla
    sta sprite_tile
    pla
    sta sprite_y
    pla
    sta sprite_x
    plx
    stz object_small
    rtl
.segment "CODE"
