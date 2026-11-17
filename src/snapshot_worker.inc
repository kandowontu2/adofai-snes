; Independent LZ4 poses. Split blocks decode CHR directly to the inactive
; atlas, avoiding an extra full-image BW-RAM copy on every rendered frame.
worker_snapshot_lz4:
    lda #0
    sta f:M1_BUILD_FORMAT
.ifdef WIDE_SNAPSHOT_SUPPORT
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    lda f:M1_BUILD_FORMAT
    ora #2
    sta f:M1_BUILD_FORMAT
:
.endif
    jsr worker_snapshot_load_hot
    lda #$4242
    sta f:lz4_literals+1
    sta f:lz4_match_copy+1
    lda transfer_ptr
    clc
    adc native_value
    sta map_left
    pha
    ldx transfer_ptr
    ldy #$2000
    jsr worker_lz4_block
    lda native_index
    beq @header
    .repeat 5
    asl a
    .endrepeat
    dec a
    pha
    jsr worker_snapshot_atlas_destination
    ldx #$2520
    pla
    phb
    mvn #$42,#$43
    plb
@header:
    jsr worker_snapshot_decoded_header
    pla
    sta transfer_ptr
    rts

worker_snapshot_lz4_split:
    lda #0
    sta f:M1_BUILD_FORMAT
    lda native_kind
    cmp #47
    bne :+
    lda #1
    sta f:M1_BUILD_FORMAT
:
.ifdef WIDE_SNAPSHOT_SUPPORT
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    lda f:M1_BUILD_FORMAT
    ora #2
    sta f:M1_BUILD_FORMAT
:
.endif
    jsr worker_snapshot_load_hot
    lda #$4242
    sta f:lz4_literals+1
    sta f:lz4_match_copy+1
    lda transfer_ptr
    clc
    adc native_value
    pha
    ldx transfer_ptr
    lda f:$420000,x
    clc
    adc transfer_ptr
    adc #2
    sta map_left
    inx
    inx
    ldy #$2000
    jsr worker_lz4_block
    lda 1,s
    sta map_left
    lda #$4243
    sta f:lz4_literals+1
    lda #$4343
    sta f:lz4_match_copy+1
    jsr worker_snapshot_atlas_destination
    jsr worker_lz4_block
    jsr worker_snapshot_decoded_header
    pla
    sta transfer_ptr
    rts

worker_snapshot_atlas_destination:
    lda f:M1_FRONT_BANK
    eor #$0200
    .repeat 5
    asl a
    .endrepeat
.ifdef WIDE_SNAPSHOT_SUPPORT
    beq :++
    pha
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    pla
    clc
    adc #$1000
    bra :++
:
    pla
:
.endif
    clc
    adc #32
    tay
    rts

worker_snapshot_decoded_header:
    lda #$2000
    sta transfer_ptr
    lda #44
    sta native_kind
    jmp worker_snapshot_packet

worker_snapshot_packet:
    jsr worker_snapshot_load_hot
    jmp worker_snapshot_decode

worker_snapshot_load_hot:
    lda M7_CACHE_CODE_VALID
    cmp #5
    beq @ready
    phb
    ldx #__HOTSNAPSHOT_LOAD__
    ldy #__HOTSNAPSHOT_RUN__
    lda #__HOTSNAPSHOT_SIZE__-1
    mvn #$01,#$00
    plb
    lda #0
    sta M7_ROW_CODE_VALID
    lda #5
    sta M7_CACHE_CODE_VALID
@ready:
    rts
.segment "HOTSNAPSHOT"
worker_lz4_block:
    lda f:$420000,x
    and #255
    sta scratch
    inx
    lsr a
    lsr a
    lsr a
    lsr a
    cmp #15
    bne lz4_literal
    sta scratch2
lz4_literal_extra:
    lda f:$420000,x
    and #255
    inx
    pha
    clc
    adc scratch2
    sta scratch2
    pla
    cmp #255
    beq lz4_literal_extra
    lda scratch2
lz4_literal:
    cmp #0
    beq lz4_match
    dec a
    phb
lz4_literals:
    mvn #$42,#$42
    plb
lz4_match:
    cpx map_left
    bcs lz4_decoded
    lda f:$420000,x
    sta map_dest
    inx
    inx
    lda scratch
    and #15
    cmp #15
    bne lz4_match_length
    sta scratch2
lz4_match_extra:
    lda f:$420000,x
    and #255
    inx
    pha
    clc
    adc scratch2
    sta scratch2
    pla
    cmp #255
    beq lz4_match_extra
    lda scratch2
lz4_match_length:
    clc
    adc #3                 ; LZ4 minimum match 4, MVN count is length-1.
    sta scratch2
    phx
    tya
    sec
    sbc map_dest
    tax
    lda scratch2
    phb
lz4_match_copy:
    mvn #$42,#$42           ; Forward copy deliberately supports overlap.
    plb
    plx
    jmp worker_lz4_block
lz4_decoded:
    rts

worker_snapshot_decode:
    lda #0
    sta f:M1_PREFETCH_READY
    lda native_index
    sta native_count
    .repeat 5
    asl a
    .endrepeat
    sta f:M1_SNAPSHOT_BYTES
    lda f:M1_FRONT_BANK
    eor #$0200
    sta f:M1_BUILD_BANK
    phb
    ldx transfer_ptr
    ldy #.loword(M1_PALETTE)
    lda #95
    mvn #$42,#$42
    plb
    lda #96
    jsr worker_native_advance
    jsr worker_snapshot_map
    lda #1216
    jsr worker_native_advance
    lda native_kind
    cmp #44
    bne @expand
    lda f:M1_SNAPSHOT_BYTES
    jsr worker_native_advance
    jmp @ready
@expand:
    lda f:M1_BUILD_BANK
    .repeat 5
    asl a
    .endrepeat
.ifdef WIDE_SNAPSHOT_SUPPORT
    beq :++
    pha
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    pla
    clc
    adc #$1000
    bra :++
:
    pla
:
.endif
    clc
    adc #32
    sta map_dest
    lda native_count
    beq @ready
@glyph:
    lda [transfer_ptr]
    and #255
    sta native_kind
    lda #1
    jsr worker_native_advance
    ldy map_dest
    lda native_kind
    cmp #2
    bne :+
    tya
    clc
    adc #16
    tay
:
    ldx transfer_ptr
    lda native_kind
    beq @full
    lda #15
    bra @copy
@full:
    lda #31
@copy:
    phb
    mvn #$42,#$43
    plb
    lda native_kind
    beq @advance_full
    cmp #2
    bne @zero
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
    lda #16
    bra @advance
@advance_full:
    lda #32
@advance:
    jsr worker_native_advance
    lda map_dest
    clc
    adc #32
    sta map_dest
    dec native_count
    jne @glyph
@ready:
    lda #1
    sta f:M1_READY
    sta f:M1_SNAPSHOT_DIRTY
    lda #0
    sta f:M1_RUN_COUNT
    lda f:M1_SNAPSHOT_BYTES
    sta f:M1_PATTERN_RUNS+2
    beq @prefetch_ready
    lda f:M1_BUILD_BANK
    .repeat 5
    asl a
    .endrepeat
.ifdef WIDE_SNAPSHOT_SUPPORT
    beq :++
    pha
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    pla
    clc
    adc #$1000
    bra :++
:
    pla
:
.endif
    clc
    adc #32
    sta f:M1_PATTERN_RUNS
    lda #1
    sta f:M1_RUN_COUNT
@prefetch_ready:
    ; All atlas bytes are final. The IRQ may fill the unused VRAM bank
    ; while the main CPU is still positioning the live planets/trails.
    lda #1
    sta f:M1_PREFETCH_READY
    rts

.segment "CODE"
worker_snapshot_prepare:
    lda #0
    sta f:M7_WRAM_STAGE_REQUIRED
    sta f:M7_PATTERN_RUN_COUNT
    sta f:M7_TAG_COUNT
    sta f:SPILL_VISIBLE
    sta f:M7_FORCE_SKIP_HUD
    sta f:M7_STAGE_BASE_X
    sta f:M7_STAGE_BASE_Y
    sta f:M1_RUN_COUNT
    sta m7_row_count
    sta m7_row_span
    sta m7_upload_slots
    lda f:M1_SNAPSHOT_DIRTY
    beq @done
    lda f:M1_MAP_RUNS+2
    sta m7_row_span
    beq @chr
    lda #1
    sta m7_row_count
@chr:
    ; The IRQ may already have prefetched a prefix during planet work.
    ; Preserve its descriptor instead of queuing those pixels a second time.
    lda f:M1_PATTERN_RUNS+2
    .repeat 5
    lsr a
    .endrepeat
    sta m7_upload_slots
    beq @done
    lda #1
    sta f:M1_RUN_COUNT
@done:
    lda f:M1_SNAPSHOT_DIRTY
    sta f:M1_PREFETCH_READY
    rts

; Complete poses remain independent in the stream. Only changed map words
; need to reach VRAM: exclude identical prefix/suffix rows without adding
; dozens of small DMA runs or changing a single pixel/update.
worker_snapshot_map:
    lda f:M1_BUILD_BANK
    beq @bank_ready
    lda #$0200
    sta scratch
    lda f:M1_BUILD_FORMAT
    beq :+
    lda #$0100
    sta scratch
.ifdef WIDE_SNAPSHOT_SUPPORT
    lda f:M1_BUILD_FORMAT
    cmp #2
    bne :+
    lda #$0080
    sta scratch
    bra :++
:
    lda f:M1_BUILD_FORMAT
    cmp #3
    bne :+
    lda #$0040
    sta scratch
.endif
:
    ldy #0
@bank:
    lda [transfer_ptr],y
    bne :+
    lda scratch
    ; Both wide and 8-bpp atlases need their own blank glyph. The
    ; first bank may still contain 4-bpp glyph 1 in the upper half
    ; of its 8-bpp glyph 0 while the other bank is being published.
    cmp #512
    beq :++
    lda #0
:
    clc
    adc scratch
    sta [transfer_ptr],y
:
    iny
    iny
    cpy #1216
    bcc @bank
@bank_ready:
    ldy #0
@first:
    tyx
    lda [transfer_ptr],y
    cmp f:M1_MAP_STAGE+256,x
    bne @found
    iny
    iny
    cpy #1216
    bcc @first
    lda #0
    sta f:M1_MAP_RUNS+2
    rts
@found:
    sty map_dest
    tya
    clc
    adc #256
    sta f:M1_MAP_RUNS
    ldy #1214
@last:
    tyx
    lda [transfer_ptr],y
    cmp f:M1_MAP_STAGE+256,x
    bne @copy
    dey
    dey
    bra @last
@copy:
    tya
    sec
    sbc map_dest
    clc
    adc #2
    sta f:M1_MAP_RUNS+2
    pha
    lda transfer_ptr
    clc
    adc map_dest
    tax
    lda map_dest
    clc
    adc #.loword(M1_MAP_STAGE)+256
    tay
    pla
    dec a
    phb
    mvn #$42,#$42
    plb
    rts

; Upload the exact range of changed hardware colors, rather than rewriting
; all six palettes on every screen-pose change. Native CGRAM fades still
; run on every authored frame, independently of geometry/selector changes.
worker_snapshot_colors:
    lda #192
    sta f:M1_CGRAM_BEGIN
    lda #0
    sta f:M1_CGRAM_BYTES
    ldx #0
@color:
    phx
    txa
    lsr a
    tax
    lda f:M1_PALETTE,x
    and #255
    beq @transparent
    sec
    sbc #32
    asl a
    tax
    lda f:NATIVE_PALETTE,x
    bra @compare
@transparent:
    lda #0
@compare:
    plx
    cmp f:M1_CGRAM,x
    beq @next
    sta f:M1_CGRAM,x
    txa
    cmp f:M1_CGRAM_BEGIN
    bcs :+
    sta f:M1_CGRAM_BEGIN
:
    txa
    inc a
    inc a
    sta f:M1_CGRAM_BYTES
@next:
    inx
    inx
    cpx #192
    bcc @color
    lda f:M1_CGRAM_BYTES
    beq @clean
    sec
    sbc f:M1_CGRAM_BEGIN
    sta f:M1_CGRAM_BYTES
@clean:
    sta f:M1_READY
    rts
