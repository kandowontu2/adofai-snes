; Mode 7 uses the low VRAM byte for its 128x128 map and the high byte for
; 256 colored 8x8 patterns. The HUD remains Mode 1 outside the playfield.
mode7_unpack_chr:
    ldx #0
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
    jsr mode7_store_chr_byte
    inx
    dec map_run
    bne @literal
    bra @next
@repeat:
    lda [transfer_ptr]
    inc transfer_ptr
    bne :+
    inc transfer_ptr+1
:
@run:
    jsr mode7_store_chr_byte
    inx
    dec map_run
    bne @run
@next:
    cpx DESC+20
    bcc @command
    rep #$20
    .a16
    rts

; The persistent 16 KiB pattern image is split around the note arrays.
mode7_store_chr_byte:
    cpx #14336
    bcs @high
    sta f:M7_CHR_LOW,x
    rts
@high:
    sta f:M7_CHR_HIGH-14336,x
    rts

mode7_upload_chr:
    lda #0
    sta f:M7_PREFETCH_ENABLED
    stz $2116
    lda #.loword(CHR_RAM)
    sta $4302
    lda #14336
    sta $4305
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #$19
    sta $4301
    stz $4300
    lda #$7E
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    lda #.loword(M7_CHR_HIGH)
    sta $4302
    lda #2048
    sta $4305
    sep #$20
    .a8
    lda #$7F
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    jsr mode7_clear_stage
    jmp mode7_cache_reset

; The CPU staging image mirrors every low VRAM map byte, including cells
; outside the first viewport. This lets later frames upload only changes.
mode7_clear_stage:
    lda #0
    ldx #0
@clear:
    sta f:M7_STAGE_MAP,x
    inx
    inx
    cpx #M7_STAGE_MASK+1
    bcc @clear
    stz $2116
    lda #.loword(M7_STAGE_MAP)
    sta $4302
    lda #M7_STAGE_MASK+1
    sta $4305
    sep #$20
    .a8
    stz $2115
    stz $4300
    lda #$18
    sta $4301
    lda #^M7_STAGE_MAP
    sta $4304
    lda #1
    sta $420B
    lda #$80
    sta $2115
    rep #$20
    .a16
    rts

mode7_upload_map:
    stz $2116
    lda #.loword(M7_MAP)
    sta $4302
    lda #16384
    sta $4305
    sep #$20
    .a8
    stz $2115
    stz $4300
    lda #$18
    sta $4301
    lda #.bankbyte(M7_MAP)
    sta $4304
    lda #1
    sta $420B
    lda #$80
    sta $2115
    rep #$20
    .a16
    rts

mode7_invalidate:
    lda #0
    ldx #0
@map:
    sta f:M7_MAP,x
    inx
    inx
    cpx #16384
    bcc @map
    ; Checkpoint state includes all active cells, including cells outside
    ; the first viewport that become visible during camera motion. Their
    ; values may not change again, so rebuild them now instead of waiting
    ; for an animation event to repopulate the cleared map.
    lda f:M7_GLOBAL_REFS_ACTIVE
    beq @loaded
    ldx #0
@cell:
    lda f:CELL_STATE,x
    and #255
    beq @next
    pha
    phx
    txa
    asl a
    tay
.ifdef ROM_PACKED_COORDS
    lda [visibility_index_ptr],y
.else
    lda [visibility_ptr],y
    and #127
    .repeat 7
    asl a
    .endrepeat
    sta m7_coord
    lda [visibility_index_ptr],y
    and #127
    ora m7_coord
.endif
    tay
    plx
    pla
    phx
    tyx
    sep #$20
    .a8
    sta f:M7_MAP,x
    rep #$20
    .a16
    plx
@next:
    inx
    cpx animation_cells
    bcc @cell
@loaded:
    lda #1
    sta m7_loading
    jmp mode7_clear_dirty

mode7_clear_dirty:
    lda #0
    ldx #0
@row:
    sta f:M7_DIRTY_BITS,x
    inx
    inx
    cpx #128
    bcc @row
    stz m7_row_count
    stz m7_row_span
    rts

; m7_coord is the physical 14-bit tile-map address. Record a changed span.
mode7_mark_dirty:
    pha
    phx
    lda #1
    sta f:M7_CACHE_DIRTY
    lda m7_coord
    and #127
    sta m7_row_span
    lda m7_coord
    .repeat 7
    lsr a
    .endrepeat
    tax
    lda f:M7_DIRTY_BITS,x
    and #255
    bne @existing
    sep #$20
    .a8
    lda #1
    sta f:M7_DIRTY_BITS,x
    rep #$20
    .a16
    txa
    asl a
    tax
    lda m7_row_span
    xba
    ora m7_row_span
    sta f:M7_DIRTY_BOUNDS,x
    bra @done
@existing:
    txa
    asl a
    tax
    lda f:M7_DIRTY_BOUNDS,x
    and #255
    cmp m7_row_span
    bcc :+
    sep #$20
    .a8
    lda m7_row_span
    sta f:M7_DIRTY_BOUNDS,x
    rep #$20
    .a16
:
    lda f:M7_DIRTY_BOUNDS+1,x
    and #255
    cmp m7_row_span
    bcs @done
    sep #$20
    .a8
    lda m7_row_span
    sta f:M7_DIRTY_BOUNDS+1,x
    rep #$20
    .a16
@done:
    plx
    pla
    rts

; Every cell keeps one byte of global animation state. Only a cell inside
; the cached world rectangle may update its wrapped texture address.
mode7_update_cell:
    ldx animation_index
    lda f:M7_GLOBAL_REFS_ACTIVE
    cmp #2
    beq @cell_store
    lda f:CELL_STATE,x
    and #255
    cmp animation_value
    beq @cell_store
    jsr mode7_reference_change
@cell_store:
    sep #$20
    .a8
    lda animation_value
    sta f:CELL_STATE,x
    rep #$20
    .a16
    lda animation_mode
    bne @done
    lda animation_index
    asl a
    tay
    lda [visibility_index_ptr],y
.ifndef ROM_PACKED_COORDS
    sta m7_cell_x
    lda [visibility_ptr],y
    sta m7_cell_y
    lda m7_cell_y
    and #127
    .repeat 7
    asl a
    .endrepeat
    sta m7_coord
    lda m7_cell_x
    and #127
    ora m7_coord
.endif
    sta m7_coord
    ldx m7_coord
    sep #$20
    .a8
    lda animation_value
    cmp f:M7_MAP,x
    beq @same
    sta f:M7_MAP,x
    rep #$20
    .a16
    jmp mode7_mark_dirty
@same:
    rep #$20
    .a16
@done:
    rts

; Unit matrices retain the inexpensive direct projection. Scaled/rotated
; scenes use the inverse sampling matrix on SA-1 for matching OBJ centers.
mode7_project:
.ifdef SA1_BUILD
    lda f:M7_PROJECT_COS
    cmp #256
    bne @rotate
    lda f:M7_PROJECT_SIN
    beq @native
@rotate:
    jsl mode7_rotate_project
    rts
@native:
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

mode7_orbit_position:
    lda step
    jsr floor_position
.ifdef NEO_BUILD
    jsr neo_offset_pivot
.endif
    lda floor_x
    clc
    adc orbit_x
    sta floor_x
    lda floor_y
    clc
    adc orbit_y
    sta floor_y
    jmp mode7_project

; Fixed Mode 1 HUD bands around a native-scale Mode 7 track.
mode7_prepare_view:
.ifdef SA1_BUILD
    jsl camera_projection_limits
.endif
    stz m7_window_left
    lda #255
    sta m7_window_right
    lda #32
    sta m7_vtop
    lda #175
    sta m7_vbottom
    lda #$0620
    sta M7_HDMA_STAGE
    lda #$117F
    sta M7_HDMA_STAGE+2
    lda #$1111
    sta M7_HDMA_STAGE+4
    lda #$0630
    sta M7_HDMA_STAGE+6
    stz M7_HDMA_STAGE+8
    ldx selected_level
    lda level_view_insets,x
    and #255
    beq :+
    lda #40
    sta m7_vtop
    lda #167
    sta m7_vbottom
    lda #$1628
    sta M7_HDMA_STAGE
    lda #$1101
    sta M7_HDMA_STAGE+4
    lda #$1638
    sta M7_HDMA_STAGE+6

:
 .ifdef SA1_BUILD
    jsl camera_orb_radius
 .else
    lda #7
 .endif
    sta m7_radius
    rts

mode7_draw_orb:
    stz object_small
    lda m7_radius
    cmp #9
    bcs @composite
    tax
    lda orb_size_tiles,x
    and #255
    sta sprite_tile
    cpx #5
    bcs @single
    lda #1
    sta object_small
    lda sprite_x
    clc
    adc #4
    sta sprite_x
    lda sprite_y
    clc
    adc #4
    sta sprite_y
@single:
    jsr mode7_orb_piece
    ; Four fixed OAM slots per planet keep trail visibility checks stable.
    lda oam_pos
    clc
    adc #12
    sta oam_pos
    stz object_small
    rts
@composite:
    ; Four 16x16 pieces use pre-scaled artwork: no runtime bitmap resampling.
    sec
    sbc #9
    lsr a
    asl a
    asl a
    tax
    lda sprite_x
    sec
    sbc #8
    sta sprite_x
    lda sprite_y
    sec
    sbc #8
    sta sprite_y
    lda #4
    pha
@part:
    phx
    lda orb_quad_tiles,x
    and #255
    sta sprite_tile
    jsr mode7_orb_piece
    plx
    inx
    pla
    dec a
    beq @done
    pha
    txa
    and #1
    beq @next_row
    lda sprite_x
    clc
    adc #16
    sta sprite_x
    bra @part
@next_row:
    lda sprite_x
    sec
    sbc #16
    sta sprite_x
    lda sprite_y
    clc
    adc #16
    sta sprite_y
    bra @part
@done:
    rts
orb_size_tiles: .byte 64,64,65,66,67,0,2,6,4,0
orb_quad_tiles: .byte 10,14,40,42,44,46,70,78,96,98,100,102,0

mode7_orb_piece:
    lda oam_pos
    pha
    jsr sprite
    pla
    cmp oam_pos
    bne @reserved
    tax
    sep #$20
    .a8
    lda #224
    sta OAM+1,x
    lda sprite_tile
    sta OAM+2,x
    rep #$20
    .a16
    lda oam_pos
    clc
    adc #4
    sta oam_pos
@reserved:
    rts

mode7_build_track_view:
.ifdef SA1_BUILD
    lda f:SA1_PENDING
    beq :+
    jmp sa1_cache_finish
:
    jsl mode7_rotation_bounds
.endif
.ifdef ROM_PATTERN_COUNT
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @ordinary_scroll
    lda map_last_x
    cmp #$FFFF
    beq @ordinary_scroll
    ; Fully dynamic resident charts already stream the exact wrapped map,
    ; including departing cells. Keep the initial/checkpoint reconstruction
    ; but do not decode those same exposed cells again during ordinary play.
    lda f:M7_VIEW_X
    sta map_x
    sta map_last_x
    lda f:M7_VIEW_Y
    sta map_y
    sta map_last_y
    jmp mode7_cache_prepare
@ordinary_scroll:
.endif
    stz map_scan_valid
    ; The cache is in raster coordinates, which may differ from gameplay
    ; coordinates during a wide-view mipmap epoch.
.ifdef SA1_BUILD
    lda f:M7_VIEW_X
    sta map_x
    lda f:M7_VIEW_Y
    sta map_y
    lda f:M7_VIEW_W
    sta m7_cache_width
    lda f:M7_VIEW_H
    sta m7_cache_height
.else
    ; One extra cell around the native viewport avoids decoding a large
    ; off-screen rectangle when a rapid chart moves several floors.
    lda #34
    sta m7_cache_width
    lda #18
    sta m7_cache_height
    lda cam_x
    clc
    adc #128
    jsr mode7_floor8
    sec
    sbc #17
    sta map_x
    lda cam_y
    clc
    adc #104
    jsr mode7_floor8
    sec
    sbc #9
    sta map_y
.endif
    sep #$20
    .a8
    lda DESC+11
    sta map_base_ptr+2
    sta map_ptr+2
    rep #$20
    .a16
    lda DESC+9
    sta map_base_ptr
    lda m7_loading
    jne @rows
    ; Global camera-culling events already update every nonblank world
    ; cell. Re-decoding the sparse ROM map on each scroll duplicates them.
    lda map_x
    sta map_last_x
    lda map_y
    sta map_last_y
    lda m7_cache_width
    sta m7_old_width
    lda m7_cache_height
    sta m7_old_height
    jmp mode7_cache_prepare
@rows:
    lda map_y
    sta view_y
    lda m7_cache_height
    sta view_rows
@row:
    lda m7_loading
    bne @whole_row
    lda view_y
    sec
    sbc map_last_y
    bmi @whole_row
    cmp m7_old_height
    bcs @whole_row
    ; Rows inside the old rectangle only need their newly exposed ends.
    lda map_last_x
    sec
    sbc map_x
    beq @right
    bmi @right
    cmp m7_cache_width
    bcc :+
    lda m7_cache_width
:
    sta view_count
    lda map_x
    sta view_x
    jsr mode7_cache_span
@right:
    lda map_last_x
    clc
    adc m7_old_width
    sec
    sbc map_x
    bmi @whole_row
    cmp m7_cache_width
    bcs @next_row
    sta scratch2
    lda m7_cache_width
    sec
    sbc scratch2
    sta view_count
    lda map_x
    clc
    adc scratch2
    sta view_x
    jsr mode7_cache_span
    bra @next_row
@whole_row:
    lda map_x
    sta view_x
    lda m7_cache_width
    sta view_count
    jsr mode7_cache_span
@next_row:
    jsr mode7_game_service
    inc view_y
    dec view_rows
    jne @row
    lda map_x
    sta map_last_x
    lda map_y
    sta map_last_y
    lda m7_cache_width
    sta m7_old_width
    lda m7_cache_height
    sta m7_old_height
    lda m7_loading
    beq @done
    ; The scene remains frozen while the cache is assembled. Only the
    ; final VRAM transfer needs forced blank, including checkpoint CHR.
    jsr mode7_finish_snapshot
    sep #$20
    .a8
    lda #$80
    sta $2100
    rep #$20
    .a16
    lda #1
    sta pattern_blanked
    stz m7_loading
    jmp mode7_cache_prepare
@done:
    jmp mode7_cache_prepare

; Decode each sparse RLE span once, rather than looking it up per pixel.
; Blank runs copy words; only changed bytes enter the VBlank dirty list.
; At increased speed, graphics may need several input polls. Service the
; timestamped game queue at safe animation/row boundaries while retaining
; this frame's visual clock and the register/scratch values of its caller.
mode7_game_service:
    jsr audio_pump
    ; Animation runs before OAM is built. Service there, so a failed input
    ; can retain the last complete scene. Once OAM/camera staging begins,
    ; defer game-state changes until the bounded map update has finished.
    lda profile_phase
    cmp #3
    bne @done
    lda speed_tenths
    cmp #11
    bcc @done
    lda tick
    cmp m7_service_tick
    beq @done
    sta m7_service_tick
    lda music_active
    beq @done
    lda state
    cmp #1
    bne @done
    phx
    phy
    lda chart_time
    pha
    lda chart_frac
    pha
    lda pressed
    pha
    lda scratch
    pha
    lda scratch2
    pha
    stz pressed
    jsr update_game
    lda step
    sta m7_logical_step
    lda #1
    sta animation_seek_dirty
    pla
    sta scratch2
    pla
    sta scratch
    pla
    sta pressed
    pla
    sta chart_frac
    pla
    sta chart_time
    ply
    plx
@done:
    rts

mode7_cache_span:
    jsr audio_pump
    lda view_y
    and #127
    .repeat 7
    asl a
    .endrepeat
    sta m7_coord
    lda view_x
    and #127
    ora m7_coord
    sta m7_coord
    ; Newly exposed cells must publish even when their logical byte is
    ; unchanged: the physical slot may have changed while offscreen.
    jsr mode7_mark_dirty
    lda m7_coord
    pha
    and #127
    clc
    adc view_count
    dec a
    cmp #128
    bcc @last_exposed
    lda m7_coord
    ora #127
    sta m7_coord
    jsr mode7_mark_dirty
    lda m7_coord
    and #$3F80
    sta m7_coord
    jsr mode7_mark_dirty
    bra @exposed_done
@last_exposed:
    and #127
    sta m7_row_key
    lda m7_coord
    and #$3F80
    ora m7_row_key
    sta m7_coord
    jsr mode7_mark_dirty
@exposed_done:
    pla
    sta m7_coord
@chunk:
    lda view_x
    and #31
    sta map_skip
    lda #32
    sec
    sbc map_skip
    cmp view_count
    bcc :+
    lda view_count
:
    sta map_scan_x
    lda view_y
    cmp map_height
    jcs @empty
    asl a
    tay
    lda [map_base_ptr],y
    jsr map_offset_pointer
    lda [map_ptr]
    sta map_tile
    and #255
    sta map_left
    lda view_x
    .repeat 5
    lsr a
    .endrepeat
    sec
    sbc map_left
    bpl :+
    jmp @empty
:
    sta map_left
    lda map_tile
    xba
    and #255
    cmp map_left
    jcc @empty
    jeq @empty
    lda map_left
    asl a
    inc a
    inc a
    tay
    lda [map_ptr],y
    jsr map_offset_pointer
@run:
    lda [map_ptr]
    and #255
    jeq @empty
    sta map_run
    lda map_skip
    cmp map_run
    bcc @selected
    sec
    sbc map_run
    sta map_skip
    jsr mode7_next_rle
    bra @run
@selected:
    lda map_run
    sec
    sbc map_skip
    cmp map_scan_x
    bcc :+
    lda map_scan_x
:
    sta map_run
    stz map_skip
    ldy #1
    lda [map_ptr],y
    sta map_tile
    jsr mode7_next_rle
    lda map_tile
    bit #$2000
    beq @physical
    and #$C000
    lsr a
    sta map_left
    lda map_tile
    and #$1FFF
    ora map_left
    tax
    lda f:CELL_STATE,x
@physical:
    and #255
    sta map_tile
    bra @emit
@empty:
    lda map_scan_x
    sta map_run
    stz map_tile
@emit:
    lda map_run
    sta map_row
    lda map_tile
    xba
    ora map_tile
    sta map_scan_y
    ldx m7_coord
@word:
    lda map_run
    cmp #2
    bcc @last_byte
    lda map_scan_y
    cmp f:M7_MAP,x
    beq @same_word
    sta f:M7_MAP,x
    stx m7_coord
    jsr mode7_mark_dirty
    inc m7_coord
    jsr mode7_mark_dirty
    ldx m7_coord
    dex
@same_word:
    inx
    inx
    dec map_run
    dec map_run
    bra @word
@last_byte:
    cmp #0
    beq @emitted
    sep #$20
    .a8
    lda map_tile
    cmp f:M7_MAP,x
    beq @same_byte
    sta f:M7_MAP,x
    rep #$20
    .a16
    stx m7_coord
    jsr mode7_mark_dirty
    ldx m7_coord
    bra @byte_end
@same_byte:
    rep #$20
    .a16
@byte_end:
    inx
@emitted:
    txa
    and #127
    bne :+
    txa
    sec
    sbc #128
    tax
:
    stx m7_coord
    lda view_x
    clc
    adc map_row
    sta view_x
    lda view_count
    sec
    sbc map_row
    sta view_count
    jeq @done
    lda map_scan_x
    sec
    sbc map_row
    sta map_scan_x
    jne @run
    jmp @chunk
@done:
    rts

mode7_next_rle:
    lda map_ptr
    clc
    adc #3
    sta map_ptr
    bcc @done
    sep #$20
    .a8
    inc map_ptr+2
    rep #$20
    .a16
@done:
    rts

; Pattern downloads never block floor motion or zoom events. A persistent
; image and a deadline heap let VBlank drain prefetched slots safely.
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

.if 0
mode7_enqueue_pattern:
    lda animation_index
    sta m7_pattern_tail
    asl a
    tax
    lda f:M7_PATTERN_POSITION,x
    cmp #$FFFF
    bne @existing
    lda m7_pattern_count
    inc m7_pattern_count
@existing:
    sta m7_pattern_head
    jsr mode7_heap_up
    jmp mode7_heap_down

mode7_heap_store:
    lda m7_pattern_head
    asl a
    tax
    lda m7_pattern_tail
    sta f:M7_PATTERN_HEAP,x
    asl a
    tax
    lda m7_pattern_head
    sta f:M7_PATTERN_POSITION,x
    rts

mode7_heap_up:
@next:
    lda m7_pattern_head
    beq @done
    dec a
    lsr a
    sta m7_run_index
    asl a
    tax
    lda f:M7_PATTERN_HEAP,x
    sta scratch
    lda m7_pattern_tail
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    sta scratch2
    lda scratch
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    cmp scratch2
    bcc @done
    beq @done
    lda m7_pattern_head
    sta f:M7_PATTERN_POSITION,x
    asl a
    tax
    lda scratch
    sta f:M7_PATTERN_HEAP,x
    lda m7_run_index
    sta m7_pattern_head
    bra @next
@done:
    jmp mode7_heap_store

mode7_heap_down:
@next:
    lda m7_pattern_head
    asl a
    inc a
    sta m7_run_index
    cmp m7_pattern_count
    bcs @done
    asl a
    tax
    lda f:M7_PATTERN_HEAP,x
    sta scratch
    lda m7_run_index
    inc a
    cmp m7_pattern_count
    bcs @chosen
    asl a
    tax
    lda f:M7_PATTERN_HEAP,x
    sta scratch2
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    sta math_a
    lda scratch
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    cmp math_a
    bcc @chosen
    beq @chosen
    inc m7_run_index
    lda scratch2
    sta scratch
@chosen:
    lda scratch
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    sta scratch2
    lda m7_pattern_tail
    asl a
    tax
    lda f:M7_PATTERN_DEADLINE,x
    cmp scratch2
    bcc @done
    beq @done
    lda scratch
    asl a
    tax
    lda m7_pattern_head
    sta f:M7_PATTERN_POSITION,x
    asl a
    tax
    lda scratch
    sta f:M7_PATTERN_HEAP,x
    lda m7_run_index
    sta m7_pattern_head
    bra @next
@done:
    jmp mode7_heap_store

.endif
mode7_visible_patterns:
    ; Dataset 11 maintains its camera-visible pattern set incrementally.
    rts

.if 0
mode7_prepare_patterns:
    jsr mode7_visible_patterns
    lda #6
    sta profile_phase
    stz pattern_queue_count
    stz m7_upload_slots
    ; VBlank capacity depends on this frame's map transfer, not song speed.
    ; Capping faster playback at twelve slots let new map cells reference
    ; graphics which were still waiting in the upload heap.
    lda #16
    sta m7_pattern_budget
    lda m7_row_count
    .repeat 4
    asl a
    .endrepeat
    sta scratch
    asl a
    clc
    adc scratch
    clc
    adc m7_row_span
    cmp #1825
    bcs @budget_ready
    cmp #1153
    bcc @thirty_two
    lda #24
    sta m7_pattern_budget
    bra @budget_ready
@thirty_two:
    lda #32
    sta m7_pattern_budget
@budget_ready:
    lda m7_pattern_count
    bne @next
    rts
@next:
    ; The sparse map decoder has finished with these two words. Bound the
    ; subsequent physical-slot scan to the entries selected for this DMA.
    lda #256
    sta map_scan_x
    stz map_scan_y
    stz pattern_hi
@visible:
    ldx pattern_hi
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    beq @visible_next
    txa
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp f:M7_PATTERN_VRAM,x
    beq @visible_next
    lda m7_upload_slots
    cmp m7_pattern_budget
    bcs @visible_next
    lda f:PATTERN_CURRENT,x
    sta f:M7_PATTERN_VRAM,x
    ldx pattern_hi
    cpx map_scan_x
    bcs :+
    stx map_scan_x
:
    cpx map_scan_y
    bcc :+
    stx map_scan_y
:
    sep #$20
    .a8
    lda #1
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    inc m7_upload_slots
@visible_next:
    inc pattern_hi
    lda pattern_hi
    cmp #256
    bcc @visible
@select:
    lda m7_pattern_count
    jeq @scan_begin
    lda m7_upload_slots
    cmp m7_pattern_budget
    jcs @scan_begin
    lda f:M7_PATTERN_HEAP
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp f:M7_PATTERN_VRAM,x
    beq @remove_word
    sta f:M7_PATTERN_VRAM,x
    txa
    lsr a
    tax
    cpx map_scan_x
    bcs :+
    stx map_scan_x
:
    cpx map_scan_y
    bcc :+
    stx map_scan_y
:
    sep #$20
    .a8
    lda #1
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    inc m7_upload_slots
@remove:
    txa
    asl a
    tax
@remove_word:
    lda #$FFFF
    sta f:M7_PATTERN_POSITION,x
    dec m7_pattern_count
    lda m7_pattern_count
    beq @selected
    asl a
    tax
    lda f:M7_PATTERN_HEAP,x
    sta m7_pattern_tail
    stz m7_pattern_head
    jsr mode7_heap_down
@selected:
    jmp @select
@scan_begin:
    lda m7_upload_slots
    jeq @patterns_done
    lda #$FFFF
    sta pattern_raw
    lda map_scan_x
    sta pattern_hi
@scan:
    ldx pattern_hi
    lda M7_PATTERN_SELECTED,x
    and #255
    jeq @scan_next
    sep #$20
    .a8
    lda #0
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    lda pattern_raw
    inc a
    cmp pattern_hi
    bne @new_run
    lda pattern_queue_count
    beq @new_run
    lda pattern_hi
    cmp #224
    beq @new_run
    lda pattern_queue_count
    dec a
    .repeat 4
    asl a
    .endrepeat
    tax
    lda f:PATTERN_QUEUE+6,x
    clc
    adc #64
    sta f:PATTERN_QUEUE+6,x
    bra @scanned
@new_run:
    lda pattern_hi
    jsr mode7_pattern_destination
    lda pattern_queue_count
    .repeat 4
    asl a
    .endrepeat
    tax
    lda transfer_dest
    sta f:PATTERN_QUEUE,x
    lda transfer_wbank
    clc
    adc #$7E
    sta f:PATTERN_QUEUE+2,x
    lda pattern_hi
    .repeat 6
    asl a
    .endrepeat
    sta f:PATTERN_QUEUE+4,x
    lda #64
    sta f:PATTERN_QUEUE+6,x
    inc pattern_queue_count
@scanned:
    lda pattern_hi
    sta pattern_raw
@scan_next:
    inc pattern_hi
    lda pattern_hi
    cmp map_scan_y
    jcc @scan
    jeq @scan
    lda m7_upload_slots
    cmp pattern_peak_queued
    bcc :+
    sta pattern_peak_queued
:
@patterns_done:
    rts

; Upload visible chunks. Unseen changes remain dirty until a pan or zoom
; reveals them, leaving VBlank time for prefetched pattern data.
mode7_prepare_dma:
    lda #5
    sta profile_phase
    stz m7_row_count
    stz m7_row_span
    stz view_rows
    lda camera_zoom
    jeq @done
    bpl :+
    eor #$FFFF
    inc a
:
    sta math_a
    lsr a
    clc
    adc #8
    cmp #505
    bcc :+
    lda #504
:
    sta math_b
    lda cam_x
    clc
    adc #128
    sec
    sbc math_b
    jsr mode7_floor128
    sta view_x
    lda cam_x
    clc
    adc #128
    clc
    adc math_b
    jsr mode7_floor128
    sec
    sbc view_x
    inc a
    sta map_left
    stz m7_cache_key
@xmask:
    lda view_x
    and #7
    tax
    lda mode7_bit_masks,x
    and #255
    ora m7_cache_key
    sta m7_cache_key
    inc view_x
    dec map_left
    bne @xmask
    lda math_a
    lsr a
    lsr a
    clc
    adc #8
    cmp #505
    bcc :+
    lda #504
:
    sta math_b
    lda cam_y
    clc
    adc #104
    sec
    sbc math_b
    jsr mode7_floor8
    sta view_y
    lda cam_y
    clc
    adc #104
    clc
    adc math_b
    jsr mode7_floor8
    sec
    sbc view_y
    inc a
    cmp #129
    bcc :+
    lda #128
:
    sta view_count
    jsr mode7_collect_rows
@done:
    rts

.endif
mode7_floor128:
    .repeat 4
    cmp #$8000
    ror a
    .endrepeat
mode7_floor8:
    .repeat 3
    cmp #$8000
    ror a
    .endrepeat
    rts

.if 0
mode7_collect_rows:
@row:
    lda view_y
    and #127
    sta m7_row_key
    tax
    lda f:M7_DIRTY_BITS,x
    and #255
    and m7_cache_key
    beq @next
    jsr mode7_collect_spans
@next:
    inc view_y
    dec view_count
    bne @row
    rts

mode7_collect_spans:
    sta map_tile
    stz view_x
@chunk:
    ldx view_x
    lda mode7_bit_masks,x
    and #255
    and map_tile
    bne @start
    inc view_x
    lda view_x
    cmp #8
    bcc @chunk
    rts
@start:
    lda view_x
    sta map_dest
    stz map_run
@extend:
    ldx view_x
    lda mode7_bit_masks,x
    and #255
    ora map_run
    sta map_run
    inc view_x
    lda view_x
    cmp #8
    beq @run
    tax
    lda mode7_bit_masks,x
    and #255
    and map_tile
    bne @extend
@run:
    lda view_x
    .repeat 4
    asl a
    .endrepeat
    sta transfer_len
    lda map_dest
    .repeat 4
    asl a
    .endrepeat
    sta map_dest
    lda m7_row_key
    asl a
    tax
    lda f:M7_DIRTY_BOUNDS,x
    sta scratch2
    and #255
    cmp map_dest
    bcc :+
    sta map_dest
:
    lda scratch2
    xba
    and #255
    inc a
    cmp transfer_len
    bcs :+
    sta transfer_len
:
    lda transfer_len
    sec
    sbc map_dest
    sta transfer_len
    clc
    adc m7_row_span
    cmp #1025
    bcs @defer
    sta transfer_dest
    lda m7_row_count
    cmp #64
    bcs @defer
    asl a
    asl a
    tax
    lda transfer_len
    sta f:M7_DMA_LIST+2,x
    lda map_dest
    sta scratch
    lda m7_row_key
    .repeat 7
    asl a
    .endrepeat
    ora scratch
    sta f:M7_DMA_LIST,x
    inc m7_row_count
    lda transfer_dest
    sta m7_row_span
    lda map_run
    eor #255
    sta scratch
    ldx m7_row_key
    sep #$20
    .a8
    lda f:M7_DIRTY_BITS,x
    and scratch
    sta f:M7_DIRTY_BITS,x
    rep #$20
    .a16
    lda view_x
    cmp #8
    jcc @chunk
    rts
@defer:
    lda view_rows
    bne @done
    inc m7_map_deferrals
@done:
    rts
.endif
.segment "RODATA"
mode7_bit_masks: .byte 1,2,4,8,16,32,64,128
hdma_mode7: .byte 32,9,127,7,17,7,48,9,0
hdma_mode7_inset: .byte 40,9,127,7,1,7,56,9,0
hdma_mode1: .byte 127,9,97,9,0
.segment "CODE"

.ifdef SA1_BUILD
.include "rotation.inc"
.endif
