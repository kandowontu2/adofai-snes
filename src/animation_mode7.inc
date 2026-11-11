; Keep the visual landing state tied to accepted inputs. An early hit may
; light its floor immediately; a late hit must not light the next floor yet.
mode7_landing_time:
    lda chart_time
    sta f:M7_RENDER_TIME
    lda checkpoint_preroll
    bne @done
    lda step
    asl a
    tax
    lda f:NOTE_TIME,x
    cmp f:M7_RENDER_TIME
    bcc @next
    sta f:M7_RENDER_TIME
@next:
    lda step
    cmp last_note
    bcs @done
    inx
    inx
    lda f:NOTE_TIME,x
    cmp f:M7_RENDER_TIME
    beq @limit
    bcs @done
@limit:
    cmp #0
    beq @done
    dec a
    sta f:M7_RENDER_TIME
@done:
    rts

; MSU animation format 9: byte cell states, translated floors, authored
; alpha and tile palettes. Camera sampling and sprite projection are distinct matrices.
load_patterns:
.ifdef ROM_NATIVE_ADDR
    lda #0
    sta f:NATIVE_READY
.endif
.ifdef SA1_BUILD
    jsr reset_symbol_index
.endif
.ifdef SA1_BUILD
    jsr bitmap_prefetch_reset
.endif
.ifdef SA1_BUILD
    jsr symbol_coords_reset
.endif
.ifdef SA1_BUILD
    lda #256
    sta f:M7_ROT_COS
    sta f:M7_PROJECT_COS
    lda #0
    sta f:M7_ROT_SIN
    sta f:M7_PROJECT_SIN
    sta f:M7_RASTER_SHIFT
    sta f:M7_ORIGIN_X
    sta f:M7_ORIGIN_Y
    sta f:M7_ROT_PHASE
.endif
    lda chart_time
    sta f:M7_RENDER_TIME
    lda #0
    sta f:CAMERA_SCRIPT_ACTIVE
    sta f:M7_GLOBAL_REFS_ACTIVE
    sta f:M7_PREFETCH_ENABLED
    sta f:M7_PATTERN_WRITING
    sta f:M7_PREFETCH_CURSOR
    sta f:M7_PREFETCH_COUNT
    jsr reset_pattern_epoch
    lda #0
    ldx #0
@cells:
    sta f:CELL_STATE,x
    inx
    inx
    ; Only clear this chart's cells. The remaining WRAM holds the high
    ; CHR shadow and audio FIFO; clearing the old 32 KiB arena destroys
    ; initial textures in slots 224..255 after they have been uploaded.
    cpx animation_cells
    bcc @cells
    jsr mode7_references_reset
    stz pattern_queue_count
    stz animation_header
    stz m7_snapshot_chr
    stz m7_snapshot_chr+2
    lda #256
    sta camera_zoom
    sta camera_inverse
    lda animation_base
    sta animation_cursor
    lda animation_base+2
    sta animation_cursor+2
    lda last_note
    inc a
    sta animation_bytes
    ldx #0
    sep #$20
    .a8
    lda #3
@alpha:
    sta f:FLOOR_ALPHA,x
    inx
    cpx animation_bytes
    bcc @alpha
    rep #$20
    .a16
    lda #2
    sta animation_mode
    jsr update_pattern_cache
    stz animation_mode
    jsr mode7_cache_reset
    jmp mode7_invalidate

.ifdef SA1_BUILD
.segment "FASTWRAM"
.endif
animation_advance:
    clc
    adc animation_cursor
    sta animation_cursor
    bcc @done
    inc animation_cursor+2
@done:
    rts
animation_seek:
    lda animation_cursor
    sta msu_seek_offset
    lda animation_cursor+2
    sta msu_seek_offset+2
    jmp msu_seek_data
animation_read_begin:
    lda #1
    sta msu_data_busy
    lda animation_seek_dirty
    beq @done
    stz animation_seek_dirty
    jsr animation_seek
@done:
    rts
animation_read_coord:
    jsr animation_read_begin
    sep #$20
    .a8
    data_read8
    sta m7_coord
    data_read8
    sta m7_coord+1
    rep #$20
    .a16
    lda #2
    jsr animation_advance
    stz msu_data_busy
    rts

animation_read_xy:
.ifdef ROM_DATA_BUILD
    jsr animation_read_begin
    lda rom_data_ptr
    cmp #$FFFC
    bcs @bytes
    lda [rom_data_ptr]
    sta m7_cell_x
    ldy #2
    lda [rom_data_ptr],y
    sta m7_cell_y
    lda rom_data_ptr
    clc
    adc #4
    sta rom_data_ptr
    lda #4
    jsr animation_advance
    stz msu_data_busy
    rts
@bytes:
.endif
    jsr animation_read_coord
    lda m7_coord
    sta m7_cell_x
    jsr animation_read_coord
    lda m7_coord
    sta m7_cell_y
    rts

update_pattern_cache:
.ifdef ROM_NATIVE_ADDR
    lda animation_mode
    bne :+
    lda state
    cmp #1
    bne :+
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    jmp native_animation_update
:
.endif
    lda #1
    sta msu_data_busy
    stz pattern_queue_count
    inc pattern_queue_epoch
    jsr animation_seek
    stz animation_seek_dirty
    stz msu_data_busy
@record:
    jsr mode7_game_service
    lda animation_mode
    bne @read_record
    lda state
    cmp #1
    jne @done
@read_record:
    lda animation_header
    jne @time
    jsr animation_read_begin
.ifdef ROM_DATA_BUILD
    ; Most headers stay within one ROM bank. Read their words directly,
    ; advancing the source once instead of seven byte-pointer increments.
    ; The existing byte reader handles bank/window crossings exactly.
    lda rom_data_ptr
    cmp #$FFF9
    bcs @byte_header
    lda [rom_data_ptr]
    sta animation_time
    ldy #2
    lda [rom_data_ptr],y
    and #255
    sta animation_kind
    iny
    lda [rom_data_ptr],y
    sta animation_index
    iny
    iny
    lda [rom_data_ptr],y
    sta animation_value
    lda rom_data_ptr
    clc
    adc #7
    sta rom_data_ptr
    jmp @header_ready
@byte_header:
.endif
    sep #$20
    .a8
    data_read8
    sta animation_time
    data_read8
    sta animation_time+1
    data_read8
    sta animation_kind
    data_read8
    sta animation_index
    data_read8
    sta animation_index+1
    data_read8
    sta animation_value
    data_read8
    sta animation_value+1
    rep #$20
    .a16
@header_ready:
    lda #7
    jsr animation_advance
    stz msu_data_busy
    inc animation_header
@time:
    lda animation_time
    cmp #$FFFF
    jeq @done
    ldx animation_mode
    bne @loading_time
    cmp f:M7_RENDER_TIME
    bra @compare_time
@loading_time:
    cmp chart_time
@compare_time:
    beq @apply
    jcs @done
@apply:
    stz animation_header
    lda animation_mode
    cmp #1
    bne @dispatch
    ; The checkpoint's map/state pass already ran. Its CHR pass must not
    ; replay old wrapped map writes over that completed map.
    lda animation_kind
    and #255
    cmp #21
    bcs @dispatch
    cmp #4
    beq @dispatch
    cmp #5
    beq @skip_bytes
    cmp #14
    beq @skip_bytes
    cmp #8
    beq @skip_colors
    cmp #9
    beq @skip_spatial
    cmp #17
    bcc :+
    cmp #20
    bcc @skip_floor_run
    beq @dispatch

:
    jmp @record
@skip_floor_run:
    jsr animation_floor_run_size
    bra @skip_payload
@skip_colors:
    lda animation_value
    asl a
    clc
    adc animation_value
    bra @skip_payload
@skip_spatial:
    lda animation_value
    clc
    adc #4
    bra @skip_payload
@skip_bytes:
    lda animation_value
@skip_payload:
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    jmp @record
@dispatch:
    ; Event kinds are a dense byte enum. Dispatch once instead of testing
    ; every preceding kind for each sparse map, palette, and camera event.
    lda animation_kind
    and #255
    cmp #30
    bcs @unknown_kind
    asl a
    tax
    jmp (@handlers,x)
@unknown_kind:
    jmp @pattern
@handlers:
    .word @cell, @alpha, @x, @y, @pattern, @run, @zoom, @color
    .word @colors, @spatial_run, @camera_position, @camera_rotation
    .word @global_references, @camera_phase, @reference_set, @camera_projection
    .word @raster_scale
    .word @floor_run, @floor_run, @floor_run
    .word @pattern_batch
    .word @catchup, @jump_span
    .word @raster_origin, @bitmap_prefetch
    .word @raw_tags, @skip_raw
    .word @raw_tag_single
    .word @symbol_set
    .word @sparse_cells
@sparse_cells:
.ifdef SA1_BUILD
    jsr animation_sparse_cells
.endif
    jmp @record
@symbol_set:
.ifdef SA1_BUILD
    jsr animation_symbol_set
.else
    lda animation_value
    jsr animation_advance
    inc animation_seek_dirty
.endif
    jmp @record
@raw_tag_single:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:PATTERN_CURRENT,x
.ifdef ROM_PATTERN_ADDR
    jsr animation_restore_raw_pattern
.endif
    lda animation_index
    tax
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    jeq @record
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
    jmp @record
@raw_tags:
    lda animation_value
    pha
    lda animation_index
    sta animation_bytes
    jsr animation_read_begin
@raw_tag:
    sep #$20
    .a8
    data_read8
    sta animation_index
    data_read8
    sta animation_index+1
    data_read8
    sta animation_value
    data_read8
    sta animation_value+1
    rep #$20
    .a16
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:PATTERN_CURRENT,x
.ifdef ROM_PATTERN_ADDR
    jsr animation_restore_raw_pattern
.endif
    lda animation_index
    tax
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    beq :+
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
:
    dec animation_bytes
    jne @raw_tag
    pla
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    stz msu_data_busy
    jmp @record
@skip_raw:
    lda animation_value
    jsr animation_advance
    inc animation_seek_dirty
    jmp @record
@bitmap_prefetch:
.ifdef SA1_BUILD
    jsr bitmap_prefetch_read
.else
    lda #64
    jsr animation_advance
    inc animation_seek_dirty
.endif
    jmp @record
@raster_origin:
.ifdef SA1_BUILD
    lda animation_index
    sta f:M7_ORIGIN_X
    lda animation_value
    sta f:M7_ORIGIN_Y
.endif
    jmp @record
@catchup:
    lda animation_mode
    beq :+
    lda chart_time
    bra @catchup_time
:
    lda f:M7_RENDER_TIME
@catchup_time:
    cmp animation_index
    bcs @catchup_ready
    lda animation_value
    clc
    adc #7
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
@catchup_ready:
    jmp @record
@jump_span:
    lda animation_index
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    jmp @record
@pattern_batch:
    jsr animation_pattern_batch
    jmp @record
@floor_run:
    jsr animation_floor_run
    jmp @record
@raster_scale:
.ifdef SA1_BUILD
    lda animation_index
    sta f:M7_RASTER_SHIFT
.endif
    jmp @record
@global_references:
    lda animation_value
    sta f:M7_GLOBAL_REFS_ACTIVE
    jmp @record
@reference_set:
    jsr animation_reference_set
    jmp @record
@camera_phase:
.ifdef SA1_BUILD
    lda animation_index
    sta f:M7_ROT_PHASE
.endif
    jmp @record
@camera_projection:
.ifdef SA1_BUILD
    lda animation_index
    sta f:M7_PROJECT_COS
    lda animation_value
    sta f:M7_PROJECT_SIN
.endif
    jmp @record
@camera_rotation:
.ifdef SA1_BUILD
    lda animation_index
    sta f:M7_ROT_COS
    sta f:M7_PROJECT_COS
    lda animation_value
    sta f:M7_ROT_SIN
    sta f:M7_PROJECT_SIN
.endif
    jmp @record
@camera_position:
    lda animation_index
    sta f:CAMERA_SCRIPT_X
    lda animation_value
    sta f:CAMERA_SCRIPT_Y
    lda #1
    sta f:CAMERA_SCRIPT_ACTIVE
    jmp @record
@spatial_run:
    jsr animation_spatial_run
    jmp @record
@cell:
    jsr mode7_update_cell
    jmp @record
@alpha:
    ldx animation_index
    sep #$20
    .a8
    lda animation_value
    sta f:FLOOR_ALPHA,x
    rep #$20
    .a16
    jmp @record
@x:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:NOTE_X,x
.ifdef SA1_BUILD
    lda animation_index
    asl a
    ldx #2
    jsr symbol_coords_changed
.endif
    jmp @record
@y:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:NOTE_Y,x
.ifdef SA1_BUILD
    lda animation_index
    asl a
    ldx #2
    jsr symbol_coords_changed
.endif
    jmp @record
@run:
    jsr animation_cell_run
    jmp @record
@zoom:
    lda animation_index
    sta camera_zoom
    lda animation_value
    sta camera_inverse
    jmp @record
@color:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:TRACK_PALETTE,x
    jsr animation_palette_dirty
    jmp @record
@colors:
    ; One short DMA reserves the MSU port for all color changes at this
    ; timestamp. Per-color headers could starve 2x BRR audio of NMI slots.
    lda animation_value
    sta animation_bytes
    asl a
    clc
    adc animation_bytes
    sta transfer_len
    lda #.loword(TRACK_PALETTE_BATCH)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda transfer_len
    jsr animation_advance
    stz msu_data_busy
    lda #.loword(TRACK_PALETTE_BATCH)
    sta transfer_ptr
    sep #$20
    .a8
    lda #$7F
    sta transfer_ptr+2
    rep #$20
    .a16
    ldy #0
@color_word:
    lda [transfer_ptr],y
    and #255
    asl a
    tax
    iny
    lda [transfer_ptr],y
    sta f:TRACK_PALETTE,x
    jsr animation_palette_dirty
    iny
    iny
    dec animation_bytes
    bne @color_word
    jmp @record
@pattern:
    lda animation_index
    inc a
    sta f:M7_PATTERN_WRITING
    jsr animation_read_coord
    jsr animation_read_coord
    lda animation_mode
    cmp #2
    jeq @discard
    cmp #1
    jeq @restore
    ; PPU residency is chosen from the visible scene, independently of
    ; the compiler's logical pattern-slot reuse.
@restore:
    lda animation_index
    jsr mode7_pattern_destination
    lda #64
    sta transfer_len
    jsr animation_read_begin
    jsr animation_dma
    bra @pattern_end
@discard:
    lda #1
    sta animation_seek_dirty
@pattern_end:
    lda f:M7_GLOBAL_REFS_ACTIVE
    cmp #2
    beq :+
    ldx animation_index
    lda f:M7_VISIBLE_PATTERNS,x
    and #255
    beq @pattern_clean
:
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
@pattern_clean:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:PATTERN_CURRENT,x
    lda #0
    sta f:M7_PATTERN_WRITING
    lda #64
    jsr animation_advance
    stz msu_data_busy
    jmp @record
@done:
    stz msu_data_busy
    lda pattern_queue_count
    cmp pattern_peak_queued
    bcc @peak
    sta pattern_peak_queued
@peak:
    rts

; Runs retain their original byte span, so checkpoint offsets stay valid.
.segment "CODE"
animation_floor_run_size:
    lda animation_value
    dec a
    sta animation_bytes
    asl a
    asl a
    asl a
    sec
    sbc animation_bytes
    rts

animation_floor_run:
.ifdef SA1_BUILD
    lda animation_kind
    cmp #19
    beq :+
    lda animation_value
    asl a
    tax
    lda animation_index
    asl a
    jsr symbol_coords_changed
:
.endif
    lda animation_value
    asl a
    sta transfer_len
    lda animation_index
    asl a
    clc
    adc #.loword(NOTE_X)
    sta transfer_dest
    lda #^NOTE_X
    and #1
    sta transfer_wbank
    lda animation_kind
    cmp #17
    beq @copy
    cmp #18
    bne @alpha
    lda transfer_dest
    clc
    adc #.loword(NOTE_Y-NOTE_X)
    sta transfer_dest
    bra @copy
@alpha:
    lda animation_value
    sta transfer_len
    lda animation_index
    clc
    adc #.loword(FLOOR_ALPHA)
    sta transfer_dest
    lda #(^FLOOR_ALPHA)&1
    sta transfer_wbank
@copy:
    jsr animation_read_begin
    jsr animation_dma
    jsr animation_floor_run_size
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    stz msu_data_busy
    rts

; Sparse pattern batches retain checkpoint offsets. Every tag is restored,
; including the map-only startup pass, which already has its pixel snapshot.
animation_pattern_batch:
    lda animation_mode
    cmp #2
    jeq animation_pattern_batch_restore
    lda animation_value
    pha
    sta animation_bytes
    jsr animation_read_begin
@stream:
    sep #$20
    .a8
    data_read8
    sta animation_index
    data_read8
    sta animation_index+1
    data_read8
    sta animation_value
    data_read8
    sta animation_value+1
    rep #$20
    .a16
    lda animation_index
    jsr mode7_pattern_destination
    lda #64
    sta transfer_len
    jsr animation_dma
    ; Publish the generation only after all bitmap bytes are available.
    ; A new tag must never describe the previous contents of this slot.
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:PATTERN_CURRENT,x
    jsr audio_pump
    dec animation_bytes
    bne @stream
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
    pla
    ; Form 75*N - 7, the unchanged byte span after the batch header.
    sta animation_bytes
    asl a
    clc
    adc animation_bytes
    asl a
    asl a
    asl a
    clc
    adc animation_bytes
    sta animation_bytes
    asl a
    clc
    adc animation_bytes
    sec
    sbc #7
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    stz msu_data_busy
    rts

animation_pattern_batch_restore:
    lda animation_value
    pha
    sta animation_bytes
@next:
    jsr audio_pump
    jsr animation_read_xy
    lda m7_cell_x
    sta animation_index
    lda m7_cell_y
    sta animation_value
    lda animation_mode
    cmp #2
    beq @discard
    lda animation_index
    jsr mode7_pattern_destination
    lda #64
    sta transfer_len
    jsr animation_read_begin
    jsr animation_dma
    bra @tag
@discard:
    lda #1
    sta animation_seek_dirty
@tag:
    lda animation_index
    asl a
    tax
    lda animation_value
    sta f:PATTERN_CURRENT,x
    lda #64
    jsr animation_advance
    stz msu_data_busy
    dec animation_bytes
    bne @next
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
    pla
    dec a
    sta animation_bytes
    asl a
    asl a
    asl a
    sec
    sbc animation_bytes
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    rts

animation_cell_run:
    lda animation_value
    sta animation_bytes
    sta transfer_len
    lda #.loword(M7_RUN_VALUES)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda transfer_len
    jsr animation_advance
    stz msu_data_busy
    stz m7_run_index
@cell:
    ldx m7_run_index
    lda f:M7_RUN_VALUES,x
    and #255
    sta animation_value
    jsr mode7_update_cell
    inc animation_index
    inc m7_run_index
    dec animation_bytes
    bne @cell
    rts

; Contiguous world-row cells share one DMA, one clip, and a block copy.
; Off-screen changes need no coordinate lookup or dirty-map work.
.ifdef SA1_BUILD
.segment "FASTWRAM"
.endif
animation_spatial_run:
    lda animation_value
    sta animation_bytes
    jsr animation_read_xy
    lda animation_bytes
    sta transfer_len
    lda f:M7_GLOBAL_REFS_ACTIVE
    cmp #2
    bne @buffered
    lda animation_index
    bra @destination
@buffered:
    lda #.loword(M7_RUN_VALUES)
@destination:
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda transfer_len
    jsr animation_advance
    stz msu_data_busy
    lda animation_index
    pha
    lda f:M7_GLOBAL_REFS_ACTIVE
    cmp #2
    beq @references_done
    stz m7_run_index
@reference:
    ldx m7_run_index
    lda f:M7_RUN_VALUES,x
    and #255
    sta animation_value
    ldx animation_index
    lda f:CELL_STATE,x
    and #255
    cmp animation_value
    beq @reference_next
    jsr mode7_reference_change
    sep #$20
    .a8
    lda animation_value
    sta f:CELL_STATE,x
    rep #$20
    .a16
@reference_next:
    inc animation_index
    inc m7_run_index
    lda m7_run_index
    cmp animation_bytes
    bcc @reference
@references_done:
    pla
    sta animation_index
    lda animation_mode
    jne @done
    lda m7_cell_y
    and #127
    .repeat 7
    asl a
    .endrepeat
    sta scratch2
    lda m7_cell_x
    and #127
    ora scratch2
    sta m7_coord
@part:
    lda m7_coord
    and #127
    sta scratch
    lda #128
    sec
    sbc scratch
    cmp animation_bytes
    bcc :+
    lda animation_bytes
:
    sta m7_run_index
    lda m7_coord
    clc
    adc #.loword(M7_MAP)
    tay
    ldx animation_index
    lda m7_run_index
.ifdef SA1_BUILD
    jsr animation_wram_to_cartridge
.else
    dec a
    phb
    mvn #$7F,#.bankbyte(M7_MAP)
    plb
.endif
    lda animation_index
    clc
    adc m7_run_index
    sta animation_index
    lda m7_coord
    clc
    adc m7_run_index
    dec a
    sta transfer_len
@dirty:
    jsr mode7_mark_dirty
    lda m7_coord
    clc
    adc #16
    cmp transfer_len
    bcs @last
    sta m7_coord
    bra @dirty
@last:
    lda transfer_len
    sta m7_coord
    jsr mode7_mark_dirty
    lda animation_bytes
    sec
    sbc m7_run_index
    sta animation_bytes
    beq @done
    lda transfer_len
    and #$3F80
    sta m7_coord
    bra @part
@done:
    rts

; Active pattern slots are computed offline from exactly the same cell
; events, including invisible cells leaving the camera neighborhood.
.ifdef SA1_BUILD
.segment "FASTNMI"
.endif
animation_reference_set:
    lda #2
    sta f:M7_GLOBAL_REFS_ACTIVE
    lda animation_value
    sta transfer_len
    sta f:M7_CACHE_ACTIVE_COUNT
    lda #.loword(M7_RUN_VALUES)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda transfer_len
    jsr animation_advance
.ifdef SA1_BUILD
    ldx #.loword(M7_RUN_VALUES)
    ldy #.loword(M7_VISIBLE_LIST)
    lda transfer_len
    jsr animation_wram_to_cartridge
.else
    phb
    ldx #.loword(M7_RUN_VALUES)
    ldy #.loword(M7_VISIBLE_LIST)
    lda transfer_len
    dec a
    mvn #$7F,#.bankbyte(M7_VISIBLE_LIST)
    plb
.endif
    stz msu_data_busy
    lda #1
    sta f:M7_POOL_DIRTY
    sta f:M7_CACHE_DIRTY
    rts

.segment "CODE"
.ifdef SA1_BUILD
; Copy a WRAM-$7F span into cartridge RAM-$41 through the WRAM data
; port. DMA takes eight master clocks per byte; CPU MVN took 56 or more.
; X=WRAM offset, Y=cartridge offset, A=length. Both callers own the map.
animation_wram_to_cartridge:
    pha
    lda #1
    sta msu_data_busy
    pla
    sta $4305
    stx $2181
    sty $4302
    lda #1
    sep #$20
    .a8
    sta $2183
    lda #$80
    sta $4300
    sta $4301
    lda #$41
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    stz msu_data_busy
    rts
.endif
animation_dma:
.ifdef LARGE_CHART_BUILD
    lda transfer_wbank
    cmp #$40
    bne @wram
    lda transfer_len
    beq @cartridge_done
    phy
    ldy #0
    sep #$20
    .a8
@cartridge_byte:
    data_read8
    sta [transfer_dest],y
    iny
    cpy transfer_len
    bcc @cartridge_byte
    rep #$20
    .a16
    ply
@cartridge_done:
    rts
@wram:
.endif
.ifdef ROM_DATA_BUILD
    jmp rom_data_dma
.else
    lda transfer_len
    beq @done
    sta $4305
    lda transfer_dest
    sta $2181
    lda #$2001
    sta $4302
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    stz $4304
    lda #8
    sta $4300
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
@done:
    rts
.endif

reset_pattern_epoch:
    stz pattern_queue_epoch
    stz m7_pattern_head
    stz m7_pattern_tail
    stz m7_pattern_count
    lda #0
    sta f:M7_CACHE_READY
    rts
.if 0
    lda #$FFFF
    ldx #0
@word:
    sta f:M7_PATTERN_POSITION,x
    inx
    inx
    cpx #512
    bcc @word
    lda #0
    ldx #0
@selected:
    sta M7_PATTERN_SELECTED,x
    inx
    inx
    cpx #256
    bcc @selected
    rts

restore_pattern_cache:
.endif
restore_pattern_cache:
    lda #256
.ifdef ROM_NATIVE_ADDR
    pha
    lda #0
    sta f:NATIVE_READY
    pla
.endif
    sta camera_zoom
    sta camera_inverse
    lda #0
    sta f:M7_PREFETCH_ENABLED
    lda msu_checkpoint_index
    asl a
    asl a
    clc
    adc animation_table
    sta msu_seek_offset
    lda animation_table+2
    adc #0
    sta msu_seek_offset+2
    jsr msu_seek_data
    sep #$20
    .a8
    ldx #0
@address:
    data_read8
    sta msu_seek_offset,x
    inx
    cpx #4
    bcc @address
    rep #$20
    .a16
    jsr msu_seek_data
    sep #$20
    .a8
    ldx #0
@header:
    data_read8
    sta snapshot_header,x
    inx
    cpx #18
    bcc @header
    rep #$20
    .a16
.ifdef SA1_BUILD
    lda #256
    sta f:M7_ROT_COS
    sta f:M7_PROJECT_COS
    lda #0
    sta f:M7_ROT_SIN
    sta f:M7_PROJECT_SIN
    sta f:M7_RASTER_SHIFT
    sta f:M7_ORIGIN_X
    sta f:M7_ORIGIN_Y
    sta f:M7_ROT_PHASE
    sta f:M7_SNAPSHOT_EXTRA
    lda snapshot_header+2
    cmp #$3953
    beq @rotation_snapshot
    cmp #$3853
    beq @rotation_snapshot
    cmp #$3753
    beq @rotation_snapshot
    cmp #$3653
    jne @old_snapshot
@rotation_snapshot:
    sep #$20
    .a8
    data_read8
    sta f:M7_ROT_COS
    data_read8
    sta f:M7_ROT_COS+1
    data_read8
    sta f:M7_ROT_SIN
    data_read8
    sta f:M7_ROT_SIN+1
    data_read8
    sta f:M7_ROT_PHASE
    data_read8
    sta f:M7_ROT_PHASE+1
    rep #$20
    .a16
    lda #6
    sta f:M7_SNAPSHOT_EXTRA
    lda f:M7_ROT_COS
    sta f:M7_PROJECT_COS
    lda f:M7_ROT_SIN
    sta f:M7_PROJECT_SIN
    lda snapshot_header+2
    cmp #$3753
    jcc @old_snapshot
    sep #$20
    .a8
    data_read8
    sta camera_zoom
    data_read8
    sta camera_zoom+1
    data_read8
    sta camera_inverse
    data_read8
    sta camera_inverse+1
    data_read8
    sta f:M7_PROJECT_COS
    data_read8
    sta f:M7_PROJECT_COS+1
    data_read8
    sta f:M7_PROJECT_SIN
    data_read8
    sta f:M7_PROJECT_SIN+1
    rep #$20
    .a16
    lda #14
    sta f:M7_SNAPSHOT_EXTRA
    lda snapshot_header+2
    cmp #$3853
.ifdef ROM_DATA_BUILD
    jcc @old_snapshot
.else
    bcc @old_snapshot
.endif
    sep #$20
    .a8
    data_read8
    sta f:M7_RASTER_SHIFT
    data_read8
    sta f:M7_RASTER_SHIFT+1
    rep #$20
    .a16
    lda #16
    sta f:M7_SNAPSHOT_EXTRA
    lda snapshot_header+2
    cmp #$3953
    bne @old_snapshot
    sep #$20
    .a8
    data_read8
    sta f:M7_ORIGIN_X
    data_read8
    sta f:M7_ORIGIN_X+1
    data_read8
    sta f:M7_ORIGIN_Y
    data_read8
    sta f:M7_ORIGIN_Y+1
    rep #$20
    .a16
    lda #20
    sta f:M7_SNAPSHOT_EXTRA
@old_snapshot:
.endif
    lda snapshot_header+14
    sta f:CAMERA_SCRIPT_X
    lda snapshot_header+16
    sta f:CAMERA_SCRIPT_Y
    lda #1
    sta f:CAMERA_SCRIPT_ACTIVE
    lda snapshot_header+4
    clc
    adc animation_base
    sta animation_cursor
    sta m7_snapshot_cursor
    lda snapshot_header+6
    adc animation_base+2
    sta animation_cursor+2
    sta m7_snapshot_cursor+2
    lda snapshot_header+10
    asl a
    asl a
    clc
    adc snapshot_header+10
    clc
    adc #210
.ifdef SA1_BUILD
    clc
    adc f:M7_SNAPSHOT_EXTRA
.endif
    clc
    adc snapshot_header+8
    clc
    adc msu_seek_offset
    sta m7_snapshot_chr
    lda msu_seek_offset+2
    adc #0
    sta m7_snapshot_chr+2
    lda #192
    sta transfer_len
    lda #.loword(TRACK_PALETTE)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda #192
    sta f:TRACK_PALETTE_DIRTY
    lda snapshot_header+8
    sta transfer_len
    lda #.loword(CELL_STATE)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda snapshot_header+10
    asl a
    sta transfer_len
    lda #.loword(NOTE_X)
    sta transfer_dest
    lda #(^NOTE_X)&1
    sta transfer_wbank
    jsr animation_dma
    jsr mode7_references_rebuild
    lda #1
    sta f:M7_GLOBAL_REFS_ACTIVE
    lda #.loword(NOTE_Y)
    sta transfer_dest
    lda #(^NOTE_Y)&1
    sta transfer_wbank
    jsr animation_dma
    lda snapshot_header+10
    sta transfer_len
    lda #.loword(FLOOR_ALPHA)
    sta transfer_dest
    lda #.bankbyte(FLOOR_ALPHA)-$7E
    sta transfer_wbank
    jsr animation_dma
    stz animation_header
    lda #2
    sta animation_mode
    jsr update_pattern_cache
    stz animation_mode
    jsr reset_pattern_epoch
    jmp mode7_invalidate

; The old death scene stays on screen while its replacement map is built.
; Read and patch the CHR shadow only once that replacement is ready.
mode7_finish_snapshot:
    lda m7_snapshot_chr
    ora m7_snapshot_chr+2
    jeq @done
    lda m7_snapshot_chr
    sta msu_seek_offset
    lda m7_snapshot_chr+2
    sta msu_seek_offset+2
    jsr msu_seek_data
    lda #14336
    sta transfer_len
    lda #.loword(CHR_RAM)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
    lda #2048
    sta transfer_len
    lda #.loword(M7_CHR_HIGH)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda m7_snapshot_cursor
    sta animation_cursor
    lda m7_snapshot_cursor+2
    sta animation_cursor+2
    ; A snapshot stores pixels, not the logical pattern IDs that produced
    ; them. IDs left over from before death must not identify these pixels.
    ; Give each restored slot its own reserved identity until a stream
    ; update supplies its real ID. Slot zero remains the blank pattern.
    lda #0
    sta f:PATTERN_CURRENT
    ldx #2
@snapshot_tag:
    txa
    lsr a
    ora #$FE00
    sta f:PATTERN_CURRENT,x
    inx
    inx
    cpx #512
    bcc @snapshot_tag
    stz animation_header
    lda #1
    sta animation_mode
    jsr update_pattern_cache
    stz animation_mode
    sep #$20
    .a8
    lda #$80
    sta $2100
    rep #$20
    .a16
    jsr mode7_upload_chr
    stz m7_snapshot_chr
    stz m7_snapshot_chr+2
    jsr reset_pattern_epoch
@done:
    rts

.ifdef SA1_BUILD
bitmap_prefetch_reset:
    lda #0
    sta f:M7_BITMAP_HEAD
    sta f:M7_BITMAP_TAIL
    jsr spill_reset
    ldx selected_level
    lda level_bitmap_prefetch,x
    and #255
    sta f:M7_BITMAP_ENABLED
.ifdef ROM_FUTURE_COUNT
    beq :+
    lda #ROM_FUTURE_COUNT
    sta f:M7_BITMAP_HEAD
:
.endif
    lda #$FFFF
    ldx #0
@tag:
    sta f:M7_FUTURE_TAGS,x
    sta f:M7_FUTURE_DEADLINES,x
    inx
    inx
    cpx #512
    bcc @tag
    rts

bitmap_prefetch_read:
    lda animation_mode
    jne @skip
    lda f:M7_BITMAP_HEAD
    inc a
    cmp #M7_BITMAP_COUNT
    bcc :+
    lda #0
:
    cmp f:M7_BITMAP_TAIL
    jeq @skip
    pha
    lda f:M7_BITMAP_HEAD
    asl a
    asl a
    asl a
    tax
    lda animation_index
    sta f:M7_BITMAP_META,x
    lda animation_value
    sta f:M7_BITMAP_META+2,x
    jsr animation_read_coord
    lda m7_coord
    sta f:M7_BITMAP_META+4,x
    lda #.loword(M7_BITMAP_BUFFER)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    lda #64
    sta transfer_len
    jsr animation_read_begin
    jsr animation_dma
    lda #.loword(M7_BITMAP_BUFFER)
    sta $2181
    sep #$20
    .a8
    lda #1
    sta $2183
    lda #$80
    sta $4340
    sta $4341
    rep #$20
    .a16
    lda f:M7_BITMAP_HEAD
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_BITMAP_SRAM)
    sta $4342
    lda #.bankbyte(M7_BITMAP_SRAM)
    adc #0
    sep #$20
    .a8
    sta $4344
    rep #$20
    .a16
    lda #64
    sta $4345
    lda #$C010
    sta $420B
    lda #64
    jsr animation_advance
    stz msu_data_busy
    pla
    sta f:M7_BITMAP_HEAD
    rts
@skip:
    lda #66
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    rts
.endif

animation_palette_dirty:
    txa
    inc a
    inc a
    cmp f:TRACK_PALETTE_DIRTY
    bcc @done
    sta f:TRACK_PALETTE_DIRTY
@done:
    rts

.ifdef ROM_PATTERN_ADDR
; During checkpoint replay the restored WRAM image must follow raw tags
; as well. Ordinary play uploads resident ROM tiles directly, so it needs
; no shadow copy. Snapshot-only FE identities retain their WRAM source.
animation_restore_raw_pattern:
    lda animation_mode
    cmp #1
    jne @done
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    jne @done
    lda msu_data_busy
    pha
    lda #1
    sta msu_data_busy
    lda animation_value
    .repeat 10
    lsr a
    .endrepeat
    clc
    adc #.bankbyte(ROM_PATTERN_ADDR)
    sta transfer_ptr+2
    lda animation_value
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(ROM_PATTERN_ADDR)
    sta transfer_ptr
    bcc :+
    inc transfer_ptr+2
:
    lda animation_index
    jsr mode7_pattern_destination
.ifdef ROM_PATTERN_PAGED
    ; Checkpoint replay runs with the worker idle. Its C0 selection also
    ; updates the mailbox, keeping the next cartridge DMA's page current.
    lda transfer_ptr+2
    and #255
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    inc a
    pha
    dec a
    sep #$20
    .a8
    sta $2220
    rep #$20
    .a16
    pla
    sta f:SA1_ROM_CURRENT
    pla
    and #15
    ora #$C0
    sta transfer_ptr+2
.endif
    lda transfer_dest
    sta $2181
    lda transfer_ptr
    sta $4302
    lda #64
    sta $4305
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    lda transfer_ptr+2
    sta $4304
    stz $4300
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    pla
    sta msu_data_busy
@done:
    rts
.endif

.ifdef SA1_BUILD
; Sparse changes share one data transfer and one SA-1 job. The CPU retains
; the complete checkpoint state; the worker updates wrapped map cells.
animation_sparse_cells:
    lda animation_index
    sta animation_bytes
    lda animation_value
    pha
    sta transfer_len
    lda #.loword(M7_RUN_VALUES)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda #.loword(M7_RUN_VALUES)
    sta transfer_ptr
    sep #$20
    .a8
    lda #^M7_RUN_VALUES
    sta transfer_ptr+2
    rep #$20
    .a16
    ldy #0
@state:
    lda [transfer_ptr],y
    tax
    iny
    iny
    iny
    iny
    lda [transfer_ptr],y
    sep #$20
    .a8
    sta f:CELL_STATE,x
    rep #$20
    .a16
    iny
    dec animation_bytes
    bne @state
    lda animation_mode
    bne @done
    lda #.loword(M7_RUN_VALUES)
    sta $2181
    sep #$20
    .a8
    lda #(^M7_RUN_VALUES)&1
    sta $2183
    lda #$80
    sta $4340
    sta $4341
    lda #^M7_SPARSE_BATCH
    sta $4344
    rep #$20
    .a16
    lda #.loword(M7_SPARSE_BATCH)
    sta $4342
    lda transfer_len
    sta $4345
    lda #$C010
    sta $420B
    lda animation_index
    sta a:SA1_LOCAL_EVENTS
    lda #0
    sta f:SA1_DONE
    lda #5
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
@wait:
    jsr audio_pump
    lda $2300
    and #$80
    beq @wait
@done:
    pla
    jsr animation_advance
    lda #1
    sta animation_seek_dirty
    stz msu_data_busy
    rts

animation_symbol_set:
    lda animation_value
    sta event_count
    sta animation_bytes
    stz m7_run_index
    jeq @done
@chunk:
    lda animation_bytes
    cmp #257
    bcc :+
    lda #256
:
    sta transfer_len
    lda #.loword(M7_RUN_VALUES)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda #.loword(M7_RUN_VALUES)
    sta $2181
    sep #$20
    .a8
    lda #1
    sta $2183
    lda #$80
    sta $4340
    sta $4341
    lda #.bankbyte(TRACK_SYMBOL_FLOORS)
    sta $4344
    rep #$20
    .a16
    lda m7_run_index
    clc
    adc #.loword(TRACK_SYMBOL_FLOORS)
    sta $4342
    lda transfer_len
    sta $4345
    lda #$C010
    sta $420B
    lda transfer_len
    jsr animation_advance
    lda m7_run_index
    clc
    adc transfer_len
    sta m7_run_index
    lda animation_bytes
    sec
    sbc transfer_len
    sta animation_bytes
    bne @chunk
@done:
    stz msu_data_busy
    rts
.endif
