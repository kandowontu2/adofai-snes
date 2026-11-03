.ifdef MSU_BUILD
.include "orbit_trails.inc"
.else
; Stock cartridges retain their world-coordinate history presentation.
record_trails:
    lda step
    jsr floor_position
    lda floor_x
    sec
    sbc #8
    sta scratch
    lda floor_y
    sec
    sbc #8
    sta scratch2
    ldx trail_head
.ifdef MSU_BUILD
    lda tick
    sta f:TRAIL_TICKS,x
.endif
    lda step
    and #1
    bne @ice_pivot
    lda scratch
    sta FIRE_X,x
    clc
    adc orbit_x
    sta ICE_X,x
    lda scratch2
    sta FIRE_Y,x
    clc
    adc orbit_y
    sta ICE_Y,x
    bra @advance
@ice_pivot:
    lda scratch
    sta ICE_X,x
    clc
    adc orbit_x
    sta FIRE_X,x
    lda scratch2
    sta ICE_Y,x
    clc
    adc orbit_y
    sta FIRE_Y,x
@advance:
    lda trail_head
    clc
    adc #2
    and #31
    sta trail_head
    lda trail_count
    cmp #32
    beq @done
    inc trail_count
    inc trail_count
@done:
    rts

draw_trails:
.ifdef MSU_BUILD
    lda #1
    sta object_small
.endif
    stz trail_orb
@orb:
    stz trail_age
@segment:
    lda trail_age
    clc
    adc #2
    asl a
    cmp trail_count
    bcc @available
    beq @available
    jmp @next_orb
@available:
    lda trail_age
    asl a
    sta trail_current
    lda trail_head
    sec
    sbc #2
    sec
    sbc trail_current
    and #31
    tax
    sta trail_current
    sec
    sbc #2
    and #31
    tay
.ifdef MSU_BUILD
    tyx
    lda tick
    sec
    sbc f:TRAIL_TICKS,x
    ldx trail_current
    cmp #9
    jcs @next_orb
    jsr mode7_trail_endpoints
    bra @trail_distances
.else
    lda trail_orb
    beq @fire
    lda ICE_X,x
    sta trail_pos_x
    lda ICE_Y,x
    sta trail_pos_y
    lda ICE_X,y
    sec
    sbc trail_pos_x
    sta trail_dx
    lda ICE_Y,y
    bra @difference_y
@fire:
    lda FIRE_X,x
    sta trail_pos_x
    lda FIRE_Y,x
    sta trail_pos_y
    lda FIRE_X,y
    sec
    sbc trail_pos_x
    sta trail_dx
    lda FIRE_Y,y
@difference_y:
    sec
    sbc trail_pos_y
    sta trail_dy
.endif
@trail_distances:
    lda trail_dx
    bpl :+
    eor #$FFFF
    inc a
:
    sta trail_abs_x
    lda trail_dy
    bpl :+
    eor #$FFFF
    inc a
:
    sta trail_abs_y
    ora trail_abs_x
    jne @length
    jmp @next_segment
@length:
    lda trail_abs_x
    cmp trail_abs_y
    bcs :+
    lda trail_abs_y
:
.ifdef MSU_BUILD
    cmp #33
.else
    cmp #65
.endif
    jcs @next_segment
    sta trail_current
    clc
    adc #3
    lsr a
    lsr a
    sta trail_pieces
    jsr trail_orientation
.ifdef MSU_BUILD
    ; Choose the shortest stroke that joins consecutive subpixel centers.
    lda trail_current
    clc
    adc trail_pieces
    dec a
    jsr trail_divide
    dec a
    .repeat 4
    asl a
    .endrepeat
    clc
    adc trail_stroke
    sta trail_stroke
.endif
    lda trail_age
.ifdef MSU_BUILD
    cmp #1
.else
    cmp #2
.endif
    bcc @bright
    lda trail_stroke
    clc
    adc #64
    sta trail_stroke
@bright:
    lda trail_abs_x
    xba
    jsr trail_divide
    ldx trail_dx
    bpl :+
    eor #$FFFF
    inc a
:
    sta trail_move_x
    lda trail_abs_y
    xba
    jsr trail_divide
    ldx trail_dy
    bpl :+
    eor #$FFFF
    inc a
:
    sta trail_move_y
    ; Keep fractional movement: integer division used to leave long
    ; segments many pixels short, producing gaps and snapping corners.
    stz trail_i
    stz trail_previous
.ifdef MSU_BUILD
    lda trail_pos_x
    clc
    adc #4
    sta trail_pos_x
    lda trail_pos_y
    clc
    adc #4
    sta trail_pos_y
.else
    lda trail_pos_x
    sec
    sbc cam_x
    sta trail_pos_x
    lda trail_pos_y
    sec
    sbc cam_y
    sta trail_pos_y
.endif
    lda trail_move_x
    cmp #$8000
    ror a
    jsr trail_advance_x
    lda trail_move_y
    cmp #$8000
    ror a
    jsr trail_advance_y
@stroke:
    lda trail_pos_x
    sta sprite_x
    lda trail_pos_y
    sta sprite_y
    lda trail_stroke
    sta sprite_tile
    lda trail_orb
    asl a
    clc
    adc #$38
    sta sprite_attr
    lda oam_pos
    sta trail_oam
    jsr sprite
    lda oam_pos
    cmp trail_oam
    beq @next_orb
    lda trail_move_x
    jsr trail_advance_x
    lda trail_move_y
    jsr trail_advance_y
    dec trail_pieces
    bne @stroke
@next_segment:
    inc trail_age
    lda trail_age
.ifdef MSU_BUILD
    cmp #3
.else
    cmp #4
.endif
    jcc @segment
@next_orb:
    inc trail_orb
    lda trail_orb
    cmp #2
    jcc @orb
.ifdef MSU_BUILD
    stz object_small
.endif
    rts

; A signed 8.8 increment, with separate fractional accumulators so screen
; positions retain their full signed range. Sprite allocation may clobber
; scratch registers, so the fractions live in otherwise unused trail words.
trail_advance_x:
    clc
    adc trail_i
    pha
    and #255
    sta trail_i
    pla
    jsr trail_signed_high
    clc
    adc trail_pos_x
    sta trail_pos_x
    rts
trail_advance_y:
    clc
    adc trail_previous
    pha
    and #255
    sta trail_previous
    pla
    jsr trail_signed_high
    clc
    adc trail_pos_y
    sta trail_pos_y
    rts
trail_signed_high:
    xba
    and #255
    bit #128
    beq :+
    ora #$FF00
:
    rts

trail_divide:
    ldx trail_pieces
    cpx #1
    beq @done
    cpx #2
    beq @half
    cpx #4
    beq @quarter
    cpx #8
    bne @hardware
    lsr a
@quarter:
    lsr a
@half:
    lsr a
@done:
    rts
@hardware:
    sta $4204
    sep #$20
    .a8
    lda trail_pieces
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
    rts

trail_orientation:
    lda trail_abs_x
    cmp trail_abs_y
    bcc @vertical
    sta math_a
    lda trail_abs_y
    sta math_b
    lda #0
    sta trail_stroke
    bra @ratio
@vertical:
    lda trail_abs_y
    sta math_a
    lda trail_abs_x
    sta math_b
    lda #8
    sta trail_stroke
@ratio:
    lda math_b
    .repeat 7
    asl a
    .endrepeat
    sta $4204
    sep #$20
    .a8
    lda math_a
    sta $4206
    .repeat 8
    nop
    .endrepeat
    rep #$20
    .a16
    lda $4214
    tax
    lda trail_angles,x
    and #255
    ldx trail_stroke
    beq @store_angle
    eor #$FFFF
    inc a
    clc
    adc #8
@store_angle:
    sta trail_stroke
@angle:
    lda trail_dx
    eor trail_dy
    bpl @tile
    lda #16
    sec
    sbc trail_stroke
    and #15
    sta trail_stroke
@tile:
    lda trail_stroke
    asl a
    tax
    lda trail_tiles,x
    sta trail_stroke
    rts

.endif

draw_tile_fx:
.ifdef MSU_BUILD
    ; Original landing feedback belongs to the tile surface. Crosses,
    ; circular hit stamps and outward marker bursts obscure tight doubles.
    rts
.else
    lda step
    sta fx_i
    lda #8
    sta fx_left
@tile:
    lda fx_i
    jsr visible_floor
    jeq @next
    lda fx_i
    sta render_i
    jsr tile_position
    lda #40
    sta sprite_tile
    lda #$30
    sta sprite_attr
    lda fx_i
    and #7
    asl a
    tax
    lda HIT_TIMES,x
    beq @draw
    sta scratch
    lda chart_time
    sec
    sbc scratch
    inc a
    cmp #24
    bcs @draw
    sta fx_age
    lsr a
    lsr a
    lsr a
    asl a
    clc
    adc #42
    sta sprite_tile
    lda fx_i
    and #1
    asl a
    clc
    adc #$38
    sta sprite_attr
@draw:
    jsr sprite
    lda fx_i
    cmp step
    bne @next
    lda sprite_tile
    cmp #40
    beq @next
    ; A short outward burst on the newest successful landing.
    lda fx_age
    lsr a
    clc
    adc #5
    sta scratch
    lda sprite_x
    clc
    adc scratch
    sta sprite_x
    lda sprite_y
    sec
    sbc scratch
    sta sprite_y
    lda #14
    sta sprite_tile
    jsr sprite
    jsr tile_position
    lda fx_age
    lsr a
    clc
    adc #5
    sta scratch
    lda sprite_x
    sec
    sbc scratch
    sta sprite_x
    lda sprite_y
    clc
    adc scratch
    sta sprite_y
    jsr sprite
@next:
    lda fx_i
    beq @done
    dec fx_i
    dec fx_left
    jne @tile
@done:
    rts
.endif
