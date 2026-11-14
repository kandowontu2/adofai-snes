.segment "CODE"
neo_prepare_hold:
    jsl neo_far_prepare_hold
    rts
neo_offset_pivot:
    jsl neo_far_offset_pivot
    rts
neo_apply_ease:
    jsl neo_far_apply_ease
    rts
neo_reset_free:
    jsl neo_far_reset_free
    rts
neo_prepare_free:
    jsl neo_far_prepare_free
    rts
neo_free_camera:
    jsl neo_far_free_camera
    rts
neo_free_orbit:
    jsl neo_far_free_orbit
    rts
neo_free_input:
    jsl neo_far_free_input
    rts
neo_draw_return:
    jsl neo_far_draw_return
    rts
neo_call_multiply_points:
    jsr multiply_points
    rtl
neo_call_divide32:
    jsr divide32
    rtl
neo_call_multiply_phase:
    jsr multiply_phase
    rtl
neo_call_fail:
    jsr fail
    rtl
neo_call_floor_position:
    jsr floor_position
    rtl
neo_call_quarter_signed:
    jsr quarter_signed
    rtl
neo_call_mode7_project:
    jsr mode7_project
    rtl
neo_call_sprite:
    jsr sprite
    rtl
neo_call_sine_cosine:
    jsr sine_cosine
    rtl

.segment "NEOCODE"
; Input A is a floor index. Zero-extra and extended holds use separate
; supplied CHR symbols; releases inherit the preceding hold's color.
neo_far_hold_style:
    jsr neo_note_presentation
    and #1
    rtl

neo_far_orb_roles:
    jsr neo_note_presentation
    rtl

neo_note_presentation:
    tay
    lda selected_level
    asl a
    tax
    tya
    clc
    adc f:neo_hold_starts,x
    tax
    lda f:neo_hold_styles,x
    and #255
    rts

neo_far_prepare_hold:
    jsr neo_impl_prepare_hold
    rtl
neo_far_offset_pivot:
    jsr neo_impl_offset_pivot
    rtl
neo_far_apply_ease:
    jsr neo_impl_apply_ease
    rtl
neo_far_reset_free:
    jsr neo_impl_reset_free
    rtl
neo_far_prepare_free:
    jsr neo_impl_prepare_free
    rtl
neo_far_free_camera:
    jsr neo_impl_free_camera
    rtl
neo_far_free_orbit:
    jsr neo_impl_free_orbit
    rtl
neo_far_free_input:
    jsr neo_impl_free_input
    rtl
neo_far_draw_return:
    jsr neo_impl_draw_return
    rtl
; Holds translate the pivot along the authored bridge while the planets
; continue rotating. All phase calculations use chart time, not frame count.
neo_impl_prepare_hold:
    stz neo_hold_x
    stz neo_hold_y
    lda step
    asl a
    tax
    lda f:NOTE_PAUSE,x
    bmi :+
    jmp @done
:
    lda f:NOTE_TIME+2,x
    sec
    sbc f:NOTE_TIME,x
    jeq @done
    sta neo_hold_duration
    lda chart_time
    sec
    sbc f:NOTE_TIME,x
    bpl :+
    jmp @done
:
    cmp neo_hold_duration
    bcc :+
    lda neo_hold_duration
:
    sta math_a
    ; Authored easing already supplies the exact phase. Only divide for
    ; holds without a curve; the lookup preserves math_a for that fallback.
    jsr neo_find_curve
    bcc @linear_phase
    txa
    asl a
    tax
    lda f:neo_ease_phases,x
    sta neo_hold_phase
    bra @phase_ready
@linear_phase:
    lda #256
    sta math_b
    jsl neo_call_multiply_points
    lda neo_hold_duration
    sta math_b
    jsl neo_call_divide32
    lda math_lo
    sta neo_hold_phase
@phase_ready:
    lda step
    inc a
    tax
    lda f:NOTE_ANGLE,x
    and #255
    tax
    lda f:cos24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    sta neo_hold_x
    lda f:sin24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    sta neo_hold_y
    lda step
    asl a
    tax
 .ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    beq @wram_hold_x
    lda f:NATIVE_READY
    beq @wram_hold_x
    lda f:SYMBOL_X+2,x
    sec
    sbc f:SYMBOL_X,x
    bra @hold_x_ready
@wram_hold_x:
.endif
    lda f:NOTE_X+2,x
    sec
    sbc f:NOTE_X,x
@hold_x_ready:
    clc
    adc neo_hold_x
    jsr neo_scale_hold
    sta neo_hold_x
    lda step
    asl a
    tax
 .ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    beq @wram_hold_y
    lda f:NATIVE_READY
    beq @wram_hold_y
    lda f:SYMBOL_Y+2,x
    sec
    sbc f:SYMBOL_Y,x
    bra @hold_y_ready
@wram_hold_y:
.endif
    lda f:NOTE_Y+2,x
    sec
    sbc f:NOTE_Y,x
@hold_y_ready:
    clc
    adc neo_hold_y
    jsr neo_scale_hold
    sta neo_hold_y
@done:
    rts

neo_scale_hold:
    ldx neo_hold_phase
    cpx #256
    bne :+
    rts
:
    pha
    ; CPX above describes the phase, not the signed offset in A.
    cmp #0
    bpl :+
    eor #$FFFF
    inc a
:
    sta math_a
    lda neo_hold_phase
    cmp #256
    bcs @wide_phase
    ; Exact floor(abs(offset) * phase / 256). NMI does not use
    ; the S-CPU multiplier; SA-1 has its own independent unit.
    sep #$20
    .a8
    lda math_a
    sta $4202
    lda neo_hold_phase
    sta $4203
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4216
    xba
    and #255
    sta scratch
    sep #$20
    .a8
    lda math_a+1
    sta $4202
    lda neo_hold_phase
    sta $4203
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4216
    clc
    adc scratch
    sta scratch
    bra @sign
@wide_phase:
    ; Preserve overshooting authored curves, including wrapped negatives.
    sta math_b
    jsl neo_call_multiply_points
    lda math_lo
    xba
    and #255
    sta scratch
    lda math_hi
    xba
    ora scratch
    sta scratch
@sign:
    pla
    bpl :+
    lda scratch
    eor #$FFFF
    inc a
    rts
:
    lda scratch
    rts

neo_impl_offset_pivot:
    lda floor_x
    clc
    adc neo_hold_x
    sta floor_x
    lda floor_y
    clc
    adc neo_hold_y
    sta floor_y
    rts

neo_impl_apply_ease:
    jsr neo_find_curve
    bcc @done
    lda f:neo_ease_samples,x
    and #255
    sta angle
@done:
    rts

neo_find_curve:
    ; Preserve the arithmetic workspace used by hold interpolation.
    lda math_a
    pha
    lda math_b
    pha
    lda math_lo
    pha
    jsr neo_find_curve_index
    pla
    sta math_lo
    pla
    sta math_b
    pla
    sta math_a
    rts

neo_find_curve_index:
    lda step
    inc a
    cmp neo_curve_cache_step
    bne @lookup
    lda selected_level
    cmp neo_curve_cache_level
    bne @lookup
    ldx neo_curve_cache_record
    cpx #$FFFF
    beq @done
    jmp @curve
@lookup:
    lda step
    inc a
    sta neo_curve_cache_step
    lda selected_level
    sta neo_curve_cache_level
    lda #$FFFF
    sta neo_curve_cache_record
    lda selected_level
    asl a
    tax
    lda f:neo_ease_counts,x
    beq @done
    sta math_b
    stz math_a
    lda f:neo_ease_starts,x
    sta scratch2
@find:
    lda math_a
    cmp math_b
    bcs @done
    clc
    adc math_b
    lsr a
    sta math_lo
    asl a
    asl a
    asl a
    clc
    adc scratch2
    tax
    lda f:neo_ease_records,x
    cmp step
    beq @curve
    bcs @earlier
    lda math_lo
    inc a
    sta math_a
    bra @find
@earlier:
    lda math_lo
    sta math_b
    bra @find
@done:
    clc
    rts
@curve:
    stx neo_curve_cache_record
    lda chart_time
    sec
    sbc f:neo_ease_records+2,x
    bpl :+
    lda #0
:
    cmp f:neo_ease_records+4,x
    bcc :+
    lda f:neo_ease_records+4,x
:
    clc
    adc f:neo_ease_records+6,x
    tax
    sec
    rts

; Free-roam keeps the chart floor fixed while individual input edges move
; the pivot around its authored grid. No chart note or score is fabricated.
neo_impl_reset_free:
    lda #$FFFF
    sta neo_free_step
    stz neo_free_mode
    stz neo_free_hops
    rts

neo_sync_free:
    lda step
    asl a
    tax
    lda f:NOTE_PAUSE,x
    and #$4000
    bne @region
    jmp neo_impl_reset_free
@region:
    lda step
    cmp neo_free_step
    jeq @transition
    sta neo_free_step
    stz neo_free_mode
    stz neo_free_hops
    stz neo_free_x
    stz neo_free_y
    stz neo_coin_mask
    stz neo_free_collected
    stz neo_free_checked
    stz neo_free_autocursor
    lda f:NOTE_TIME,x
    sta neo_free_time
    ldx step
    lda f:NOTE_ANGLE,x
    and #255
    sta neo_free_angle
    lda selected_level
    asl a
    tax
    lda f:neo_free_counts,x
    sta scratch2
    lda f:neo_free_starts,x
    tax
@find:
    lda scratch2
    jeq @done
    lda f:neo_free_records,x
    cmp step
    beq @found
    txa
    clc
    adc #64
    tax
    dec scratch2
    bra @find
@found:
    stx neo_free_record
    lda cam_x
    sta neo_cam_x
    lda cam_y
    sta neo_cam_y
    lda #1
    sta neo_free_mode
    sta neo_cam_active
@transition:
    lda neo_free_mode
    cmp #1
    bne @done
    ldx neo_free_record
    lda neo_free_clock
    cmp f:neo_free_records+4,x
    bcc @done
    lda #2
    sta neo_free_mode
    lda f:neo_free_records+10,x
    sta neo_return_begin
    clc
    adc f:neo_free_records+52,x
    sta neo_return_until
    lda f:neo_free_records+52,x
    sta neo_return_fade
    lda neo_free_x
    sta neo_free_from_x
    lda neo_free_y
    sta neo_free_from_y
@done:
    rts

neo_impl_prepare_free:
    lda chart_time
    sta neo_free_clock
    jsr neo_sync_free
    lda neo_free_mode
    beq @done
    lda neo_free_x
    sta neo_hold_x
    lda neo_free_y
    sta neo_hold_y
    lda neo_free_mode
    cmp #2
    bne @done
    ldx neo_free_record
    lda chart_time
    sec
    sbc f:neo_free_records+4,x
    cmp f:neo_free_records+6,x
    bcc :+
    lda f:neo_free_records+6,x
:
    asl a
    clc
    adc f:neo_free_records+24,x
    tax
    lda f:neo_free_phases,x
    sta neo_hold_phase
    ldx neo_free_record
    lda f:neo_free_records+20,x
    sec
    sbc neo_free_from_x
    jsr neo_scale_hold
    clc
    adc neo_free_from_x
    sta neo_hold_x
    ldx neo_free_record
    lda f:neo_free_records+22,x
    sec
    sbc neo_free_from_y
    jsr neo_scale_hold
    clc
    adc neo_free_from_y
    sta neo_hold_y
    lda step
    jsl neo_call_floor_position
    lda floor_x
    clc
    adc neo_hold_x
    sta neo_return_x
    lda floor_y
    clc
    adc neo_hold_y
    sta neo_return_y
@done:
    rts

; A = chart-clock sample. Input uses the queued edge's clock; rendering
; uses the current song clock, so missed video frames never alter a turn.
neo_impl_free_orbit:
    sta neo_free_clock
    lda neo_free_mode
    beq @done
    cmp #2
    beq @return
    lda step
    asl a
    tax
    lda f:NOTE_RATE,x
    sta mul_rate
    lda neo_free_clock
    sec
    sbc neo_free_time
    sta mul_delta
    jsl neo_call_multiply_phase
    clc
    adc neo_free_angle
    and #255
    sta angle
    rts
@return:
    ldx neo_free_record
    lda f:neo_free_records+28,x
    sta mul_rate
    lda neo_free_clock
    sec
    sbc f:neo_free_records+10,x
    sta mul_delta
    jsl neo_call_multiply_phase
    ldx neo_free_record
    clc
    adc f:neo_free_records+26,x
    and #255
    sta angle
@done:
    rts

neo_impl_free_input:
    lda tap_clock
    sta neo_free_clock
    jsr neo_sync_free
    jsr neo_autoplay_free
    jsr neo_free_objectives
    jsr neo_laser_collision
    lda state
    cmp #1
    jne @consumed
    lda neo_free_mode
    jeq @ordinary
    cmp #2
    bne @grid
    ldx neo_free_record
    lda tap_clock
    cmp f:neo_free_records+8,x
    jcs @ordinary
    jmp @consumed
@grid:
    lda autoplay
    jne @consumed
    lda tap_release
    jne @consumed
    lda pressed
    and #TAP_MASK
    jeq @consumed
    lda tap_clock
    sec
    sbc neo_free_time
    cmp #3
    jcc @consumed
    lda tap_clock
    jsr neo_impl_free_orbit
    lda angle
    clc
    adc #32
    and #192
    sta scratch2
    tax
    lda f:cos24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    clc
    adc neo_free_x
    sta neo_free_from_x
    lda f:sin24,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    clc
    adc neo_free_y
    sta neo_free_from_y
    ; Bias signed coordinates before unsigned bounds comparisons.
    ldx neo_free_record
    lda neo_free_from_x
    sec
    sbc f:neo_free_records+12,x
    bpl :+
    jmp @outside
:
    lda f:neo_free_records+16,x
    sec
    sbc neo_free_from_x
    bpl :+
    jmp @outside
:
    lda neo_free_from_y
    sec
    sbc f:neo_free_records+14,x
    bpl :+
    jmp @outside
:
    lda f:neo_free_records+18,x
    sec
    sbc neo_free_from_y
    bpl :+
    jmp @outside
:
    lda f:neo_free_records+34,x
    sta scratch
    lda f:neo_free_records+32,x
    tax
@cell:
    lda f:neo_free_cells,x
    cmp neo_free_from_x
    bne @next_cell
    lda f:neo_free_cells+2,x
    cmp neo_free_from_y
    beq @land
@next_cell:
    inx
    inx
    inx
    inx
    dec scratch
    bne @cell
    bra @outside
@land:
    ; The cell table is shared with warning cells; deaths use a separate
    ; per-region array indexed by the matched landable-cell ordinal.
    ldx neo_free_record
    lda f:neo_free_records+34,x
    sec
    sbc scratch
    asl a
    clc
    adc f:neo_free_records+62,x
    tax
    lda tap_clock
    cmp f:neo_free_deaths,x
    jcs @outside
    lda neo_free_from_x
    sta neo_free_x
    lda neo_free_from_y
    sta neo_free_y
    lda scratch2
    eor #128
    sta neo_free_angle
    lda tap_clock
    sta neo_free_time
    inc neo_free_hops
@consumed:
    sec
    rts
@ordinary:
    clc
    rts
@outside:
    lda #1
    sta fail_reason
    jsl neo_call_fail
    sec
    rts

neo_impl_free_camera:
    lda neo_cam_active
    bne :+
    rts
:
    lda neo_free_mode
    beq @smooth
    lda step
    jsl neo_call_floor_position
    lda neo_free_mode
    cmp #1
    bne @follow
    ldx neo_free_record
    lda f:neo_free_records+46,x
    beq @follow
    ; T3's coin field stays in view while the player explores it.
    lda f:neo_free_records+12,x
    clc
    adc f:neo_free_records+16,x
    cmp #$8000
    ror a
    clc
    adc floor_x
    sec
    sbc #128
    sta cam_x
    lda f:neo_free_records+14,x
    clc
    adc f:neo_free_records+18,x
    cmp #$8000
    ror a
    clc
    adc floor_y
    sec
    sbc #104
    sta cam_y
    bra @smooth
@follow:
    lda floor_x
    clc
    adc neo_hold_x
    sec
    sbc #128
    sta cam_x
    lda floor_y
    clc
    adc neo_hold_y
    sec
    sbc #104
    sta cam_y
@smooth:
    lda cam_x
    sta neo_free_object_x
    lda cam_y
    sta neo_free_object_y
    lda cam_x
    sec
    sbc neo_cam_x
    jsr neo_camera_delta
    clc
    adc neo_cam_x
    sta cam_x
    sta neo_cam_x
    lda cam_y
    sec
    sbc neo_cam_y
    jsr neo_camera_delta
    clc
    adc neo_cam_y
    sta cam_y
    sta neo_cam_y
    lda neo_free_mode
    bne @done
    lda cam_x
    cmp neo_free_object_x
    bne @done
    lda cam_y
    cmp neo_free_object_y
    bne @done
    stz neo_cam_active
@done:
    rts

neo_camera_delta:
    cmp #4
    bcc @done
    cmp #$FFFD
    bcs @done
    jsl neo_call_quarter_signed
    rts
@done:
    rts

; Only the occupied cell follows the return tween. The background grid
; has its own authored fade and must never be translated with the player.
neo_impl_draw_return:
    jsr neo_draw_collectibles
    jsr neo_draw_laser
    jsr neo_draw_meteors
    lda neo_return_until
    jeq @done
    cmp chart_time
    jcc @done
    stz neo_return_shade
    lda chart_time
    sec
    sbc neo_return_begin
    bmi @bright
    sta math_a
    lda #4
    sta math_b
    jsl neo_call_multiply_points
    lda neo_return_fade
    sta math_b
    jsl neo_call_divide32
    lda math_lo
    cmp #4
    jcs @done
    beq @bright
    inc a
    asl a
    asl a
    sta neo_return_shade
@bright:
    lda #1
    sta object_small
    ldy #0
@part:
    phy
    lda neo_return_x
    sta floor_x
    lda neo_return_y
    sta floor_y
    ply
    phy
    tya
    asl a
    tax
    lda floor_x
    clc
    adc f:neo_cell_x,x
    sta floor_x
    lda floor_y
    clc
    adc f:neo_cell_y,x
    sta floor_y
    jsl neo_call_mode7_project
    ; mode7_project returns a 16-pixel OBJ origin; this is an 8-pixel part.
    lda sprite_x
    clc
    adc #4
    sta sprite_x
    lda sprite_y
    clc
    adc #4
    sta sprite_y
    ply
    phy
    tyx
    lda f:neo_cell_tiles,x
    and #255
    clc
    adc neo_return_shade
    sta sprite_tile
    lda f:neo_cell_flags,x
    and #255
    ora #$21
    sta sprite_attr
    jsl neo_call_sprite
    ply
    iny
    cpy #9
    bcc @part
    stz object_small
@done:
    rts
neo_cell_x: .word $FFF8,0,8,$FFF8,0,8,$FFF8,0,8
neo_cell_y: .word $FFF8,$FFF8,$FFF8,0,0,0,8,8,8
neo_cell_tiles: .byte 192,193,192,194,195,194,192,193,192
neo_cell_flags: .byte 0,0,64,0,0,64,128,128,192

; Projectiles use the same chart clock as the hidden defense rhythm floors.
; Fixed-point velocities are compiled from authored approach times/directions.
neo_draw_meteors:
    lda selected_level
    asl a
    tax
    lda f:neo_meteor_counts,x
    sta neo_free_count
    jeq @done
    lda f:neo_meteor_starts,x
    sta neo_free_pointer
    ; Lower-bound search skips expired projectiles, including on checkpoint
    ; resumes. Work per frame depends on visible targets, not song progress.
    stz neo_free_index
    lda neo_free_count
    sta neo_free_mask
@search:
    lda neo_free_index
    cmp neo_free_mask
    bcs @found
    clc
    adc neo_free_mask
    lsr a
    sta scratch2
    jsr neo_meteor_offset
    tax
    lda f:neo_meteor_records+2,x
    cmp chart_time
    bcs @earlier
    lda scratch2
    inc a
    sta neo_free_index
    bra @search
@earlier:
    lda scratch2
    sta neo_free_mask
    bra @search
@found:
    lda neo_free_count
    sec
    sbc neo_free_index
    sta neo_free_count
    jeq @done
    lda neo_free_index
    jsr neo_meteor_offset
    sta neo_free_pointer
    lda #1
    sta object_small
@next:
    ldx neo_free_pointer
    lda chart_time
    cmp f:neo_meteor_records,x
    jcc @done
    lda f:neo_meteor_records+2,x
    sec
    sbc chart_time
    bmi @advance
    sta neo_hold_phase
    lda step
    cmp f:neo_meteor_records+4,x
    bcs @advance
    lda f:neo_meteor_records+10,x
    jsr neo_scale_hold
    ldx neo_free_pointer
    clc
    adc f:neo_meteor_records+6,x
    sta neo_free_object_x
    lda f:neo_meteor_records+12,x
    jsr neo_scale_hold
    ldx neo_free_pointer
    clc
    adc f:neo_meteor_records+8,x
    sta floor_y
    lda neo_free_object_x
    sta floor_x
    jsl neo_call_mode7_project
    lda sprite_x
    clc
    adc #4
    sta sprite_x
    lda sprite_y
    clc
    adc #4
    sta sprite_y
    lda #212
    sta sprite_tile
    lda #$23
    sta sprite_attr
    jsl neo_call_sprite
@advance:
    lda neo_free_pointer
    clc
    adc #14
    sta neo_free_pointer
    dec neo_free_count
    jne @next
@done:
    stz object_small
    rts
neo_meteor_offset:
    asl a
    sta scratch
    asl a
    asl a
    asl a
    sec
    sbc scratch
    clc
    adc neo_free_pointer
    rts

neo_free_objectives:
    lda neo_free_mode
    jeq @done
    lda chart_time
    jsr neo_impl_free_orbit
    jsl neo_call_sine_cosine
    ldx neo_free_record
    lda f:neo_free_records+38,x
    sta neo_free_count
    jeq @hazards
    lda f:neo_free_records+36,x
    sta neo_free_pointer
    lda #1
    sta neo_free_mask
@coin:
    lda neo_coin_mask
    and neo_free_mask
    bne @next_coin
    ldx neo_free_pointer
    lda f:neo_free_coins,x
    sta neo_free_object_x
    lda f:neo_free_coins+2,x
    sta neo_free_object_y
    lda neo_free_x
    sec
    sbc neo_free_object_x
    jsr neo_near_coin
    bcc @orbit_coin
    lda neo_free_y
    sec
    sbc neo_free_object_y
    jsr neo_near_coin
    bcs @collect
@orbit_coin:
    lda neo_free_x
    clc
    adc orbit_x
    sec
    sbc neo_free_object_x
    jsr neo_near_coin
    bcc @next_coin
    lda neo_free_y
    clc
    adc orbit_y
    sec
    sbc neo_free_object_y
    jsr neo_near_coin
    bcc @next_coin
@collect:
    lda neo_coin_mask
    ora neo_free_mask
    sta neo_coin_mask
    inc neo_free_collected
@next_coin:
    lda neo_free_pointer
    clc
    adc #4
    sta neo_free_pointer
    asl neo_free_mask
    dec neo_free_count
    bne @coin
    ldx neo_free_record
    lda chart_time
    cmp f:neo_free_records+40,x
    bcc @hazards
    lda neo_free_collected
    cmp #3
    jcc @failed
@hazards:
    ldx neo_free_record
    lda f:neo_free_records+44,x
    sta neo_free_count
    jeq @done
    lda f:neo_free_records+42,x
    sta neo_free_pointer
    lda #1
    sta neo_free_mask
@hazard:
    lda neo_free_checked
    and neo_free_mask
    bne @next_hazard
    ldx neo_free_pointer
    lda chart_time
    cmp f:neo_free_hazards+2,x
    bcc @next_hazard
    lda neo_free_checked
    ora neo_free_mask
    sta neo_free_checked
    lda chart_time
    cmp f:neo_free_hazards+4,x
    bcs @next_hazard
    lda f:neo_free_hazards+8,x
    sta scratch
    lda f:neo_free_hazards+6,x
    tax
@danger_cell:
    lda f:neo_free_cells,x
    cmp neo_free_x
    bne @next_danger
    lda f:neo_free_cells+2,x
    cmp neo_free_y
    beq @failed
@next_danger:
    inx
    inx
    inx
    inx
    dec scratch
    bne @danger_cell
@next_hazard:
    lda neo_free_pointer
    clc
    adc #10
    sta neo_free_pointer
    asl neo_free_mask
    dec neo_free_count
    bne @hazard
@done:
    rts
@failed:
    lda autoplay
    bne @done
    lda #1
    sta fail_reason
    jsl neo_call_fail
    rts

neo_near_coin:
    bpl :+
    eor #$FFFF
    inc a
:
    cmp #6
    bcs @far
    sec
    rts
@far:
    clc
    rts

neo_draw_collectibles:
    lda neo_free_mode
    jeq @done
    ldx neo_free_record
    lda f:neo_free_records+38,x
    sta neo_free_count
    jeq @hazards
    lda f:neo_free_records+36,x
    sta neo_free_pointer
    lda #1
    sta object_small
    sta neo_free_mask
@coin:
    lda neo_coin_mask
    and neo_free_mask
    bne @next_coin
    ldx neo_free_pointer
    lda f:neo_free_coins,x
    sta neo_free_object_x
    lda f:neo_free_coins+2,x
    sta neo_free_object_y
    jsr neo_object_position
    lda #196
    sta sprite_tile
    lda #$23
    sta sprite_attr
    jsl neo_call_sprite
@next_coin:
    lda neo_free_pointer
    clc
    adc #4
    sta neo_free_pointer
    asl neo_free_mask
    dec neo_free_count
    bne @coin
@hazards:
    ldx neo_free_record
    lda f:neo_free_records+44,x
    sta neo_free_count
    beq @done
    lda f:neo_free_records+42,x
    sta neo_free_pointer
    lda #1
    sta object_small
@hazard:
    ldx neo_free_pointer
    lda chart_time
    cmp f:neo_free_hazards,x
    bcc @next_hazard
    cmp f:neo_free_hazards+4,x
    bcs @next_hazard
    lda f:neo_free_hazards+8,x
    sta neo_free_mask
    lda f:neo_free_hazards+6,x
    sta neo_free_index
@cell:
    ldx neo_free_index
    lda f:neo_free_cells,x
    sta neo_free_object_x
    lda f:neo_free_cells+2,x
    sta neo_free_object_y
    jsr neo_object_position
    lda #197
    sta sprite_tile
    lda #$23
    sta sprite_attr
    jsl neo_call_sprite
    lda neo_free_index
    clc
    adc #4
    sta neo_free_index
    dec neo_free_mask
    bne @cell
@next_hazard:
    lda neo_free_pointer
    clc
    adc #10
    sta neo_free_pointer
    dec neo_free_count
    bne @hazard
@done:
    stz object_small
    rts

neo_object_position:
    lda step
    jsl neo_call_floor_position
    lda floor_x
    clc
    adc neo_free_object_x
    sta floor_x
    lda floor_y
    clc
    adc neo_free_object_y
    sta floor_y
    jsl neo_call_mode7_project
    lda sprite_x
    clc
    adc #4
    sta sprite_x
    lda sprite_y
    clc
    adc #4
    sta sprite_y
    rts

; Per-frame authored collision rectangle. Precomputed off-cartridge so the
; SA-1/CPU does no curve evaluation or scene graph traversal during play.
neo_laser_bounds:
    lda neo_free_mode
    cmp #1
    bne @none
    ldx neo_free_record
    lda chart_time
    cmp f:neo_free_records+58,x
    bcs @none
    sec
    sbc f:neo_free_records+56,x
    bcc @none
    asl a
    asl a
    asl a
    clc
    adc f:neo_free_records+54,x
    tay
    lda f:neo_free_records+60,x
    sta neo_laser_axis
    tyx
    lda f:neo_free_lasers,x
    sta neo_laser_left
    lda f:neo_free_lasers+2,x
    sta neo_laser_top
    lda f:neo_free_lasers+4,x
    sta neo_laser_right
    lda f:neo_free_lasers+6,x
    sta neo_laser_bottom
    sec
    rts
@none:
    clc
    rts
neo_laser_collision:
    lda autoplay
    bne @done
    jsr neo_laser_bounds
    bcc @done
    lda chart_time
    jsr neo_impl_free_orbit
    jsl neo_call_sine_cosine
    lda neo_free_x
    sta neo_free_object_x
    lda neo_free_y
    sta neo_free_object_y
    jsr neo_laser_point
    bcs @failed
    lda neo_free_x
    clc
    adc orbit_x
    sta neo_free_object_x
    lda neo_free_y
    clc
    adc orbit_y
    sta neo_free_object_y
    jsr neo_laser_point
    bcc @done
@failed:
    lda #1
    sta fail_reason
    jsl neo_call_fail
@done:
    rts
neo_laser_point:
    lda neo_free_object_x
    sec
    sbc neo_laser_left
    bpl :+
    jmp @outside
:
    lda neo_laser_right
    sec
    sbc neo_free_object_x
    bpl :+
    jmp @outside
:
    lda neo_free_object_y
    sec
    sbc neo_laser_top
    bpl :+
    jmp @outside
:
    lda neo_laser_bottom
    sec
    sbc neo_free_object_y
    bpl :+
    jmp @outside
:
    sec
    rts
@outside:
    clc
    rts
neo_draw_laser:
    jsr neo_laser_bounds
    jcc @done
    ; Segments are eight screen pixels wide. Space them in world units
    ; using zoom so a zoomed-out beam does not waste overlapping sprites.
    lda camera_zoom
    .repeat 5
    lsr a
    .endrepeat
    bne :+
    inc a
:
    sta neo_free_index
    lda #1
    sta object_small
    lda neo_laser_left
    sta neo_free_object_x
    lda neo_laser_top
    sta neo_free_object_y
    lda neo_laser_axis
    beq @vertical
    lda neo_laser_bottom
    sec
    sbc neo_laser_top
    lsr a
    clc
    adc neo_laser_top
    sta neo_free_object_y
    bra @part
@vertical:
    lda neo_laser_right
    sec
    sbc neo_laser_left
    lsr a
    clc
    adc neo_laser_left
    sta neo_free_object_x
@part:
    jsr neo_object_position
    lda #198
    clc
    adc neo_laser_axis
    sta sprite_tile
    lda #$23
    sta sprite_attr
    jsl neo_call_sprite
    lda neo_laser_axis
    beq @next_y
    lda neo_free_object_x
    clc
    adc neo_free_index
    sta neo_free_object_x
    sec
    sbc neo_laser_right
    bmi @part
    bra @finish
@next_y:
    lda neo_free_object_y
    clc
    adc neo_free_index
    sta neo_free_object_y
    sec
    sbc neo_laser_bottom
    bmi @part
@finish:
    stz object_small
@done:
    rts

neo_autoplay_free:
    lda autoplay
    beq @done
    lda neo_free_mode
    cmp #1
    bne @done
@next:
    ldx neo_free_record
    lda neo_free_autocursor
    cmp f:neo_free_records+50,x
    bcs @done
    asl a
    asl a
    asl a
    clc
    adc f:neo_free_records+48,x
    tax
    lda f:neo_free_routes,x
    cmp tap_clock
    bcc @hop
    bne @done
@hop:
    sta neo_free_time
    lda f:neo_free_routes+2,x
    sta neo_free_x
    lda f:neo_free_routes+4,x
    sta neo_free_y
    lda f:neo_free_routes+6,x
    sta neo_free_angle
    inc neo_free_hops
    inc neo_free_autocursor
    bra @next
@done:
    rts



.segment "CODE"
