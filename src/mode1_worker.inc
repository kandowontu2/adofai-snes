.ifdef SA1_MODE1_BUILD
; Projected frames carry their exact 4-bpp pixels. The worker stages them
; directly; dictionary IDs are unnecessary for these screen-space glyphs.
worker_mode1_inline_packet:
    lda native_index
    sta native_count
@glyph:
    lda [transfer_ptr]
    sta native_value
    and #1023
    tax
    sep #$20
    .a8
    lda #1
    sta f:M1_DIRTY,x
    rep #$20
    .a16
    txa
    pha
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda #1
    sta f:M1_DIRTY_BLOCKS,x
    rep #$20
    .a16
    pla
    .repeat 5
    asl a
    .endrepeat
    tay
    lda native_value
    bit #$4000
    beq :+
    tya
    clc
    adc #16
    tay
:
    lda transfer_ptr
    clc
    adc #2
    tax
    lda native_value
    bit #$C000
    beq @full
    lda #15
    bra @copy
@full:
    lda #31
@copy:
    phb
    mvn #$42,#$43
    plb
    lda native_value
    bit #$C000
    beq @advance_full
    bit #$4000
    beq @zero
    tya
    sec
    sbc #32
    tay
@zero:
    tyx
    lda #0
    .repeat 8, ROW
    sta f:M1_CHR_STAGE+ROW*2,x
    .endrepeat
    lda #18
    bra @advance
@advance_full:
    lda #34
@advance:
    jsr worker_native_advance
    dec native_count
    jne @glyph
    rts

worker_mode1_packet:
    lda [transfer_ptr]
    sta native_kind
    lda #2
    jsr worker_native_advance
    lda native_kind
    and #1
    beq @palette
    phb
    ldx transfer_ptr
    ldy #$0100
    lda #511
    mvn #$42,#$00
    plb
    lda #512
    jsr worker_native_advance
@palette:
    lda native_kind
    and #2
    beq @patterns
    phb
    ldx transfer_ptr
    ldy #.loword(M1_PALETTE)
    lda #95
    mvn #$42,#$42
    plb
    lda #1
    sta f:M1_READY
    lda #96
    jsr worker_native_advance
@patterns:
    lda native_index
    jeq @done
    sta native_count
@pattern:
    lda [transfer_ptr]
    tax
    sep #$20
    .a8
    lda #1
    sta f:M1_DIRTY,x
    rep #$20
    .a16
    phx
    txa
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda #1
    sta f:M1_DIRTY_BLOCKS,x
    rep #$20
    .a16
    plx
    txa
    asl a
    tax
    ldy #2
    lda [transfer_ptr],y
    sta f:M1_PENDING_GLYPHS,x
    lda #4
    jsr worker_native_advance
    dec native_count
    jne @pattern
@done:
    rts

worker_mode1_rows:
    lda f:M1_GLYPH_COUNT
    jsr worker_mode1_address
    lda map_base_ptr
    sta map_ptr
    lda map_base_ptr+2
    sta map_ptr+2
    rts

.segment "HOTMODE1"
; Shared address calculation for the packed lossless row dictionary.
worker_mode1_address:
    sta scratch
    asl a
    clc
    adc scratch
    pha
    and #$3FFF
    asl a
    asl a
    clc
    adc f:STREAM_PATTERNS
    sta map_base_ptr
    lda #0
    adc #0
    sta map_base_ptr+2
    pla
    xba
    and #255
    .repeat 6
    lsr a
    .endrepeat
    clc
    adc map_base_ptr+2
    clc
    adc f:STREAM_PATTERNS+2
    sta map_base_ptr+2
    rts
worker_mode1_copy:
    sta scratch
    asl a
    clc
    adc scratch
    pha
    and #$3FFF
    asl a
    asl a
    clc
    adc f:STREAM_PATTERNS
    sta map_base_ptr
    lda #0
    adc #0
    sta map_base_ptr+2
    pla
    xba
    and #255
    .repeat 6
    lsr a
    .endrepeat
    clc
    adc map_base_ptr+2
    clc
    adc f:STREAM_PATTERNS+2
    sta map_base_ptr+2
    .repeat 8, ROW
    ldy #(ROW*3)/2
    lda [map_base_ptr],y
    .if ROW & 1
    lsr a
    lsr a
    .else
    asl a
    asl a
    .endif
    and #$3FFC
    tay
    lda [map_ptr],y
    sta f:M1_CHR_STAGE+ROW*2,x
    iny
    iny
    lda [map_ptr],y
    sta f:M1_CHR_STAGE+16+ROW*2,x
    .endrepeat
    rts

.segment "CODE"
worker_mode1_code:
    lda M7_CACHE_CODE_VALID
    cmp #2
    beq @ready
    phb
    lda #__HOTMODE1_SIZE__-1
    ldx #__HOTMODE1_LOAD__
    ldy #__HOTMODE1_RUN__
    mvn #$01,#$00
    plb
    lda #0
    sta M7_ROW_CODE_VALID
    lda #2
    sta M7_CACHE_CODE_VALID
@ready:
    rts

worker_mode1_seed:
    jsr worker_mode1_code
    lda f:STREAM_PAGE
    jsr worker_select_rom_bank
    jsr worker_mode1_rows
    stz native_index
@slot:
    lda native_index
    asl a
    tax
    lda f:STREAM_BUFFER,x
    pha
    txa
    .repeat 4
    asl a
    .endrepeat
    tax
    pla
    jsr worker_mode1_copy
    inc native_index
    lda native_index
    cmp #1024
    bcc @slot
    rts

worker_mode1_prepare:
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    jsr worker_snapshot_prepare
    jmp @patterns_ready
:
    cmp #2
    bne @dictionary_code
    jsr worker_projected_code
    bra @code_ready
@dictionary_code:
    jsr worker_mode1_code
@code_ready:
    lda f:STREAM_PAGE
    jsr worker_select_rom_bank
    lda #0
    sta M7_ROW_CODE_VALID
    sta f:M7_WRAM_STAGE_REQUIRED
    sta f:M7_PATTERN_RUN_COUNT
    sta f:M7_TAG_COUNT
    sta f:SPILL_VISIBLE
    sta f:M7_FORCE_SKIP_HUD
    sta f:M7_STAGE_BASE_X
    sta f:M7_STAGE_BASE_Y
    stz m7_row_count
    stz m7_row_span
    stz pattern_queue_count
    stz m7_upload_slots
    ldy #0
@map_row:
    tyx
    lda f:M1_ROW_MAX,x
    and #255
    beq @map_next
    sta scratch
    lda f:M1_ROW_MIN,x
    and #255
    sta scratch2
    tya
    .repeat 6
    asl a
    .endrepeat
    clc
    adc scratch2
    sta map_dest
    lda scratch
    sec
    sbc scratch2
    sta map_left
    ; Adjacent row spans share one DMA when the intervening unchanged
    ; words cost less than another transfer setup. The staging map is a
    ; complete exact image, so these extra words preserve every pixel.
    lda m7_row_count
    beq @map_append
    dec a
    asl a
    asl a
    tax
    lda f:M1_MAP_RUNS,x
    clc
    adc f:M1_MAP_RUNS+2,x
    sta scratch2
    lda map_dest
    sec
    sbc scratch2
    cmp #17
    bcs @map_append
    clc
    adc map_left
    sta map_left
    clc
    adc f:M1_MAP_RUNS+2,x
    sta f:M1_MAP_RUNS+2,x
    bra @map_count_bytes
@map_append:
    lda m7_row_count
    asl a
    asl a
    tax
    lda map_dest
    sta f:M1_MAP_RUNS,x
    lda map_left
    sta f:M1_MAP_RUNS+2,x
    inc m7_row_count
@map_count_bytes:
    lda map_left
    clc
    adc m7_row_span
    sta m7_row_span
    sep #$20
    .a8
    tyx
    lda #0
    sta f:M1_ROW_MAX,x
    lda #255
    sta f:M1_ROW_MIN,x
    rep #$20
    .a16
@map_next:
    iny
    cpy #64
    jcc @map_row
    lda f:STREAM_MODE1
    cmp #2
    bne :+
    jsr worker_projected_runs
    jmp @patterns_ready
:
    jsr worker_mode1_rows
    lda #0
    sta f:M1_RUN_COUNT
    ldx #0
@scan:
    txa
    and #15
    bne @within_block
    phx
    txa
    .repeat 4
    lsr a
    .endrepeat
    tax
    lda f:M1_DIRTY_BLOCKS,x
    and #255
    plx
    cmp #0
    bne @within_block
    txa
    clc
    adc #16
    tax
    jmp @scan_check
@within_block:
    lda f:M1_DIRTY,x
    jeq @scan_pair
    and #255
    jeq @scan_next
    stx scratch
@run:
    lda f:M1_DIRTY,x
    and #255
    beq @unchanged_glyph
    lda f:STREAM_MODE1
    cmp #2
    beq @unchanged_glyph
    phx
    lda scratch
    pha
    txa
    asl a
    tax
    lda f:M1_PENDING_GLYPHS,x
    pha
    txa
    .repeat 4
    asl a
    .endrepeat
    tax
    pla
    jsr worker_mode1_copy
    pla
    sta scratch
    plx
@unchanged_glyph:
    sep #$20
    .a8
    lda #0
    sta f:M1_DIRTY,x
    rep #$20
    .a16
    inc m7_upload_slots
    inx
    cpx #1024
    bcs @run_done
    lda f:M1_DIRTY,x
    and #255
    bne @run
    ; Re-uploading one unchanged 32-byte glyph costs less than another
    ; S-CPU DMA setup. Its staging pixels are already the exact VRAM image.
    cpx #1023
    bcs @run_done
    lda f:M1_DIRTY+1,x
    and #255
    bne @run
@run_done:
    phx
    txa
    sec
    sbc scratch
    .repeat 5
    asl a
    .endrepeat
    pha
    lda f:M1_RUN_COUNT
    asl a
    asl a
    tax
    pla
    sta f:M1_PATTERN_RUNS+2,x
    lda scratch
    .repeat 5
    asl a
    .endrepeat
    sta f:M1_PATTERN_RUNS,x
    lda f:M1_RUN_COUNT
    inc a
    sta f:M1_RUN_COUNT
    plx
    bra @scan_check
@scan_pair:
    inx
@scan_next:
    inx
@scan_check:
    cpx #1024
    jcc @scan
    ldx #0
    lda #0
@clear_blocks:
    sta f:M1_DIRTY_BLOCKS,x
    inx
    inx
    cpx #64
    bcc @clear_blocks
@patterns_ready:
    lda m7_upload_slots
    sta pattern_queue_count
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    jsr worker_snapshot_colors
    bra @prepared
:
    lda f:M1_READY
    beq @prepared

    ldx #0
@palette:
    lda f:M1_PALETTE,x
    and #255
    beq @transparent
    sec
    sbc #32
    asl a
    phx
    tax
    lda f:NATIVE_PALETTE,x
    plx
    bra @write_color
@transparent:
    lda #0
@write_color:
    phx
    pha
    txa
    asl a
    tax
    pla
    sta f:M1_CGRAM,x
    plx
    inx
    cpx #96
    bcc @palette
@prepared:
    lda #1
    jmp worker_select_rom_bank

worker_mode1_map_packet:
    lda native_index
    sta native_count
@map_span:
    lda [transfer_ptr]
    sta map_dest
    and #63
    sta scratch2
    ldy #2
    lda [transfer_ptr],y
    sta transfer_len
    clc
    adc scratch2
    sta scratch
    lda map_dest
    .repeat 6
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda scratch2
    cmp f:M1_ROW_MIN,x
    bcs :+
    sta f:M1_ROW_MIN,x
:
    lda scratch
    cmp f:M1_ROW_MAX,x
    bcc :+
    sta f:M1_ROW_MAX,x
:
    rep #$20
    .a16
    lda #4
    jsr worker_native_advance
    lda map_dest
    clc
    adc #.loword(M1_MAP_STAGE)
    tay
    ldx transfer_ptr
    lda transfer_len
    dec a
    phb
    mvn #$42,#$42
    plb
    lda transfer_len
    jsr worker_native_advance
    dec native_count
    bne @map_span
    rts
.endif
