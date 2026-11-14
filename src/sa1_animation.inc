.ifdef ROM_NATIVE_ADDR
; The stream is byte-identical in length to the canonical MSU stream.
; C0/D0 temporarily form a contiguous two-MiB reader. D0 is restored
; before completion; F0 audio and the low-bank executable remain mapped.
native_time=map_x
native_kind=map_y
native_index=view_x
native_value=view_y
native_count=map_left
native_coord=scratch2

.ifdef SA1_STREAM_BUILD
worker_stream_animation:
    lda #1
    sta f:STREAM_DECODING
    bra worker_animation_start
.endif
worker_native_animation:
.ifdef SA1_STREAM_BUILD
    lda #0
    sta f:STREAM_DECODING
.endif
worker_animation_start:
    lda #0
.ifdef SA1_STREAM_BUILD
    sta f:STREAM_SPILL_DIRECT
    sta f:STREAM_PATTERN_DIRECT
    sta f:STREAM_OAM_DIRECT
    dec a
    sta f:STREAM_SPILL_BASE_ID
    inc a
.endif
    sta f:NATIVE_PALETTE_DIRTY
    sta f:NATIVE_ALPHA_DIRTY
    sta f:NATIVE_ALPHA_END
    dec a
    sta f:NATIVE_ALPHA_BEGIN
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_DECODING
    beq :+
    lda #.loword(STREAM_BUFFER)
    sta transfer_ptr
    lda #^STREAM_BUFFER
    sta transfer_ptr+2
    jmp @record
:
.endif
    lda f:NATIVE_OFFSET
    clc
    adc #.loword(ROM_NATIVE_ADDR)
    sta transfer_ptr
    lda f:NATIVE_OFFSET+2
    adc #.bankbyte(ROM_NATIVE_ADDR)
    sta transfer_ptr+2
    jsr worker_paged_pointer
    lda ROM_SOURCE_PAGE
    sta NATIVE_SOURCE_PAGE
    ora #$0100
    jsr worker_select_rom_bank
    lda #.loword(ROM_NATIVE_COORDS)
    sta map_base_ptr
.ifndef ROM_PACKED_COORDS
    clc
    adc #ROM_NATIVE_CELLS*2
    sta map_ptr
    lda #.bankbyte(ROM_NATIVE_COORDS)
    adc #0
    sep #$20
    .a8
    sta map_ptr+2
.else
    sep #$20
    .a8
.endif
    lda #.bankbyte(ROM_NATIVE_COORDS)
    sta map_base_ptr+2
    rep #$20
    .a16
@record:
    lda [transfer_ptr]
    cmp #$FFFF
    jeq @done
    cmp f:NATIVE_TARGET
    beq @header
    jcs @done
@header:
    sta native_time
    ldy #2
    lda [transfer_ptr],y
    and #255
    sta native_kind
    iny
    lda [transfer_ptr],y
    sta native_index
    iny
    iny
    lda [transfer_ptr],y
    sta native_value
    lda #7
    jsr worker_native_advance
    lda native_kind
    cmp #45
    jcs @bad_kind
    asl a
    tax
    jmp (@handlers,x)
@handlers:
    .word @cell,@alpha,@x,@y,@pattern,@bad_kind,@zoom,@color
    .word @colors,@spatial,@camera,@rotation,@references,@phase,@active,@projection
    .word @bad_kind,@bulk_x,@bulk_y,@bulk_alpha,@bad_kind,@bad_kind,@spill
    .word @origin,@bad_kind,@tags,@bad_kind,@tag,@symbols,@sparse
.ifdef SA1_MODE1_BUILD
    .word @mode1,@mode1map,@direct_spill,@direct_patterns,@bulk_patterns,@spill_delta,@map_rows,@mode1inline
    .word @bad_kind,@mode1priority
    .word @bad_kind,@mode1snapshot
    .word @mode1snapshot_reference
    .word @camera_copies
    .word @mode1snapshot
@camera_copies:
    lda native_index
    cmp #5
    jcs @bad_kind
    sta f:CLONE_COUNT
    lda native_value
    beq @copies_done
    ldx #0
@copies_data:
    txy
    lda [transfer_ptr],y
    sta f:CLONE_PARAMS,x
    inx
    inx
    cpx native_value
    bcc @copies_data
@copies_done:
    lda native_value
    jsr worker_native_advance
    jmp @record
@mode1snapshot_reference:
    lda native_value
    sta f:M1_SNAPSHOT_PENDING
    lda [transfer_ptr]
    sta f:M1_SNAPSHOT_OFFSET
    ldy #2
    lda [transfer_ptr],y
    sta f:M1_SNAPSHOT_OFFSET+2
    lda #4
    jsr worker_native_advance
    jmp @record
@mode1snapshot:
    jsr worker_snapshot_packet
    jmp @record
@mode1priority:
    jsr worker_projected_priority
    jmp @record
@mode1inline:
    jsr worker_mode1_inline_packet
    jmp @record
@mode1map:
    jsr worker_mode1_map_packet
    jmp @record
@mode1:
    jsr worker_mode1_packet
    jmp @record
.else
    .word @bad_kind,@bad_kind,@direct_spill,@direct_patterns,@bulk_patterns,@spill_delta,@map_rows,@bad_kind
    .word @bad_kind,@bad_kind
    .word @bad_kind,@bad_kind
    .word @bad_kind
    .word @bad_kind
    .word @bad_kind
.endif
@map_rows:
.ifdef SA1_STREAM_BUILD
    lda native_index
    sta m7_run_index
@map_row:
    ldy #2
    lda [transfer_ptr],y
    sta native_value
    lda transfer_ptr
    clc
    adc #4
    sta transfer_ptr
    lda [transfer_ptr]
    and #127
    sta scratch
    ldy #2
    lda [transfer_ptr],y
    and #127
    .repeat 7
    asl a
    .endrepeat
    ora scratch
    sta native_coord
    jsr worker_stream_map_row
    lda native_value
    clc
    adc #4
    clc
    adc transfer_ptr
    sta transfer_ptr
    dec m7_run_index
    bne @map_row
    jmp @record
.else
    jmp @bad_kind
.endif
@bulk_patterns:
.ifdef SA1_STREAM_BUILD
    lda native_index
    sta native_count
    asl a
    asl a
    asl a
    clc
    adc transfer_ptr
    sta native_coord
    ldy #0
@bulk_pattern:
    lda [transfer_ptr],y
    asl a
    tax
    iny
    iny
    lda [transfer_ptr],y
    sta f:PATTERN_CURRENT,x
    sta f:STREAM_DELTA_TARGET,x
    iny
    iny
    lda [transfer_ptr],y
    sta f:STREAM_DELTA_BASE,x
    iny
    iny
    lda [transfer_ptr],y
    sta f:STREAM_DELTA_SPAN,x
    iny
    iny
    lda f:STREAM_PATTERN_DIRECT
    bne @bulk_pattern_next
    phy
    txa
    .repeat 5
    asl a
    .endrepeat
    tay
    ldx native_coord
    phb
    lda #63
    mvn #$42,#$43
    plb
    ply
@bulk_pattern_next:
    lda native_coord
    clc
    adc #64
    sta native_coord
    dec native_count
    bne @bulk_pattern
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
    lda native_value
    jsr worker_native_advance
    jmp @record
.else
    jmp @bad_kind
.endif
@spill_delta:
.ifdef SA1_STREAM_BUILD
    lda native_index
    sta f:STREAM_SPILL_BASE_ID
    lda native_value
    sta f:STREAM_SPILL_DELTA_BYTES
    lda [transfer_ptr]
    sta f:STREAM_SPILL_DELTA_START
    lda #2
    jsr worker_native_advance
    jmp @record
.else
    jmp @bad_kind
.endif
@direct_patterns:
.ifdef SA1_STREAM_BUILD
    lda #1
    sta f:STREAM_PATTERN_DIRECT
    ; Older direct packets contain only CHR routes. Detect the OAM route
    ; explicitly so they still use the packed-position copy fallback.
    lda native_value
    sec
    sbc #2
    tay
@oam_route:
    lda [transfer_ptr],y
    cmp #.loword(SPILL_OAM_OUT)
    beq @has_oam
    tya
    sec
    sbc #6
    tay
    bpl @oam_route
    bra @routes_done
@has_oam:
    lda #1
    sta f:STREAM_OAM_DIRECT
@routes_done:
    lda native_value
    jsr worker_native_advance
.endif
@direct_spill:
.ifdef SA1_STREAM_BUILD
    lda #1
    sta f:STREAM_SPILL_DIRECT
    jmp @record
.else
    jmp @bad_kind
.endif
@spill:
.ifdef SA1_STREAM_BUILD
    jsr worker_stream_spill_packet
    jmp @record
.else
    jmp @bad_kind
.endif
@tags:
    ldy #0
@tag_item:
    lda [transfer_ptr],y
    asl a
    tax
    iny
    iny
    lda [transfer_ptr],y
    sta f:PATTERN_CURRENT,x
    txa
    lsr a
    tax
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    beq :+
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
:
    iny
    iny
    cpy native_value
    bcc @tag_item
    tya
    jsr worker_native_advance
    jmp @record
@pattern:
.ifdef SA1_STREAM_BUILD
    lda native_index
    asl a
    tax
    lda [transfer_ptr]
    sta f:STREAM_DELTA_BASE,x
    ldy #2
    lda [transfer_ptr],y
    sta f:STREAM_DELTA_SPAN,x
    lda native_value
    sta f:STREAM_DELTA_TARGET,x
    lda f:STREAM_PATTERN_DIRECT
    jne @pixels_ready
    lda native_index
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(STREAM_CHR)
    tay
    lda transfer_ptr
    clc
    adc #4
    tax
    phb
    pea $4343
    plb
    plb
    .repeat 32, word
    lda f:$420000+word*2,x
    sta word*2,y
    .endrepeat
    plb
@pixels_ready:
    lda #68
    jsr worker_native_advance
    lda native_index
    asl a
    tax
    lda native_value
    sta f:PATTERN_CURRENT,x
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
    jmp @record
.else
    jmp @bad_kind
.endif
@sparse:
.ifdef SA1_STREAM_BUILD
    lda native_index
    sta native_count
    ldy #2
@sparse_cell:
    lda [transfer_ptr],y
    sta native_coord
    iny
    iny
    lda [transfer_ptr],y
    and #255
    jsr worker_native_cell
    iny
    iny
    iny
    dec native_count
    bne @sparse_cell
    lda native_value
    jsr worker_native_advance
    jmp @record
.else
    jmp @bad_kind
.endif
@cell:
    lda native_index
    asl a
    tay
    lda [map_base_ptr],y
.ifndef ROM_PACKED_COORDS
    and #127
    sta scratch
    lda [map_ptr],y
    and #127
    .repeat 7
    asl a
    .endrepeat
    ora scratch
.endif
    sta native_coord
    lda native_value
    jsr worker_native_cell
    jmp @record
@alpha:
    ldx native_index
    lda native_value
    sep #$20
    .a8
    cmp f:NATIVE_ALPHA,x
    beq @alpha_done
    sta f:NATIVE_ALPHA,x
    rep #$20
    .a16
    lda #1
    sta f:NATIVE_ALPHA_DIRTY
    txa
    cmp f:NATIVE_ALPHA_BEGIN
    bcs @alpha_begin_ok
    sta f:NATIVE_ALPHA_BEGIN
@alpha_begin_ok:
    inc a
    cmp f:NATIVE_ALPHA_END
    bcc @alpha_done
    sta f:NATIVE_ALPHA_END
@alpha_done:
    rep #$20
    .a16
    jmp @record
@x:
    lda native_index
    asl a
    tax
    lda native_value
    sta f:SYMBOL_X,x
    jmp @record
@bulk_x:
    lda #.loword(SYMBOL_X)
    bra @bulk_coordinate
@bulk_y:
    lda #.loword(SYMBOL_Y)
@bulk_coordinate:
.ifdef SA1_STREAM_BUILD
    sta native_coord
    lda native_index
    asl a
    clc
    adc native_coord
    tay
    ldx transfer_ptr
    phb
    lda native_value
    asl a
    dec a
    mvn #.bankbyte(STREAM_BUFFER),#.bankbyte(SYMBOL_X)
    plb
@bulk_advance:
    lda native_value
    dec a
    sta native_count
    asl a
    asl a
    asl a
    sec
    sbc native_count
    jsr worker_native_advance
    jmp @record
.else
    jmp @bad_kind
.endif
@bulk_alpha:
.ifdef SA1_STREAM_BUILD
    lda #1
    sta f:NATIVE_ALPHA_DIRTY
    lda native_index
    cmp f:NATIVE_ALPHA_BEGIN
    bcs :+
    sta f:NATIVE_ALPHA_BEGIN
:
    clc
    adc native_value
    cmp f:NATIVE_ALPHA_END
    bcc :+
    sta f:NATIVE_ALPHA_END
:
    lda native_index
    clc
    adc #.loword(NATIVE_ALPHA)
    tay
    ldx transfer_ptr
    lda native_value
    dec a
    phb
    mvn #.bankbyte(STREAM_BUFFER),#.bankbyte(NATIVE_ALPHA)
    plb
    jmp @bulk_advance
.else
    jmp @bad_kind
.endif
@y:
    lda native_index
    asl a
    tax
    lda native_value
    sta f:SYMBOL_Y,x
    jmp @record
@zoom:
    lda native_index
    sta f:NATIVE_ZOOM
    lda native_value
    sta f:NATIVE_INVERSE
    jmp @record
@color:
    lda native_index
    asl a
    tax
    lda native_value
    jsr worker_native_color
    jmp @record
@colors:
    lda native_value
    sta native_count
    ldy #0
@color_item:
    lda [transfer_ptr],y
    and #255
    asl a
    tax
    iny
    lda [transfer_ptr],y
    jsr worker_native_color
    iny
    iny
    dec native_count
    bne @color_item
    tya
    jsr worker_native_advance
    jmp @record
@spatial:
    lda [transfer_ptr]
    and #127
    sta scratch
    ldy #2
    lda [transfer_ptr],y
    and #127
    .repeat 7
    asl a
    .endrepeat
    ora scratch
    sta native_coord
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_DECODING
    beq @spatial_scalar
    lda native_value
    cmp #2
    bcc @spatial_scalar
    clc
    adc scratch
    cmp #129
    bcs @spatial_scalar
    jsr worker_stream_map_row
    lda native_value
    clc
    adc #4
    jsr worker_native_advance
    jmp @record
@spatial_scalar:
.endif
    lda native_value
    sta native_count
    ldy #4
@spatial_cell:
    lda [transfer_ptr],y
    and #255
    jsr worker_native_cell
    iny
    inc native_coord
    lda native_coord
    and #127
    bne :+
    lda native_coord
    sec
    sbc #128
    sta native_coord
:
    dec native_count
    bne @spatial_cell
    tya
    jsr worker_native_advance
    jmp @record
@camera:
    lda native_index
    sta f:NATIVE_CAMERA_X
    lda native_value
    sta f:NATIVE_CAMERA_Y
    jmp @record
@rotation:
    lda native_index
    sta f:M7_ROT_COS
    sta f:M7_PROJECT_COS
    lda native_value
    sta f:M7_ROT_SIN
    sta f:M7_PROJECT_SIN
    jmp @record
@references:
    lda native_value
    sta f:M7_GLOBAL_REFS_ACTIVE
    jmp @record
@phase:
    lda native_index
    sta f:M7_ROT_PHASE
    jmp @record
@active:
    lda native_value
    sta f:M7_CACHE_ACTIVE_COUNT
    ldy #0
    sep #$20
    .a8
@active_slot:
    tyx
    lda [transfer_ptr],y
    sta f:M7_VISIBLE_LIST,x
    iny
    cpy native_value
    bcc @active_slot
    rep #$20
    .a16
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
    lda #2
    sta f:M7_GLOBAL_REFS_ACTIVE
    tya
    jsr worker_native_advance
    jmp @record
@projection:
    lda native_index
    sta f:M7_PROJECT_COS
    lda native_value
    sta f:M7_PROJECT_SIN
    jmp @record
@origin:
    lda native_index
    sta f:M7_ORIGIN_X
    lda native_value
    sta f:M7_ORIGIN_Y
    jmp @record
@tag:
    lda native_index
    asl a
    tax
    lda native_value
    sta f:PATTERN_CURRENT,x
    ldx native_index
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    beq :+
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
:
    jmp @record
@symbols:
    lda native_value
    sta f:NATIVE_SYMBOL_BYTES
    beq @symbol_done
    ldy #0
@symbol_item:
    tyx
    lda [transfer_ptr],y
    sta f:TRACK_SYMBOL_FLOORS,x
    iny
    iny
    cpy native_value
    bcc @symbol_item
    tya
    jsr worker_native_advance
@symbol_done:
    jmp @record
@bad_kind:
    lda f:M7_CACHE_ERRORS
    inc a
    sta f:M7_CACHE_ERRORS
@done:
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_DECODING
    beq :+
    lda #1
    jsr worker_select_rom_bank
    rts
:
.endif
    lda NATIVE_SOURCE_PAGE
    dec a
    .repeat 4
    asl a
    .endrepeat
    sta scratch
    lda transfer_ptr+2
    and #15
    clc
    adc scratch
    sta scratch
    lda transfer_ptr
    sec
    sbc #.loword(ROM_NATIVE_ADDR)
    sta f:NATIVE_RESULT
    lda scratch
    sbc #.bankbyte(ROM_NATIVE_ADDR)
    sta f:NATIVE_RESULT+2
    ; Restore the ordinary D0 static-asset window before waking the CPU.
    lda NATIVE_SOURCE_PAGE
    jsr worker_select_rom_bank
    rts

; A=payload length. Paired C0/D0 mappings also cover indexed reads across
; the end of the current MiB; only record boundaries move the window.
worker_native_advance:
.ifdef SA1_STREAM_BUILD
    pha
    lda f:STREAM_DECODING
    beq @rom_advance
    pla
    clc
    adc transfer_ptr
    sta transfer_ptr
    rts
@rom_advance:
    pla
.endif
    clc
    adc transfer_ptr
    sta transfer_ptr
    bcc @done
    sep #$20
    .a8
    inc transfer_ptr+2
    lda transfer_ptr+2
    cmp #$D0
    bcc @wide_done
    lda #$C0
    sta transfer_ptr+2
    rep #$20
    .a16
    inc NATIVE_SOURCE_PAGE
    lda NATIVE_SOURCE_PAGE
    ora #$0100
    jsr worker_select_rom_bank
    rts
@wide_done:
    rep #$20
    .a16
@done:
    rts

worker_native_color:
    cmp f:NATIVE_PALETTE,x
    beq @done
    sta f:NATIVE_PALETTE,x
.ifdef SA1_MODE1_BUILD
    lda #1
    sta f:M1_READY
.endif
    txa
    inc a
    inc a
    cmp f:NATIVE_PALETTE_DIRTY
    bcc @done
    sta f:NATIVE_PALETTE_DIRTY
@done:
    rts

.ifdef SA1_STREAM_BUILD
; A contiguous packet row needs one dirty-range update, not one per pixel.
; The caller checks the 128-cell boundary; all authored bytes are retained.
worker_stream_map_row:
    lda scratch
    clc
    adc native_value
    dec a
    sta native_count
    lda #1
    sta f:M7_CACHE_DIRTY
    lda native_coord
    asl a
    xba
    and #127
    tax
    sep #$20
    .a8
    lda f:M7_DIRTY_BITS,x
    bne @merge
    lda #1
    sta f:M7_DIRTY_BITS,x
    rep #$20
    .a16
    txa
    asl a
    tax
    lda native_count
    xba
    ora scratch
    sta f:M7_DIRTY_BOUNDS,x
    bra @copy
@merge:
    rep #$20
    .a16
    txa
    asl a
    tax
    sep #$20
    .a8
    lda scratch
    cmp f:M7_DIRTY_BOUNDS,x
    bcs :+
    sta f:M7_DIRTY_BOUNDS,x
:
    lda native_count
    cmp f:M7_DIRTY_BOUNDS+1,x
    bcc :+
    sta f:M7_DIRTY_BOUNDS+1,x
:
    rep #$20
    .a16
@copy:
    lda native_coord
    clc
    adc #.loword(M7_MAP)
    tay
    lda transfer_ptr
    clc
    adc #4
    tax
    phb
    lda native_value
    dec a
    mvn #.bankbyte(STREAM_BUFFER),#.bankbyte(M7_MAP)
    plb
    rts

; Eight shared rows reconstruct the exact 64 pixels without MSU bitmap DMA.
worker_stream_pattern:
    tay
    phb
    lda map_base_ptr
    pha
    lda map_base_ptr+2
    pha
    tya
    pha
    and #$0FFF
    .repeat 4
    asl a
    .endrepeat
    clc
    adc f:STREAM_PATTERNS
    sta map_base_ptr
    lda #0
    adc #0
    sta map_base_ptr+2
    pla
    xba
    and #255
    .repeat 4
    lsr a
    .endrepeat
    clc
    adc map_base_ptr+2
    clc
    adc f:STREAM_PATTERNS+2
    sta map_base_ptr+2
    sep #$20
    .a8
    lda f:STREAM_ROWS+2
    pha
    plb
    rep #$20
    .a16
    .repeat 8, row
    ldy #row*2
    lda [map_base_ptr],y
    clc
    adc f:STREAM_ROWS
    tay
    .repeat 4, word
    lda a:word*2,y
    sta f:M7_PATTERN_STAGE+row*8+word*2,x
    .endrepeat
    .endrepeat
    pla
    sta map_base_ptr+2
    pla
    sta map_base_ptr
    plb
    rts
.endif

; A=byte, native_coord=wrapped address. Preserve the payload reader's Y.
worker_native_cell:
    phy
    sta scratch
    ldx native_coord
    sep #$20
    .a8
    lda scratch
    cmp f:M7_MAP,x
    beq @same
    sta f:M7_MAP,x
    rep #$20
    .a16
    lda #1
    sta f:M7_CACHE_DIRTY
    txa
    and #127
    sta scratch
    txa
    asl a
    xba
    and #127
    tax
    sep #$20
    .a8
    lda f:M7_DIRTY_BITS,x
    bne @bounds
    lda #1
    sta f:M7_DIRTY_BITS,x
    rep #$20
    .a16
    txa
    asl a
    tax
    lda scratch
    xba
    ora scratch
    sta f:M7_DIRTY_BOUNDS,x
    bra @done
@bounds:
    rep #$20
    .a16
    txa
    asl a
    tax
    sep #$20
    .a8
    lda scratch
    cmp f:M7_DIRTY_BOUNDS,x
    bcs :+
    sta f:M7_DIRTY_BOUNDS,x
:
    cmp f:M7_DIRTY_BOUNDS+1,x
    bcc @same
    sta f:M7_DIRTY_BOUNDS+1,x
@same:
    rep #$20
    .a16
@done:
    ply
    rts
.endif
