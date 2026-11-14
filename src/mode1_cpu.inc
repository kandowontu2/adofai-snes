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
    ldy #.loword(M1_PALETTE)
    lda #96
    jsr mode1_read_seed_block
    ldy #.loword(M1_MAP_STAGE)
    lda #4096
    jsr mode1_read_seed_block
    lda f:STREAM_MODE1
    cmp #2
    bcc @dictionary_seed
    jsl mode1_restore_raw_atlas
    bra @atlas_ready
@dictionary_seed:
    ldy #.loword(STREAM_BUFFER)
    lda #2048
    jsr mode1_read_seed_block
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
    lda #0
    sta f:SPILL_OAM_BYTES
    jsr symbol_world_bounds
    jsr sa1_symbols
mode1_icons_ready = *
    lda f:SPILL_OAM_BYTES
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
    lda #4096
    sta transfer_len
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    jsl $800000+mode1_raw_dma
    phb
    ldx #.loword(M7_CHR_LOW)
    ldy stream_destination
    lda #4095
    mvn #$7E,#$43
    plb
    lda stream_destination
    clc
    adc #4096
    sta stream_destination
    cmp #32768
    bcc @chunk
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
:
    rts
.segment "CODE"
.endif

.ifdef SA1_MODE1_BUILD
.segment "CODE"
.endif
