; Exact-color, precompiled OBJ cells for dense streamed Mode 7 scenes.
.segment "CODE"
worker_stream_spill_packet:
    lda f:STREAM_SPILL_PALETTE_DIRTY
    bne @palette_checked
    ldx #0
    ldy #4
@palette_compare:
    lda [transfer_ptr],y
    cmp f:STREAM_SPILL_PALETTE,x
    bne @palette_changed
    inx
    inx
    iny
    iny
    cpx #30
    bcc @palette_compare
    bra @palette_checked
@palette_changed:
    lda #1
    sta f:STREAM_SPILL_PALETTE_DIRTY
@palette_checked:
    lda #6
    sta f:STREAM_SPILL_STRIDE
    lda native_index
    bit #$8000
    beq @full_cells
    and #$7FFF
    cmp #121
    jcs worker_stream_spill_bad
    pha
    lda #4
    sta f:STREAM_SPILL_STRIDE
    pla
    bra @count_ready
@full_cells:
    cmp #81
    jcs worker_stream_spill_bad
@count_ready:
    sta f:STREAM_SPILL_CELLS_COUNT
    lda [transfer_ptr]
    cmp #129
    jcs worker_stream_spill_bad
    .repeat 5
    asl a
    .endrepeat
    sta f:STREAM_SPILL_CHR_BYTES
    lda f:STREAM_SPILL_CELLS_COUNT
    asl a
    sta scratch
    asl a
    pha
    lda f:STREAM_SPILL_STRIDE
    cmp #4
    beq @compact_bytes
    pla
    clc
    adc scratch
    bra @cell_bytes
@compact_bytes:
    pla
@cell_bytes:
    clc
    adc #30
    sta transfer_len
    clc
    adc transfer_ptr
    adc #4
    adc f:STREAM_SPILL_CHR_BYTES
    sta f:STREAM_SPILL_FAST_PTR
    lda transfer_ptr
    clc
    adc #4
    tax
    ldy #.loword(STREAM_SPILL_PALETTE)
    phb
    lda transfer_len
    dec a
    mvn #$42,#$42
    plb
    jsr worker_stream_spill_seed_mask
    jsr worker_stream_spill_snapshot
    lda f:STREAM_SPILL_CHR_BYTES
    beq @advance
    ldy #2
    lda [transfer_ptr],y
    cmp f:STREAM_SPILL_BUFFER_ID
    beq @advance
    sta f:STREAM_SPILL_BUFFER_ID
    lda f:STREAM_SPILL_DIRECT
    bne @advance
    lda transfer_ptr
    clc
    adc #4
    adc transfer_len
    tax
    ldy #.loword(SPILL_CHR)
    lda f:STREAM_SPILL_CHR_BYTES
    jsr worker_stream_spill_copy
@advance:
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
    lda native_value
    jsr worker_native_advance
    rts

; Row rollback reuses STREAM_BUFFER during cache preparation. The object
; pass follows that work, so it must not retain pointers into the packet.
worker_stream_spill_snapshot:
    lda f:STREAM_SPILL_FAST_PTR
    tax
    sec
    sbc transfer_ptr
    sta scratch
    lda native_value
    sec
    sbc scratch
    sta scratch2
    lda f:STREAM_OAM_DIRECT
    beq @copy
    lda f:$420006,x
    clc
    adc #40
    sta scratch2
@copy:
    lda scratch2
    cmp #513
    jcs worker_stream_spill_bad
    dec a
    ldy #.loword(STREAM_SPILL_SNAPSHOT)
    phb
    mvn #$42,#$42
    plb
    lda #.loword(STREAM_SPILL_SNAPSHOT)
    sta f:STREAM_SPILL_FAST_PTR
    rts

; Canonical checkpoint seeds contain the ordinary background. Restore the
; complete OBJ mask once; subsequent packets only need changed mask cells.
worker_stream_spill_seed_mask:
    lda f:STREAM_SPILL_SEED_MASK
    beq @done
    lda #0
    sta f:STREAM_SPILL_SEED_MASK
    lda f:STREAM_SPILL_CELLS_COUNT
    beq @done
    sta native_count
    ldy #0
@cell:
    tyx
    lda f:STREAM_SPILL_CELLS,x
    lsr a
    lsr a
    lsr a
    and #127
    sta scratch
    lda f:STREAM_SPILL_CELLS+2,x
    lsr a
    lsr a
    lsr a
    and #127
    .repeat 7
    asl a
    .endrepeat
    ora scratch
    sta native_coord
    lda #0
    jsr worker_native_cell
    tya
    clc
    adc f:STREAM_SPILL_STRIDE
    tay
    dec native_count
    bne @cell
@done:
    rts

; The decoder is outside the IRAM kernels. Use their idle 512-byte window
; as a DMA bridge between BW-RAM banks, then invalidate every borrowed view.
worker_stream_spill_copy:
    sta map_left
    stx map_scan_x
    sty map_dest
@chunk:
    lda map_left
    cmp #512
    bcc :+
    lda #512
:
    sta scratch2
    lda #$42
    sta transfer_wbank
    ldx map_scan_x
    ldy #$0500
    lda scratch2
    jsr worker_bw_to_iram
    lda #$43
    sta transfer_wbank
    ldx #$0500
    ldy map_dest
    lda scratch2
    jsr worker_iram_to_bw
    lda map_scan_x
    clc
    adc scratch2
    sta map_scan_x
    lda map_dest
    clc
    adc scratch2
    sta map_dest
    lda map_left
    sec
    sbc scratch2
    sta map_left
    bne @chunk
    lda #0
    sta M7_CACHE_CODE_VALID
    sta M7_ROW_CODE_VALID
    lda #1
    sta f:M7_HASH_DIRTY
    rts
worker_stream_spill_bad:
    lda f:M7_CACHE_ERRORS
    inc a
    sta f:M7_CACHE_ERRORS
    lda native_value
    jsr worker_native_advance
    rts

worker_stream_spill_cost:
    lda f:STREAM_ENABLED
    beq @done
    lda f:STREAM_SPILL_CELLS_COUNT
    beq @done
    lda f:STREAM_SPILL_BUFFER_ID
    cmp f:STREAM_SPILL_VRAM_ID
    bne :+
    lda f:STREAM_SPILL_PALETTE_DIRTY
    beq @done
    lda #86 ; Palette only; the exact glyph image is already resident.
    rts
:
    jsr worker_stream_spill_span
    clc
    adc #56 ; One CHR run and its setup.
    pha
    lda f:STREAM_SPILL_PALETTE_DIRTY
    beq @clean_palette
    pla
    clc
    adc #86
    rts
@clean_palette:
    pla
@done:
    rts

worker_stream_spill_cells:
    lda f:STREAM_SPILL_CELLS_COUNT
    jeq worker_stream_spill_cells_slow
    lda f:STREAM_SPILL_FAST_PTR
    sta transfer_ptr
    lda #$42
    sta transfer_ptr+2
    lda [transfer_ptr]
    cmp f:M7_RASTER_X
    jne worker_stream_spill_cells_slow
    ldy #2
    lda [transfer_ptr],y
    cmp f:M7_RASTER_Y
    jne worker_stream_spill_cells_slow
    ldy #4
    lda [transfer_ptr],y
    sta f:SPILL_VISIBLE
    ldy #6
    lda [transfer_ptr],y
    sta f:STREAM_SPILL_NEG_COUNT
    lda transfer_ptr
    clc
    adc #8
    tax
    ldy #.loword(STREAM_SPILL_LINES)
    phb
    lda #31
    mvn #$42,#$42
    plb
    lda f:STREAM_SPILL_NEG_COUNT
    beq @packed
    ldy #.loword(STREAM_SPILL_NEGATIVE)
    dec a
    phb
    mvn #$42,#$42
    plb
@packed:
    ; The transport can populate OAM directly. Only use it when the
    ; authored raster origin matched above; the fallback recomputes it.
    lda f:STREAM_OAM_DIRECT
    jne worker_stream_spill_uploads
    lda f:SPILL_VISIBLE
    asl a
    asl a
    jeq worker_stream_spill_uploads
    dec a
    ldy #.loword(SPILL_OAM_OUT)
    phb
    mvn #$42,#.bankbyte(SPILL_OAM_OUT)
    plb
    jmp worker_stream_spill_uploads
worker_stream_spill_cells_slow:
    lda #0
    sta f:SPILL_VISIBLE
    sta f:STREAM_SPILL_NEG_COUNT
    ldx #30
@clear_lines:
    sta f:STREAM_SPILL_LINES,x
    dex
    dex
    bpl @clear_lines
    lda f:STREAM_SPILL_CELLS_COUNT
    jeq @done
    sta SPILL_REMAIN
    stz map_scan_x
    stz map_left
@cell:
    ldx map_scan_x
    lda f:STREAM_SPILL_CELLS,x
    sec
    sbc f:M7_RASTER_X
    cmp #$FFF9
    bcs @x_ok
    cmp #256
    bcs @next
@x_ok:
    sta SPILL_X
    lda f:STREAM_SPILL_CELLS+2,x
    sec
    sbc f:M7_RASTER_Y
    cmp #25
    bcc @next
    cmp #177
    bcs @next
    sta SPILL_Y
    lda f:STREAM_SPILL_STRIDE
    cmp #4
    bne :+
    lda #0
    bra @tile_ready
:
    lda f:STREAM_SPILL_CELLS+4,x
@tile_ready:
    sta SPILL_TILE
    ldx map_left
    lda SPILL_X
    sta f:SPILL_FRAME,x
    lda SPILL_Y
    sta f:SPILL_FRAME+2,x
    lda SPILL_TILE
    sta f:SPILL_FRAME+4,x
    jsr worker_stream_spill_object_cell
    lda map_left
    clc
    adc #6
    sta map_left
    lda f:SPILL_VISIBLE
    inc a
    sta f:SPILL_VISIBLE
@next:
    lda map_scan_x
    clc
    adc f:STREAM_SPILL_STRIDE
    sta map_scan_x
    dec SPILL_REMAIN
    jne @cell
@uploads:
    lda f:STREAM_SPILL_BUFFER_ID
    cmp f:STREAM_SPILL_VRAM_ID
    jeq @done
    lda f:STREAM_SPILL_CHR_BYTES
    .repeat 5
    lsr a
    .endrepeat
    sta f:SPILL_COUNT
@done:
    rts

worker_stream_spill_uploads = @uploads

; Build the immutable object bytes while translating the cells, once.
; The later OAM-prefix job only checks aggregate line budgets and shifts
; the rare negative-X bits into their absolute OAM positions.
worker_stream_spill_object_cell:
    lda f:SPILL_VISIBLE
    asl a
    asl a
    tax
    lda SPILL_Y
    xba
    and #$FF00
    sta scratch
    lda SPILL_X
    and #255
    ora scratch
    sta f:SPILL_OAM_OUT,x
    lda SPILL_TILE
    ora #$2100
    sta f:SPILL_OAM_OUT+2,x
    lda SPILL_X
    bpl @lines
    txa
    pha
    lda f:STREAM_SPILL_NEG_COUNT
    tax
    pla
    sta f:STREAM_SPILL_NEGATIVE,x
    inx
    inx
    txa
    sta f:STREAM_SPILL_NEG_COUNT
@lines:
    lda SPILL_Y
    lsr a
    lsr a
    lsr a
    tax
    sep #$20
    .a8
    lda f:STREAM_SPILL_LINES,x
    inc a
    sta f:STREAM_SPILL_LINES,x
    lda SPILL_Y
    and #7
    beq @done
    inx
    lda f:STREAM_SPILL_LINES,x
    inc a
    sta f:STREAM_SPILL_LINES,x
@done:
    rep #$20
    .a16
    rts

worker_stream_spill_objects:
    lda f:SPILL_VISIBLE
    bne :+
    sta f:SPILL_OAM_BYTES
    ; Even an empty clipped job returns the high table to the CPU. Do not
    ; OR a previous frame's negative-X flags into later gameplay objects.
    ldx #30
@clear_empty:
    sta f:SPILL_OAM_HIGH,x
    dex
    dex
    bpl @clear_empty
    rts
:
    asl a
    asl a
    clc
    adc f:SPILL_OAM_PREFIX
    cmp #513
    jcs @fallback
    ; CPU symbol admission can prove the complete frame against exact
    ; scanlines when conservative eight-line bins overestimate the overlap.
    lda f:STREAM_SPILL_EXACT
    bne @exact
    ldx #0
@check:
    lda f:STREAM_SPILL_LINES,x
    and #255
    sta scratch
    lda f:SPILL_OAM_BUDGET,x
    and #255
    clc
    adc scratch
    cmp #33
    jcs @fallback
    inx
    cpx #32
    bcc @check
@exact:
    ldx #0
    sep #$20
    .a8
@charge:
    lda f:SPILL_OAM_BUDGET,x
    clc
    adc f:STREAM_SPILL_LINES,x
    sta f:SPILL_OAM_BUDGET,x
    inx
    cpx #32
    bcc @charge
    rep #$20
    .a16
    lda #0
    ldx #30
@clear:
    sta f:SPILL_OAM_HIGH,x
    dex
    dex
    bpl @clear
    stz map_scan_x
@negative:
    lda map_scan_x
    cmp f:STREAM_SPILL_NEG_COUNT
    bcs @done
    tax
    lda f:STREAM_SPILL_NEGATIVE,x
    clc
    adc f:SPILL_OAM_PREFIX
    sta map_left
    and #12
    lsr a
    tax
    lda f:$010000+@bits,x
    sta scratch
    lda map_left
    lsr a
    lsr a
    lsr a
    lsr a
    tax
    sep #$20
    .a8
    lda f:SPILL_OAM_HIGH,x
    ora scratch
    sta f:SPILL_OAM_HIGH,x
    rep #$20
    .a16
    inc map_scan_x
    inc map_scan_x
    bra @negative
@done:
    lda f:SPILL_VISIBLE
    asl a
    asl a
    sta f:SPILL_OAM_BYTES
    rts
@fallback:
    ; Keep the established clipping path when gameplay has used more of
    ; the object budget than the compiler's reserved margin.
    jsr worker_stream_spill_cells_slow
    jmp worker_emit_spills_ordinary
@bits:
    .word 1,4,16,64

; A=bytes, X=offset. A delta is valid only against the image acknowledged
; by NMI, never merely against the last decoded/catch-up packet.
worker_stream_spill_span:
    lda f:STREAM_SPILL_BASE_ID
    cmp #$FFFF
    beq @full
    cmp f:STREAM_SPILL_VRAM_ID
    bne @full
    lda f:STREAM_SPILL_DELTA_BYTES
    beq @full
    clc
    adc f:STREAM_SPILL_DELTA_START
    cmp f:STREAM_SPILL_CHR_BYTES
    bcc @delta
    bne @full
@delta:
    lda f:STREAM_SPILL_DELTA_START
    tax
    lda f:STREAM_SPILL_DELTA_BYTES
    rts
@full:
    ldx #0
    lda f:STREAM_SPILL_CHR_BYTES
    rts
