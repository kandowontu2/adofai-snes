; Native-scale circular streaks. Every fragment is part of the same
; 24-pixel orbit as the planet, so skipped frames cannot form chords,
; zigzags, or detached pieces of old world-coordinate history.
record_trails:
    lda trail_count
    bne @compare
    lda #2
    sta trail_count
    lda step
    sta f:TRAIL_TICKS
    lda tick
    sec
    sbc #8
    sta f:TRAIL_TICKS+2
    rts
@compare:
    lda step
    cmp f:TRAIL_TICKS
    beq @done
    sta f:TRAIL_TICKS
    lda tick
    sta f:TRAIL_TICKS+2
@done:
    rts

draw_trails:
    lda #1
    sta object_small
    jsr pivot_position
.ifdef SA1_BUILD
    ; The last projected center is ready. Prepare the next track map in
    ; parallel with the remaining OAM-only arc drawing. Initial loading
    ; must first populate the map and therefore stays synchronous.
    lda state
    cmp #1
    bne :+
    lda m7_loading
    bne :+
    jsl mode7_rotation_bounds
    jsr sa1_cache_begin
:
.endif
    lda sprite_x
    clc
    adc #8
    sta trail_move_x
    sta trail_pos_x
    lda sprite_y
    clc
    adc #8
    sta trail_move_y
    sta trail_pos_y
    ; The moving planet has the opposite color from the current pivot.
    lda step
    and #1
    eor #1
    sta trail_orb
    stz trail_age
    lda OAM+17
    and #255
    cmp #224
    jeq @afterglow
    lda mul_delta
    bmi @afterglow
    ldx step
    lda angle
    sec
    sbc f:NOTE_ANGLE,x
    and #255
    ldy mul_rate
    bpl @phase
    eor #$FFFF
    inc a
    and #255
@phase:
    cmp #32
    bcc :+
    lda #32
:
    clc
    adc #3
    lsr a
    lsr a
    sta trail_pieces
    beq @afterglow
    lda angle
.ifdef SA1_BUILD
    clc
    adc f:M7_ROT_PHASE
    and #255
.endif
    lsr a
    lsr a
    sta trail_current
    lda mul_rate
    jsr orbit_trail_direction
    jsr draw_orbit_arc
@afterglow:
    ; A landed planet retains a short fading arc, anchored to its current
    ; center. Do not bridge a midspin, three-planet change, or retry.
    lda step
    jeq @done
    lda OAM+1
    and #255
    cmp #224
    jeq @done
    lda step
    tax
    lda f:NOTE_CCW,x
    and #2
    jne @done
    lda f:NOTE_FLAGS,x
    and #16
    jne @done
    dex
    lda f:NOTE_FLAGS,x
    and #16
    jne @done
    lda tick
    sec
    sbc f:TRAIL_TICKS+2
    cmp #8
    jcs @done
    lsr a
    sta trail_age
    lda step
    and #1
    sta trail_orb
    ldx step
    lda f:NOTE_ANGLE,x
    clc
    adc #128
.ifdef SA1_BUILD
    clc
    adc f:M7_ROT_PHASE
.endif
    and #255
    sta trail_current
    tax
    lda cos24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
 .ifdef SA1_BUILD
    jsl camera_scale_offset
 .endif
    sta trail_abs_x
    lda sin24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
 .ifdef SA1_BUILD
    jsl camera_scale_offset
 .endif
    sta trail_abs_y
    lda trail_move_x
    sec
    sbc trail_abs_x
    sta trail_pos_x
    lda trail_move_y
    sec
    sbc trail_abs_y
    sta trail_pos_y
    lda trail_current
    lsr a
    lsr a
    sta trail_current
    lda step
    dec a
    asl a
    tax
    lda f:NOTE_RATE,x
    jsr orbit_trail_direction
    lda #8
    sta trail_pieces
    jsr draw_orbit_arc
@done:
    stz object_small
    rts

orbit_trail_direction:
    bmi @ccw
    lda #$FFFF
    bra @store
@ccw:
    lda #1
@store:
    sta trail_previous
    rts

draw_orbit_arc:
    stz trail_stroke
@piece:
    lda trail_stroke
    lsr a
    clc
    adc trail_age
    cmp #4
    bcs @done
    .repeat 4
    asl a
    .endrepeat
    sta trail_abs_x
    ldy trail_current
    lda orbit_arc_tiles,y
    and #255
    clc
    adc trail_abs_x
    sta sprite_tile
    lda camera_inverse
    cmp #320
    bcc :+
    lda sprite_tile
    clc
    adc #64
    sta sprite_tile
:
    lda trail_orb
    asl a
    clc
    adc #$38
    sta sprite_attr
    lda orbit_arc_flips,y
    and #255
    ora sprite_attr
    sta sprite_attr
    tya
    asl a
    tay
    lda orbit_arc_x,y
 .ifdef SA1_BUILD
    jsl camera_scale_sprite
 .endif
    clc
    adc trail_pos_x
    sta sprite_x
    lda orbit_arc_y,y
 .ifdef SA1_BUILD
    jsl camera_scale_sprite
 .endif
    clc
    adc trail_pos_y
    sta sprite_y
    lda oam_pos
    sta trail_oam
    jsr sprite
    lda oam_pos
    cmp trail_oam
    beq @done
    lda trail_current
    clc
    adc trail_previous
    and #63
    sta trail_current
    inc trail_stroke
    dec trail_pieces
    jne @piece
@done:
    rts

