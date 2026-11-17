.ifdef SA1_MODE1_BUILD
.segment "CODE"
mode7_commit_map:
    lda f:STREAM_MODE1
    beq :+
    jsl mode1_commit_map
    rts
:
    jmp mode7_commit_map_native
mode7_commit_patterns:
    lda f:STREAM_MODE1
    beq :+
    jmp mode1_commit_patterns
:
    jmp mode7_commit_patterns_native
mode1_initialize:
    jsl mode1_clear_buffers
    sep #$20
    .a8
    lda #$71
    sta $2107
    rep #$20
    .a16
    jsr mode7_cache_reset
    jmp mode1_restore_seed
.ifdef NEO_BUILD
.segment "NEOCODE"
.endif
mode1_clear_buffers:
    lda #0
    sta f:M1_BUILD_FORMAT
    sta f:M1_FRONT_FORMAT
    sta f:M1_READY
    sta f:M1_RUN_COUNT
    ldx #0
@dirty:
    sta f:M1_DIRTY,x
    inx
    inx
    cpx #1024
    bcc @dirty
    ldx #0
@map_bounds:
    lda #$FFFF
    sta f:M1_ROW_MIN,x
    lda #0
    sta f:M1_ROW_MAX,x
    sta f:M1_DIRTY_BLOCKS,x
    inx
    inx
    cpx #64
    bcc @map_bounds
    rtl
.segment "CODE"

mode1_restore_seed:
.ifdef EXTENDED_CHART_BUILD
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    jsl snapshot_icons_seed
:
.endif
    lda #1
    sta msu_data_busy
    lda f:M7_RENDER_TIME
    .repeat 6
    lsr a
    .endrepeat
    asl a
    asl a
    clc
    adc f:M1_SEEDS_LO
    sta msu_seek_offset
    lda f:M1_SEEDS_HI
    adc #0
    sta msu_seek_offset+2
    jsr msu_seek_data
    sep #$20
    .a8
    ldx #0
@offset:
    data_read8
    sta stream_offset,x
    inx
    cpx #4
    bcc @offset
    rep #$20
    .a16
    lda stream_offset
    clc
    adc f:M1_SEEDS_LO
    sta msu_seek_offset
    lda stream_offset+2
    adc f:M1_SEEDS_HI
    sta msu_seek_offset+2
    jsr msu_seek_data
    sep #$20
    .a8
    data_read8
    sta f:M1_SEED_CURSOR
    data_read8
    sta f:M1_SEED_CURSOR+1
    rep #$20
    .a16
.ifdef NEO_BUILD
    jsl snapshot_seed_header
.endif
.ifdef REFERENCE_SNAPSHOT_SEEDS
    jsl snapshot_reference_seed
.else
    ldy #.loword(M1_PALETTE)
    lda #96
    jsr mode1_read_seed_block
    ldy #.loword(M1_MAP_STAGE)
    lda #4096
.ifdef COMPACT_SNAPSHOT_SEEDS
.if COMPACT_SNAPSHOT_SEEDS >= 3
    pha
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    pla
    lda #1472
    bra :++
:
    pla
:
.endif
.endif
    jsr mode1_read_seed_block
.ifdef COMPACT_SNAPSHOT_SEEDS
.if COMPACT_SNAPSHOT_SEEDS >= 3
    lda f:STREAM_MODE1
    cmp #3
    bne @map_ready
    ldx #1472
    lda #0
@zero_map_tail:
    sta f:M1_MAP_STAGE,x
    inx
    inx
    cpx #4096
    bcc @zero_map_tail
@map_ready:
.endif
.endif
    lda f:STREAM_MODE1
    cmp #2
    bcc @dictionary_seed
    jsl mode1_restore_raw_atlas
    bra @atlas_ready
@dictionary_seed:
    ldy #.loword(STREAM_BUFFER)
    lda #2048
    jsr mode1_read_seed_block
.endif
@atlas_ready:
    sep #$20
    .a8
    data_read8
    sta f:M1_SEED_SYMBOL_BYTES
    data_read8
    sta f:M1_SEED_SYMBOL_BYTES+1
    rep #$20
    .a16
    lda f:M1_SEED_SYMBOL_BYTES
    beq @symbols_ready
    sta transfer_len
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
    phb
    ldx #.loword(M7_CHR_LOW)
    ldy #.loword(TRACK_SYMBOL_FLOORS)
    lda f:M1_SEED_SYMBOL_BYTES
    dec a
    mvn #$7E,#$40
    plb
@symbols_ready:
    lda f:STREAM_MODE1
    cmp #2
    bcs @pixels_ready
    lda f:STREAM_ROWS
    sta msu_seek_offset
    lda f:STREAM_ROWS+2
    sta msu_seek_offset+2
    jsr msu_seek_data
    lda last_note
    inc a
    .repeat 4
    asl a
    .endrepeat
    ldy #.loword(M1_ICON_INFO)
    jsr mode1_read_seed_block
    lda #0
    sta f:SA1_DONE
    lda #10
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
    jsr stream_wait_worker
@pixels_ready:
    lda #0
    sta f:NATIVE_READY
    jsr native_animation_seed
    lda f:M1_SEED_SYMBOL_BYTES
    sta event_count
    sta f:NATIVE_SYMBOL_BYTES
    jsr stream_animation_update
    lda #1
    sta f:M1_READY
    jsr sa1_cache_prepare
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4350
    lda #$18
    sta $4351
    lda #$43
    sta $4354
    rep #$20
    .a16
    stz $2116
    stz $4352
    lda #32768
.ifdef WIDE_SNAPSHOT_SUPPORT
    pha
    lda f:M1_GLYPH_COUNT
    cmp #640
    tax
    pla
    cpx #640
    bne :+
    lda #40960
:
.endif
    sta $4355
    start_dma 32
    lda #$7000
    sta $2116
    lda #.loword(M1_MAP_STAGE)
    sta $4352
    lda #4096
    sta $4355
    sep #$20
    .a8
    lda #$42
    sta $4354
    rep #$20
    .a16
    start_dma 32
    lda #1
    sta f:M1_READY
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    lda #0
    sta f:M1_CGRAM_BEGIN
    lda #192
    sta f:M1_CGRAM_BYTES
:
    jsr mode1_upload_palette
.ifdef NEO_BUILD
    jsl snapshot_force_complete
.endif
    lda #0
    sta f:M1_RUN_COUNT
    stz pattern_queue_count
    stz m7_row_count
    stz msu_data_busy
    rts

mode1_read_seed_block:
.ifdef NEO_BUILD
    jsl mode1_seed_block_far
    rts
.segment "NEOCODE"
mode1_seed_block_far:
.endif
    sta stream_copy_length
    sta transfer_len
    sty stream_destination
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
 .ifdef NEO_BUILD
    jsl $800000+mode1_raw_dma
 .else
    jsr animation_dma
 .endif
    ldx #.loword(M7_CHR_LOW)
    ldy stream_destination
    lda stream_copy_length
 .ifdef NEO_BUILD
    jml $800000+stream_copy_plain_chunk
.segment "CODE"
 .else
    jmp native_seed_span
 .endif

.export mode1_icons_ready, mode1_icons_complete
mode1_render_symbols:
    stz object_small
.ifdef EXTENDED_CHART_BUILD
    lda f:STREAM_MODE1
    cmp #3
    bne @setup
    jsr symbol_world_bounds
    jsr sa1_symbols
    lda f:SYMBOL_VISIBLE_COUNT
    cmp #32
    bcs @setup
    lda f:SNAPSHOT_ICON_HAS_PREVIEWS
    bne @setup
    lda #$FFFF
    sta f:SPILL_OAM_BYTES
    jmp mode1_icons_ready
@setup:
.endif
    lda oam_pos
    sta f:SPILL_OAM_PREFIX
    lda time_attack
    sta f:M1_ICON_ATTACK
    lda #$FFFF
    sta f:M1_ICON_CHECKPOINT
    lda checkpoint_record
    beq @no_checkpoint
    dec a
    tax
    lda f:CHECKPOINTS,x
    sta f:M1_ICON_CHECKPOINT
@no_checkpoint:
    ldx #0
@budget_in:
    lda SPRITE_BUDGET,x
    sta f:SPILL_OAM_BUDGET,x
    inx
    inx
    cpx #32
    bcc @budget_in
.ifdef EXTENDED_CHART_BUILD
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    ; The worker proves exact OBJ/34-sliver limits from the existing
    ; planets/HUD once, then incrementally charges each accepted icon.
    lda #1
    sta msu_data_busy
    lda #OAM
    sta $2181
    sep #$20
    .a8
    stz $2183
    lda #$80
    sta $4300
    sta $4301
    lda #^SNAPSHOT_ICON_PREFIX
    sta $4304
    rep #$20
    .a16
    lda #.loword(SNAPSHOT_ICON_PREFIX)
    sta $4302
    lda #544
    sta $4305
    start_dma 1
    stz msu_data_busy
:
.endif
    lda #0
    sta f:SPILL_OAM_BYTES
.ifdef EXTENDED_CHART_BUILD
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    jsr sa1_snapshot_icons
    bra :++
:
.endif
    jsr symbol_world_bounds
    jsr sa1_symbols
.ifdef EXTENDED_CHART_BUILD
:
.endif
mode1_icons_ready = *
    lda f:SPILL_OAM_BYTES
    cmp #$FFFF
    jeq mode1_icons_sparse
    cmp #0
    beq @done
    ldx #0
@budget_out:
    lda f:SPILL_OAM_BUDGET,x
    sta SPRITE_BUDGET,x
    lda f:SPILL_OAM_HIGH,x
    ora OAM+512,x
    sta OAM+512,x
    inx
    inx
    cpx #32
    bcc @budget_out
    lda #1
    sta msu_data_busy
    lda oam_pos
    clc
    adc #OAM
    sta $2181
    sep #$20
    .a8
    stz $2183
    stz $4300
    lda #$80
    sta $4301
    lda #^SPILL_OAM_OUT
    sta $4304
    rep #$20
    .a16
    lda #.loword(SPILL_OAM_OUT)
    sta $4302
    lda f:SPILL_OAM_BYTES
    sta $4305
    start_dma 1
    stz msu_data_busy
    lda oam_pos
    clc
    adc f:SPILL_OAM_BYTES
    sta oam_pos
@done:
mode1_icons_complete = *
    clc
    rts
mode1_icons_sparse:
    sec
    rts

.segment "FASTWRAM"
 ; Load the cache only after load_patterns has reset render time and loaded
; this song's animation descriptor. A previous song's time selects a wrong seed.
mode1_load_initial_chr:
    lda f:STREAM_MODE1
    bne @done
    jmp mode7_upload_chr
@done:
    rts
mode1_load_chart_ready:
    lda f:STREAM_MODE1
    beq @done
    jmp mode1_initialize
@done:
    rts
mode1_hud_before:
    jsl stream_hud_before
    rts
mode1_hud_after:
    jsl stream_hud_after
    rts
stream_hud_draw:
    jsr draw_hud
    rtl
.ifdef SA1_FASTROM_MIRROR
stream_hud_draw_entry=stream_hud_draw+$800000
.else
stream_hud_draw_entry=stream_hud_draw
.endif
.segment "CAMERA"
stream_hud_before:
    stz stream_hud_pending
    lda f:STREAM_MODE1
    bne @done
    lda state
    cmp #1
    bne @draw
    lda f:STREAM_ENABLED
    beq @draw
    inc stream_hud_pending
    rtl
@draw:
    jsl stream_hud_draw_entry
@done:
    rtl
stream_hud_after:
    lda stream_hud_pending
    beq @ordinary
    stz stream_hud_pending
    jsl stream_hud_draw_entry
    rtl
@ordinary:
    lda f:STREAM_MODE1
    beq @done
    jsl stream_hud_draw_entry
@done:
    rtl
stream_hud_during_decode:
    lda stream_hud_pending
    beq @done
    stz stream_hud_pending
    lda step
    pha
    lda m7_logical_step
    sta step
    jsl stream_hud_draw_entry
    pla
    sta step
@done:
    rtl
.segment "FASTWRAM"
mode1_start_frame:
    ; Loading must finish the checkpoint snapshot before an async cache job.
    lda m7_loading
    bne @done
    lda f:STREAM_MODE1
    beq @done
    lda state
    cmp #1
    bne @done
    lda f:STREAM_MODE1
    cmp #2
    bcs @projection_ready
    lda f:M7_PROJECT_COS
    cmp #256
    bne @done
    lda f:M7_PROJECT_SIN
    bne @done
@projection_ready:
    lda f:SA1_PENDING
    bne @done
    jmp sa1_cache_begin
@done:
    rts
.segment "CODE"
mode1_raw_dma:
    jsr animation_dma
    rtl
.ifdef NEO_BUILD
.segment "NEOCODE"
.else
.segment "CODE"
.endif
mode1_restore_raw_atlas:
    stz stream_destination
@chunk:
.ifdef COMPACT_SNAPSHOT_SEEDS
.if COMPACT_SNAPSHOT_SEEDS >= 2
    lda f:STREAM_MODE1
    cmp #3
    bne @full_chunk
    lda f:M1_SNAPSHOT_BYTES
    and #$7FFF
    clc
    adc #32
    sec
    sbc stream_destination
    cmp #4097
    bcc @chunk_size
@full_chunk:
.endif
.endif
    lda #4096
@chunk_size:
    sta transfer_len
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    jsl $800000+mode1_raw_dma
    phb
    ldx #.loword(M7_CHR_LOW)
    ldy stream_destination
    lda transfer_len
    dec a
    mvn #$7E,#$43
    plb
    lda stream_destination
    clc
    adc transfer_len
    sta stream_destination
.ifdef COMPACT_SNAPSHOT_SEEDS
    lda f:STREAM_MODE1
    cmp #3
    bne @full_seed
    lda f:M1_SNAPSHOT_BYTES
    and #$7FFF
    clc
.if COMPACT_SNAPSHOT_SEEDS >= 2
    adc #32   ; exact visible atlas, including its blank glyph
.else
    adc #4127 ; legacy seeds rounded up to a 4096-byte DMA block
    and #$F000
.endif
    cmp stream_destination
    jne @chunk
    ; Compact seeds omit unused atlas tails. The back buffer's blank
    ; glyph must still be cleared before that buffer is first displayed.
    ; Wide atlases use $5000; ordinary atlases use $4000. Do not clear
    ; $4000 in wide mode: it can contain a live first-buffer glyph.
    ldx #$4000
.ifdef WIDE_SNAPSHOT_SUPPORT
    lda f:M1_GLYPH_COUNT
    cmp #640
    bne :+
    ldx #$5000
:
.endif
    ldy #16
    lda #0
@clear_blank:
    sta f:$430000,x
    inx
    inx
    dey
    bne @clear_blank
    rtl
@full_seed:
    lda stream_destination
.endif
.ifdef WIDE_SNAPSHOT_SUPPORT
    pha
    lda f:M1_GLYPH_COUNT
    cmp #640
    tax
    pla
    cpx #640
    bne :+
    cmp #40960
    bra :++
:
.endif
    cmp #32768
:
    jcc @chunk
    rtl
mode1_commit_map:
    stz pattern_skip_hud
    lda display_state
    cmp #2
    bne :+
    rtl
:
    lda f:STREAM_MODE1
    cmp #3
    bne @other_hud
    lda m7_upload_slots
    cmp #185
    bcc @hud_ready
    inc pattern_skip_hud
    bra @hud_ready
@other_hud:
    cmp #2
    bne @hud_ready
    ; Keep pending meter/text dirties for a smaller transfer frame. The
    ; projected track and all gameplay objects still publish atomically.
    lda m7_upload_slots
    .repeat 5
    asl a
    .endrepeat
    clc
    adc m7_row_span
    sta scratch
    lda m7_row_count
    .repeat 6
    asl a
    .endrepeat
    clc
    adc scratch
    sta scratch
    lda f:M1_RUN_COUNT
    .repeat 6
    asl a
    .endrepeat
    clc
    adc scratch
    sta scratch
    lda f:M1_RUN_COUNT
    asl a
    asl a
    sta scratch2
    lda scratch
    sec
    sbc scratch2
    cmp #3500
    bcc @hud_ready
    inc pattern_skip_hud
@hud_ready:
    lda m7_row_count
    jeq @palette
    tay
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda #^M1_MAP_STAGE
    sta $4304
    rep #$20
    .a16
    ldx #0
@map_run:
    lda f:M1_MAP_RUNS,x
    pha
    lsr a
    clc
    adc #$7000
    sta $2116
    pla
    clc
    adc #.loword(M1_MAP_STAGE)
    sta $4302
    lda f:M1_MAP_RUNS+2,x
    sta $4305
    start_dma 1
    inx
    inx
    inx
    inx
    dey
    bne @map_run
@palette:
    rtl

.segment "FASTWRAM"
mode1_commit_palette:
    lda display_state
    cmp #2
    bne :+
    rts
:
mode1_upload_palette:
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    jsl snapshot_commit_palette
    rts
:
    lda f:TRACK_PALETTE_DIRTY
    ora f:M1_READY
    bne :+
    rts
:
    sep #$20
    .a8
    lda #32
    sta $2121
    stz $4300
    lda #$22
    sta $4301
    lda #^M1_CGRAM
    sta $4304
    rep #$20
    .a16
    lda #.loword(M1_CGRAM)
    sta $4302
    lda #192
    sta $4305
    start_dma 1
    lda #0
    sta f:TRACK_PALETTE_DIRTY
    sta f:M1_READY
    rts

mode1_commit_patterns:
    ; A failed run keeps the last published track, just like Mode 7.
    ; Re-uploading its full atlas before the death HUD wastes VBlank.
    lda display_state
    cmp #2
    bne :+
    rts
:
    stz pattern_queue_count
    lda f:M1_RUN_COUNT
    beq @done
    tay
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4350
    lda #$18
    sta $4351
    lda #^M1_CHR_STAGE
    sta $4354
    rep #$20
    .a16
    ldx #0
@run:
    lda f:M1_PATTERN_RUNS,x
    sta $4352
    lsr a
    sta $2116
    lda f:M1_PATTERN_RUNS+2,x
    sta $4355
    start_dma 32
    inx
    inx
    inx
    inx
    dey
    bne @run
@done:
    lda f:STREAM_MODE1
    cmp #3
    bne :+
    lda #0
    sta f:M1_SNAPSHOT_DIRTY
    sta f:M1_PREFETCH_READY
    lda f:M1_BUILD_BANK
    sta f:M1_FRONT_BANK
    lda f:M1_BUILD_FORMAT
    sta f:M1_FRONT_FORMAT
:
    rts
.segment "CODE"
.endif

.ifdef SA1_MODE1_BUILD
.segment "CODE"
.endif

.ifdef SA1_MODE1_BUILD
.ifdef NEO_BUILD
.segment "NEOCODE"
.else
.segment "CODE"
.endif
mode1_prime_hdma_select:
    ; Select the incoming pose before a large DMA can cross scanline zero.
    ; HDMA latches its base table at frame start, before the final commit.
    lda f:STREAM_MODE1
    cmp #3
    bne mode1_hdma_select
    lda f:M1_SNAPSHOT_DIRTY
    beq mode1_hdma_select
    phy
    lda f:M1_BUILD_FORMAT
    tay
    lda f:M1_BUILD_BANK
    bra mode1_hdma_choose
mode1_hdma_select:
    phy
    lda f:M1_FRONT_FORMAT
    tay
    lda f:M1_FRONT_BANK
mode1_hdma_choose:
.ifdef WIDE_SNAPSHOT_SUPPORT
    pha
    sep #$20
    .a8
    lda #$50
    sta $210B
    rep #$20
    .a16
    pla
    beq :+
    tya
    and #2
    beq :+
    sep #$20
    .a8
    lda #$52
    sta $210B
    rep #$20
    .a16
:
.endif
    lda f:STREAM_MODE1
    beq @done
    ldx #.loword(hdma_mode1)
    tya
    and #1
    beq @done
    ldx #.loword(hdma_mode3)
@done:
    ply
    rtl
.segment "CODE"
.endif
