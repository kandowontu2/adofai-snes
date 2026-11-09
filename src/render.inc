clear_oam:
    ; Only the previous frame's appended objects need hiding. Reset seeds
    ; oam_pos with 512 so the first frame still clears every hardware object.
    lda oam_pos
    beq @high_start
    ldx #0
    lda #$E000
@hide:
    sta OAM,x
    inx
    inx
    inx
    inx
    cpx oam_pos
    bne @hide
@high_start:
    ldx #0
@high:
    stz OAM+512,x
    inx
    inx
    cpx #32
    bne @high
    ldx #0
@budget:
    stz SPRITE_BUDGET,x
    inx
    inx
    cpx #32
    bne @budget
    stz oam_pos
    rts

; Expand losslessly packed two-plane tiles into the PPU's four-plane format.
; Called during loading/forced blank; a full output bank never crosses WRAM.
unpack_track_chr:
.ifdef MSU_BUILD
    jmp mode7_unpack_chr
.endif
    ldx #0
    lda #0
@clear:
    sta f:CHR_RAM,x
    inx
    inx
    cpx DESC+20
    bcc @clear
    ldx #0
    stz map_run
    sep #$20
    .a8
@command:
    lda [transfer_ptr]
    inc transfer_ptr
    bne :+
    inc transfer_ptr+1
:
    pha
    and #127
    inc a
    sta map_run
    pla
    bmi @repeat
@literal:
    lda [transfer_ptr]
    inc transfer_ptr
    bne :+
    inc transfer_ptr+1
:
    jsr @byte
    dec map_run
    bne @literal
    bra @next
@repeat:
    lda [transfer_ptr]
    inc transfer_ptr
    bne :+
    inc transfer_ptr+1
:
    sta map_tile
@run:
    lda map_tile
    jsr @byte
    dec map_run
    bne @run
@next:
    cpx DESC+20
    bcc @command
    rep #$20
    .a16
    rts
    .a8
@byte:
    sta f:CHR_RAM,x
    inx
    txa
    and #31
    cmp #16
    bne @done
    rep #$20
    .a16
    txa
    clc
    adc #16
    tax
    sep #$20
    .a8
@done:
    rts
    .a16

.ifdef SA1_BUILD
.segment "FASTNMI"
.endif
sprite:
    lda oam_pos
    cmp #512
    jcs @done
    lda sprite_x
    cmp #$FFF1
    bcs @xok
    cmp #256
    jcs @done
@xok:
    lda state
    bne @field
    lda sprite_y
    cmp #209
    jcs @done
    bra @append
@field:
    lda sprite_y
    cmp #32
    jcc @done
    cmp #177
    jcs @done
@append:
    ; Sixteen-pixel objects cost two OBJ tiles per scanline. Conservative
    ; eight-line bins cap optional effects before the PPU's 34-tile limit.
    lda sprite_y
    lsr a
    lsr a
    lsr a
    sta budget_first
    lda sprite_y
    clc
    adc #15
    lsr a
    lsr a
    lsr a
    sta budget_last
    ldx budget_first
@check:
    lda SPRITE_BUDGET,x
    and #255
    cmp #17
    jcc @room
    rts
@room:
    inx
    cpx budget_last
    bcc @check
    beq @check
    ldx budget_first
    sep #$20
    .a8
@charge:
    inc SPRITE_BUDGET,x
    inx
    cpx budget_last
    bcc @charge
    beq @charge
    rep #$20
    .a16
    ldx oam_pos
    sep #$20
    .a8
    lda sprite_x
    sta OAM,x
    lda sprite_y
    sta OAM+1,x
    lda sprite_tile
    sta OAM+2,x
    lda sprite_attr
    sta OAM+3,x
    rep #$20
    .a16
    lda sprite_x
    bpl @added
    txa
    and #12
    lsr a
    tay
    lda xhigh_masks,y
    sta scratch2
    txa
    lsr a
    lsr a
    lsr a
    lsr a
    tax
    sep #$20
    .a8
    lda OAM+512,x
    ora scratch2
    sta OAM+512,x
    rep #$20
    .a16
@added:
.ifdef MSU_BUILD
    lda object_small
    bne @size_done
    ldx oam_pos
    txa
    and #12
    lsr a
    tay
    lda xhigh_masks,y
    asl a
    sta scratch2
    txa
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda OAM+512,x
    ora scratch2
    sta OAM+512,x
    rep #$20
    .a16
@size_done:
.endif
    lda oam_pos
    clc
    adc #4
    sta oam_pos
@done:
    rts

.segment "CODE"
render:
.ifdef MSU_BUILD
    lda step
    sta m7_visual_step
    sta m7_logical_step
    lda tick
    sta m7_service_tick
    jsr render_inner
    lda m7_logical_step
    sta step
    rts
render_inner:
    lda state
    cmp #2
    bne :+
    rts
:
.endif
.ifdef MSU_BUILD
    stz object_small
    stz m7_row_count
    stz m7_row_span
    lda state
    cmp #1
    bne @no_animation
    jsr mode7_landing_time
    jsr update_pattern_cache
    lda state
    cmp #2
    bne :+
    rts
:
    cmp #1
    bne @no_animation
    lda m7_visual_step
    sta step
@no_animation:
    jsr mode7_prepare_view
.endif
    jsr clear_oam
    lda #6
    sta sprite_tile
    lda #$38
    sta sprite_attr
    lda state
    cmp #3
    beq @no_orbs
    cmp #8
    beq @no_orbs
    cmp #7
    jeq @settings
    cmp #0
    jeq @title
    cmp #1
    jeq @level
    cmp #2
    jeq @level
    cmp #4
    jeq @level
    cmp #5
    jeq @calibrate
    cmp #6
    bne @emblem
@no_orbs:
    rts
@settings:
    lda #96
    sta sprite_x
    lda #140
    sta sprite_y
    jsr sprite
    lda #144
    sta sprite_x
    lda #$3A
    sta sprite_attr
    jmp sprite
@emblem:
    ; Decorative planets on pause/result screens, clear of the text.
    lda tick
    asl a
    and #255
    sta angle
    jsr sine_cosine
    lda orbit_y
    jsr quarter_signed
    sta orbit_y
    lda orbit_x
    clc
    adc #120
    sta sprite_x
    lda orbit_y
    clc
    adc #152
    sta sprite_y
    jsr sprite
    lda #120
    sec
    sbc orbit_x
    sta sprite_x
    lda #152
    sec
    sbc orbit_y
    sta sprite_y
    lda #$3A
    sta sprite_attr
    jmp sprite
@title:
    lda #8
    sta sprite_x
    lda #24
    sta sprite_y
    jsr sprite
    lda #232
    sta sprite_x
    lda #$3A
    sta sprite_attr
    jmp sprite
@calibrate:
    lda #120
    sta sprite_x
    lda #96
    sta sprite_y
    jsr sprite
.ifdef MSU_BUILD
    ; The metronome keeps moving without input. Input measurement also uses
    ; cal_phase as scratch, so rebuild the visible phase from the live clock.
    lda audio_ticks
@cal_cycle:
    cmp #CALIBRATION_PERIOD
    bcc @cal_phase_ready
    sec
    sbc #CALIBRATION_PERIOD
    bra @cal_cycle
@cal_phase_ready:
    sta cal_phase
    sta math_a
    lda #256
    sta math_b
    jsr multiply_points
    lda #CALIBRATION_PERIOD
    sta math_b
    jsr divide32
    lda math_lo
.else
    lda cal_phase
    asl a
    and #255
.endif
    sta angle
    jsr sine_cosine
    lda orbit_x
    clc
    adc #120
    sta sprite_x
    lda orbit_y
    clc
    adc #96
    sta sprite_y
    lda #$3A
    sta sprite_attr
    jsr sprite
    lda #144
    sta sprite_x
    lda #96
    sta sprite_y
    lda #8
    sta sprite_tile
    jmp sprite
@level:
    lda state
    cmp #1
    bne @fixed_camera
    lda step
    jsr floor_position
.ifdef MSU_BUILD
    lda f:CAMERA_SCRIPT_X
    sta cam_x
    lda f:CAMERA_SCRIPT_Y
    sta cam_y
    bra @fixed_camera
.else
    lda floor_x
    sec
.ifdef MSU_BUILD
    sbc #128
.else
    sbc #96
.endif
    sec
    sbc cam_x
    sta camera_delta
    bpl @x_distance
    eor #$FFFF
    inc a
@x_distance:
    cmp #81
    bcs @snap_x
    lda camera_delta
    jsr quarter_signed
    clc
    adc cam_x
    sta cam_x
    bra @camera_y
@snap_x:
    lda floor_x
    sec
.ifdef MSU_BUILD
    sbc #128
.else
    sbc #96
.endif
    sta cam_x
@camera_y:
    lda floor_y
    sec
.ifdef MSU_BUILD
    sbc #96
.else
    sbc #116
.endif
    sec
    sbc cam_y
    sta camera_delta
    bpl @y_distance
    eor #$FFFF
    inc a
@y_distance:
    cmp #49
    bcs @snap_y
    lda camera_delta
    jsr quarter_signed
    clc
    adc cam_y
    sta cam_y
    bra @fixed_camera
@snap_y:
    lda floor_y
    sec
.ifdef MSU_BUILD
    sbc #96
.else
    sbc #116
.endif
    sta cam_y
.endif
@fixed_camera:
    lda step
    asl a
    tax
    lda f:NOTE_RATE,x
    sta mul_rate
    lda step
    bne @normal_delta
    lda chart_time
    sec
    sbc first_hit
    clc
    adc first_arc_frames
    bra @delta
@normal_delta:
    lda chart_time
    sec
    sbc f:NOTE_TIME,x
    sec
    sbc f:NOTE_PAUSE,x
    bpl @delta
    ldy checkpoint_preroll
    bne @delta
    lda #0
@delta:
    sta mul_delta
    jsr multiply_phase
    ldx step
    clc
    adc f:NOTE_ANGLE,x
    and #255
    sta angle
    jsr sine_cosine
    lda step
    and #1
    asl a
    clc
    adc #$38
    sta sprite_attr
    jsr pivot_position
.ifdef MSU_BUILD
    jsr mode7_draw_orb
.else
    jsr sprite
.endif
    lda sprite_attr
    eor #2
    sta sprite_attr
.ifdef MSU_BUILD
    jsr mode7_orbit_position
    jsr mode7_draw_orb
.else
    jsr pivot_position
    lda sprite_x
    clc
    adc orbit_x
    sta sprite_x
    lda sprite_y
    clc
    adc orbit_y
    sta sprite_y
    jsr sprite
.endif
@symbols:
.ifdef MSU_BUILD
    ldx step
    lda f:NOTE_CCW,x
    and #2
    cmp #2
    bne @two_planets
    lda orbit_x
    pha
    lda orbit_y
    pha
    lda angle
    pha
    lda f:NOTE_CCW,x
    and #1
    beq @third_cw
    lda angle
    clc
    adc #43
    bra @third_angle
@third_cw:
    lda angle
    sec
    sbc #43
@third_angle:
    and #255
    sta angle
    jsr sine_cosine
    jsr mode7_orbit_position
    lda #6
    sta sprite_tile
    lda #$3C
    sta sprite_attr
    jsr mode7_draw_orb
    pla
    sta angle
    pla
    sta orbit_y
    pla
    sta orbit_x
@two_planets:
.endif
.ifdef SA1_BUILD
    stz event_cursor
    lda event_count
    jeq @portal
.else
    lda step
    clc
.ifdef MSU_BUILD
    adc #4
.else
    adc #12
.endif
    cmp last_note
    bcc @end
    lda last_note
@end:
    sta event_end
    lda step
    sec
    sbc #2
    bpl @begin
    lda #0
@begin:
    sta render_i
.endif
@symbol:
.ifdef SA1_BUILD
    ldx event_cursor
    lda f:TRACK_SYMBOL_FLOORS,x
    sta render_i
.endif
    ldx render_i
    lda f:NOTE_FLAGS,x
    bit #128
    jne @next
    and #119
    jeq @next
    lda render_i
    jsr visible_floor
    jeq @next
    ; Most future events are far outside the camera. Cull once before
    ; building either icon, rather than rendering every event in the song.
    jsr tile_position
    lda sprite_x
    cmp #$FFF1
    bcs @event_x
    cmp #256
    jcc @event_x
    jmp @next
@event_x:
    lda sprite_y
    cmp #32
    jcc @next
    cmp #191
    bcc @event_visible
    jmp @next
@event_visible:
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #3
    beq @reverse
    cmp #1
    beq @rabbit
    lda #34
    sta sprite_tile
    lda #$34
    bra @speed
@rabbit:
    lda #32
    sta sprite_tile
    lda #$32
@speed:
    sta sprite_attr
    jsr sprite
@reverse:
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #4
    beq @special
    lda f:NOTE_CCW,x
    and #1
    asl a
    clc
    adc #36
    sta sprite_tile
    lda #$36
    sta sprite_attr
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #3
    beq @swirl
    lda sprite_y
    sec
    sbc #14
    sta sprite_y
@swirl:
    jsr sprite
@special:
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #32
    beq @checkpoint
    lda #72
@special_icon:
    sta sprite_tile
    lda #$36
    sta sprite_attr
    jsr tile_position
    jsr sprite
@checkpoint:
    lda time_attack
    jne @next
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #64
    beq @next
    lda #74
    sta sprite_tile
    lda checkpoint_record
    beq @flag
    dec a
    tax
    lda f:CHECKPOINTS,x
    cmp render_i
    bcc @flag
@activated:
    lda #76
    sta sprite_tile
@flag:
    lda #$36
    sta sprite_attr
    jsr tile_position
    ldx render_i
    lda f:NOTE_FLAGS,x
    and #55
    beq @flag_draw
    lda sprite_y
    sec
    sbc #14
    sta sprite_y
@flag_draw:
    jsr sprite
@next:
.ifdef SA1_BUILD
    inc event_cursor
    inc event_cursor
    lda event_cursor
    cmp event_count
    jcs @portal
.else
    inc render_i
    lda event_end
    cmp render_i
    jcc @portal
.endif
    jmp @symbol
@portal:
    lda state
    cmp #1
    bne @frozen_trails
    jsr record_trails
@frozen_trails:
    jsr draw_tile_fx
    lda last_note
    jsr visible_floor
    beq @hidden_portal
    lda last_note
    sta render_i
    jsr tile_position
    lda #12
    sta sprite_tile
    lda #$36
    sta sprite_attr
    jsr sprite
@hidden_portal:
    ; All projected symbols must finish before draw_trails starts the
    ; parallel SA-1 cache job. The end portal can be visible far ahead.
    jmp draw_trails

pivot_position:
    lda step
    sta render_i
tile_position:
    lda render_i
    jsr floor_position
.ifdef MSU_BUILD
    jmp mode7_project
.endif
    lda floor_x
    sec
    sbc cam_x
    sec
    sbc #8
    sta sprite_x
    lda floor_y
    sec
    sbc cam_y
    sec
    sbc #8
    sta sprite_y
    rts
quarter_signed:
    cmp #$8000
    ror a
    cmp #$8000
    ror a
    bpl @done
    inc a
@done:
    rts
sine_cosine:
    ldx angle
    lda cos24,x
    and #255
    cmp #128
    bcc @cx
    ora #$FF00
@cx:
    sta orbit_x
    lda sin24,x
    and #255
    cmp #128
    bcc @sy
    ora #$FF00
@sy:
    sta orbit_y
    rts

; Bits 8..15 of delta * signed 8.8 rate, using the SNES hardware multiplier.
multiply_phase:
    sep #$20
    .a8
    lda mul_delta
    sta $4202
    lda mul_rate
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
    sta mul_product
    sep #$20
    .a8
    lda mul_delta
    sta $4202
    lda mul_rate+1
    sta $4203
    nop
    nop
    nop
    nop
    lda mul_product
    clc
    adc $4216
    sta mul_product
    lda mul_delta+1
    sta $4202
    lda mul_rate
    sta $4203
    nop
    nop
    nop
    nop
    lda mul_product
    clc
    adc $4216
    rep #$20
    .a16
    and #255
    rts

; Circular BG tilemap cache. A camera tile crossing replaces just the exposed
; row/column; fine scroll uses the full 256-pixel cache, never rebuilds it.
build_track_view:
.ifdef MSU_BUILD
    jmp mode7_build_track_view
.else
    stz map_scan_valid
    lda cam_x
    lsr a
    lsr a
    lsr a
    sta map_x
    lda cam_y
    lsr a
    lsr a
    lsr a
    ; BG1 is visible only between the two HUD bands. Keep a generous
    ; 24-row cache around those 160 lines, rather than decoding hidden rows.
    clc
    adc #3
    sta map_y
    sep #$20
    .a8
    lda DESC+11
    sta map_base_ptr+2
    sta map_ptr+2
    rep #$20
    .a16
    lda DESC+9
    sta map_base_ptr
    lda map_last_x
    cmp #$FFFF
    jeq @initial
    lda map_x
    sec
    sbc map_last_x
    bpl @delta_x
    eor #$FFFF
    inc a
@delta_x:
    sta camera_delta
    lda map_y
    sec
    sbc map_last_y
    bpl @delta_y
    eor #$FFFF
    inc a
@delta_y:
    clc
    adc camera_delta
    cmp #24
    jcs @initial
@horizontal:
    lda map_x
    cmp map_last_x
    beq @vertical
    bcc @left
    inc map_last_x
    lda map_last_x
    clc
    adc #31
    bra @column
@left:
    dec map_last_x
    lda map_last_x
@column:
    sta view_x
    lda map_y
    sta view_y
    lda #24
    sta view_count
@column_tile:
    jsr cache_tile
    inc view_y
    dec view_count
    bne @column_tile
    lda #1
    sta track_dirty
    bra @horizontal
@vertical:
    lda map_y
    cmp map_last_y
    beq @done
    bcc @up
    inc map_last_y
    lda map_last_y
    clc
    adc #23
    bra @row
@up:
    dec map_last_y
    lda map_last_y
@row:
    sta view_y
    jsr cache_row
    lda #1
    sta track_dirty
    bra @vertical
@done:
    jmp update_dynamic_cells
@initial:
    lda map_y
    sta view_y
    lda #24
    sta view_rows
@initial_row:
    jsr cache_row
    inc view_y
    dec view_rows
    bne @initial_row
    lda #1
    sta track_dirty
    lda map_x
    sta map_last_x
    lda map_y
    sta map_last_y
    jmp update_dynamic_cells

cache_row:
    stz map_scan_valid
    lda map_x
    sta view_x
    lda #32
    sta view_count
@tile:
    jsr cache_tile
    inc view_x
    dec view_count
    bne @tile
    rts

cache_tile:
    lda map_scan_valid
    beq @lookup
    lda view_y
    cmp map_scan_y
    bne @lookup
    lda view_x
    and #31
    beq @lookup
    lda map_scan_x
    inc a
    cmp view_x
    bne @lookup
    inc map_skip
    lda map_skip
    cmp map_run
    jcc @found
    stz map_skip
    lda map_ptr
    clc
    adc #3
    sta map_ptr
    bcc @cached_run
    sep #$20
    .a8
    inc map_ptr+2
    rep #$20
    .a16
@cached_run:
    jmp @run
@lookup:
    stz map_scan_valid
    lda view_y
    cmp map_height
    jcc @in_bounds
    jmp @empty
@in_bounds:
    asl a
    tay
    lda [map_base_ptr],y
    jsr map_offset_pointer
    lda [map_ptr]
    sta map_tile
    and #255
    sta map_skip
    lda view_x
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    sec
    sbc map_skip
    bmi @empty
    sta map_skip
    lda map_tile
    xba
    and #255
    cmp map_skip
    bcc @empty
    beq @empty
    lda map_skip
    asl a
    inc a
    inc a
    tay
    lda [map_ptr],y
    jsr map_offset_pointer
    lda view_x
    and #31
    sta map_skip
@run:
    lda [map_ptr]
    and #255
    beq @empty
    sta map_run
    lda map_skip
    cmp map_run
    bcc @found
    sec
    sbc map_run
    sta map_skip
    lda map_ptr
    clc
    adc #3
    sta map_ptr
    bcc @run
    sep #$20
    .a8
    inc map_ptr+2
    rep #$20
    .a16
    bra @run
@found:
    lda #1
    sta map_scan_valid
    ldy #1
    lda [map_ptr],y
    bra @write
@empty:
    lda #0
@write:
    pha
    lda view_x
    sta map_scan_x
    lda view_y
    sta map_scan_y
    pla
.ifdef MSU_BUILD
    jmp mode7_store_map_tile
.endif
    sta map_tile
    lda view_y
    and #31
    asl a
    asl a
    asl a
    asl a
    asl a
    asl a
    sta map_dest
    lda view_x
    and #31
    asl a
    ora map_dest
    tax
    lda map_tile
    sta f:DYNAMIC_CACHE,x
    jsr resolve_visibility
    sta TRACK,x
    lda visibility_next
    sta f:DYNAMIC_NEXT,x
    rts

.endif
map_offset_pointer:
    stz map_offset_hi
    .repeat MAP_OFFSET_SHIFT
    asl a
    rol map_offset_hi
    .endrepeat
    clc
    adc map_base_ptr
    sta map_ptr
    lda map_base_ptr+2
    and #255
    adc map_offset_hi
    sep #$20
    .a8
    sta map_ptr+2
    rep #$20
    .a16
    rts
