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

worker_native_animation:
    lda #0
    sta f:NATIVE_PALETTE_DIRTY
    sta f:NATIVE_ALPHA_DIRTY
    sta f:NATIVE_ALPHA_END
    dec a
    sta f:NATIVE_ALPHA_BEGIN
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
    cmp #29
    jcs @bad_kind
    asl a
    tax
    jmp (@handlers,x)
@handlers:
    .word @cell,@alpha,@x,@y,@bad_kind,@bad_kind,@zoom,@color
    .word @colors,@spatial,@camera,@rotation,@references,@phase,@active,@projection
    .word @bad_kind,@bad_kind,@bad_kind,@bad_kind,@bad_kind,@bad_kind,@bad_kind
    .word @origin,@bad_kind,@bad_kind,@bad_kind,@tag,@symbols
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
    txa
    inc a
    inc a
    cmp f:NATIVE_PALETTE_DIRTY
    bcc @done
    sta f:NATIVE_PALETTE_DIRTY
@done:
    rts

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
    .repeat 7
    lsr a
    .endrepeat
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
