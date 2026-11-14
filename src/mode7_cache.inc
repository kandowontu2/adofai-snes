; Logical chart slots and physical PPU slots have independent generations.
; Keep the old viewport resident until its replacement is complete.
mode7_cache_reset:
.if .defined(SA1_WRAM_RENDERER) .and .defined(SA1_BUILD)
    lda f:M7_CACHE_RESET_SERIAL
    inc a
    sta f:M7_CACHE_RESET_SERIAL
.endif
.ifdef SA1_BUILD
.ifndef SA1_WORKER
    jsr symbol_coords_reset
.endif
.endif
    lda #0
    sta f:M7_CACHE_READY
    sta f:M7_TAG_COUNT
    sta M7_CACHE_FREE
    sta f:M7_CACHE_WAIT
    sta f:M7_CACHE_ERRORS
    sta f:M7_CACHE_MAX_VISIBLE
    sta f:M7_CACHE_ABORT
    sta f:M7_CACHE_UNCHANGED
    sta f:M7_TRANSITION_DEFERRALS
    sta f:M7_IDENTITY_MODE
    sta f:M7_PREFETCH_CURSOR
    lda #1
    sta f:M7_CACHE_DIRTY
    sta f:M7_POOL_DIRTY
    sta f:M7_HASH_DIRTY
    lda #$FFFF
    sta f:M7_STAGE_BASE_X
    sta f:M7_STAGE_BASE_Y
    stz pattern_queue_count
    ldx #0
@slot:
    txa
    sep #$20
    .a8
    sta M7_LOGICAL_TO_PPU,x
    sta f:M7_DISPLAY_TO_PPU,x
    lda #0
    sta M7_NEW_VISIBLE,x
    sta M7_OLD_VISIBLE,x
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    inx
    cpx #256
    bcc @slot
    ldx #0
@tag:
    lda f:PATTERN_CURRENT,x
    sta f:M7_PATTERN_VRAM,x
    inx
    inx
    cpx #512
    bcc @tag
    rts

mode7_cache_commit:
.ifdef SA1_MODE1_BUILD
    lda f:STREAM_MODE1
    beq :+
    rts
:
.endif
.ifdef SA1_WORKER
    jsr worker_commit_tags
    jsr worker_spill_commit
.elseif .defined(SA1_BUILD)
    lda f:M7_TAG_COUNT
    ora f:SPILL_TAG_COUNT
    bne @worker
.endif
    lda f:M7_MASKS_CHANGED
    beq @done
    lda f:M7_CACHE_UNCHANGED
    bne @done
    lda display_state
    cmp #1
    bne @done
.ifdef SA1_BUILD
.ifndef SA1_WORKER
@worker:
    jmp sa1_cache_commit
.endif
.endif
    phb
    lda #255
    ldx #.loword(M7_NEW_VISIBLE)
    ldy #.loword(M7_OLD_VISIBLE)
    mvn #.bankbyte(M7_NEW_VISIBLE),#.bankbyte(M7_OLD_VISIBLE)
    lda f:M7_IDENTITY_MODE
    beq @mapping
    lda f:M7_STAGE_FORCE
    beq @mapped
@mapping:
    lda #255
    ldx #.loword(M7_LOGICAL_TO_PPU)
    ldy #.loword(M7_DISPLAY_TO_PPU)
    mvn #.bankbyte(M7_LOGICAL_TO_PPU),#.bankbyte(M7_DISPLAY_TO_PPU)
@mapped:
    plb
@done:
    rts

mode7_cache_prepare:
.ifdef SA1_BUILD
.ifndef SA1_WORKER
    lda sa1_async
    beq :+
    jmp sa1_cache_begin
:
    jmp sa1_cache_prepare
.endif
.endif
.if .defined(SA1_WRAM_RENDERER) .and .defined(SA1_WORKER)
    lda f:M7_CACHE_RESET_SERIAL
    cmp M7_CACHE_SERIAL_SEEN
    beq @private_ready
    sta M7_CACHE_SERIAL_SEEN
    lda #0
    ldx #0
@private_masks:
    sta M7_NEW_VISIBLE,x
    sta M7_OLD_VISIBLE,x
    sta M7_PATTERN_SELECTED,x
    inx
    inx
    cpx #256
    bcc @private_masks
    ldx #0
@private_spill:
    sta f:SPILL_LOGICAL,x
    inx
    inx
    cpx #256
    bcc @private_spill

    phb
    lda #255
    ldx #$F000
    ldy #.loword(M7_LOGICAL_TO_PPU)
    mvn #$41,#$00
    plb
@private_ready:
.endif
 .ifdef SA1_WORKER
    lda f:M7_CACHE_ABORT
    beq :+
    jsr worker_recover_prefetch
:
.endif
 .ifdef SA1_WORKER
    jsr worker_spill_begin
.endif
    lda #0
    sta f:M7_CACHE_UNCHANGED
    sta f:M7_CACHE_ABORT
    sta f:M7_MASKS_CHANGED
    sta f:M7_STAGE_FORCE
.ifdef SA1_WORKER
    sta M7_MAP_PREPARED
    sta M7_BULK_ROWS
    sta M7_ROW_CODE_VALID
    sta NATIVE_ROW_UNDO
    sta f:M7_FORCE_SKIP_HUD
    lda f:M7_UPLOAD_LIMIT
    sta M7_CACHE_BUDGET
.endif
.ifdef SA1_BUILD
    lda f:M7_VIEW_X
.else
    lda cam_x
    jsr mode7_floor8
.endif
    sta f:M7_CACHE_TARGET_X
    cmp f:M7_CACHE_LOCAL_X
    bne @changed
.ifdef SA1_BUILD
    lda f:M7_VIEW_Y
.else
    lda cam_y
    clc
    adc #32
    jsr mode7_floor8
.endif
    sta f:M7_CACHE_TARGET_Y
    cmp f:M7_CACHE_LOCAL_Y
    bne @changed
.ifdef SA1_BUILD
    lda f:M7_VIEW_W
.else
    lda cam_x
    and #7
    beq :+
    lda #1
:
    clc
    adc #32
.endif
    cmp f:M7_CACHE_LOCAL_W
    bne @changed
.ifdef SA1_BUILD
    lda f:M7_VIEW_H
.else
    lda cam_y
    and #7
    beq :+
    lda #1
:
    clc
    adc #16
.endif
    cmp f:M7_CACHE_LOCAL_H
    bne @changed
    lda f:M7_CACHE_DIRTY
    bne @changed
    lda f:M7_POOL_DIRTY
    bne @changed
    stz pattern_queue_count
    stz m7_upload_slots
    stz m7_row_count
    stz m7_row_span
    lda #1
    sta f:M7_CACHE_UNCHANGED
    jsr mode7_cache_future
    rts
@changed:
    lda f:M7_POOL_DIRTY
    bne @pool_changed
    stz pattern_queue_count
    stz m7_upload_slots
    jmp @map
@pool_changed:
    lda #1
    sta f:M7_MASKS_CHANGED
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda f:STREAM_ENABLED
    beq @ordinary_pool
    jsr mode7_cache_fixed_prepare
    lda f:M7_CACHE_ATOMIC
    cmp f:M7_UPLOAD_LIMIT
    bcc @stream_fixed
    beq @stream_fixed
    jmp @versioned
@stream_fixed:
    jmp @retained
@ordinary_pool:
.endif
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
.ifdef ROM_DIRECT_UNTIL
    lda f:M7_RENDER_TIME
    cmp #ROM_DIRECT_UNTIL
    bcs @versioned
    jsr mode7_cache_fixed_prepare
    jmp @retained
.endif
    jmp @versioned
:
.endif
 .ifdef SA1_BUILD
    lda f:M7_BITMAP_ENABLED
    bne @versioned
.endif
    jsr mode7_cache_identity
    bcc @versioned
    lda #0
    sta f:M7_POOL_DIRTY
    jmp @map
@versioned:
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    jsr worker_cache_code
.endif
    lda #0
    sta f:M7_IDENTITY_MODE
    lda #6
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda #0
    sta f:M7_CACHE_ABORT
    jsr mode7_visible_patterns
    jsr mode7_cache_hash
.ifdef SA1_BUILD
    lda f:M7_UPLOAD_LIMIT
.else
    lda #16
.endif
    sta M7_CACHE_BUDGET
    lda #7
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda #0
    sta f:M7_CACHE_REMAIN
    sta f:M7_CACHE_ATOMIC
    sta M7_CACHE_SCAN
    ldx #0
@clear:
    sta M7_NEW_VISIBLE,x
    sta M7_PATTERN_SELECTED,x
.ifdef SA1_WORKER
    sta f:M7_VISIBLE_PATTERNS,x
.endif
    inx
    inx
    cpx #256
    bcc @clear
    ; Protect every resident pattern needed by the new scene before an
    ; allocator may evict anything, regardless of logical scan order.
    lda #0
    sta M7_CACHE_ACTIVE_CURSOR
.ifdef SA1_WORKER
    sta M7_CACHE_MISSING_COUNT
.endif
.if .defined(SA1_WORKER) .and .defined(SA1_WRAM_RENDERER) .and .defined(ROM_PATTERN_COUNT)
    jmp @retain
.segment "HOTCACHE"
.endif
@retain:
    lda M7_CACHE_ACTIVE_CURSOR
    tax
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
.ifdef SA1_WORKER
    sep #$20
    .a8
    lda #1
    sta f:M7_VISIBLE_PATTERNS,x
    rep #$20
    .a16
.endif
    lda M7_LOGICAL_TO_PPU,x
    and #255
    sta M7_CACHE_PHYSICAL
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    sta scratch
    lda pattern_hi
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp scratch
    beq @resident
    jsr mode7_cache_find
    cmp #$FFFF
    bne @retain_found
.ifdef SA1_WORKER
    lda f:M7_SPILL_ELIGIBLE
    beq @retain_missing
    lda M7_CACHE_LOGICAL
    jsr worker_spill_find
    cmp #$FFFF
    beq @retain_missing
    tax
    sep #$20
    .a8
    lda #1
    sta f:SPILL_NEW,x
    rep #$20
    .a16
    lda SPILL_LIVE_COUNT
    inc a
    sta SPILL_LIVE_COUNT
    txa
    inc a
    ldx pattern_hi
    sep #$20
    .a8
    sta f:SPILL_LOGICAL,x
    lda #0
    sta M7_LOGICAL_TO_PPU,x
    rep #$20
    .a16
    lda #1
    sta f:M7_STAGE_FORCE
    jmp @retain_next
.else
    jmp @retain_next
.endif
@retain_found:
    sta M7_CACHE_PHYSICAL
    ldx pattern_hi
    sep #$20
    .a8
    sta M7_LOGICAL_TO_PPU,x
    rep #$20
    .a16
@resident:
    ldx pattern_hi
    lda f:M7_DISPLAY_TO_PPU,x
    and #255
    cmp M7_CACHE_PHYSICAL
    beq :+
    lda #1
    sta f:M7_STAGE_FORCE
:
    lda M7_CACHE_PHYSICAL
    tax
    sep #$20
    .a8
    lda #1
    sta M7_NEW_VISIBLE,x
    rep #$20
    .a16
.ifdef SA1_WORKER
    jmp @retain_next
@retain_missing:
    lda M7_CACHE_MISSING_COUNT
    tax
    lda pattern_hi
    sep #$20
    .a8
    sta f:M7_MISSING_LIST,x
    rep #$20
    .a16
    lda M7_CACHE_MISSING_COUNT
    inc a
    sta M7_CACHE_MISSING_COUNT
.endif
@retain_next:
.ifndef SA1_WORKER
    lda msu_pcm
    bne :+
    jsr audio_pump
:
.endif
    lda M7_CACHE_ACTIVE_CURSOR
    inc a
    sta M7_CACHE_ACTIVE_CURSOR
    cmp f:M7_CACHE_ACTIVE_COUNT
    jcc @retain
.ifdef SA1_WORKER
    lda M7_CACHE_MISSING_COUNT
    jeq @retained
.endif
    lda #0
    sta M7_CACHE_ACTIVE_CURSOR
    lda #8
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
@logical:
    lda M7_CACHE_ACTIVE_CURSOR
    tax
.ifdef SA1_WORKER
    lda f:M7_MISSING_LIST,x
.else
    lda f:M7_VISIBLE_LIST,x
.endif
    and #255
    sta pattern_hi
    tax
.ifdef SA1_WORKER
    lda f:SPILL_LOGICAL,x
    and #255
    jne @logical_next
.endif
    lda M7_LOGICAL_TO_PPU,x
    and #255
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    sta scratch
    lda pattern_hi
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp scratch
    jeq @logical_next
    sta M7_CACHE_LOGICAL
    ; Reservations only consume slots during this pass. Once exhausted,
    ; skip the repeated 256-slot free-pool scan.
    lda M7_CACHE_SCAN
    jne @atomic_begin
    lda #$FFFF
    sta M7_BITMAP_CHOICE
    lda #0
    sta M7_BITMAP_BEST
    lda #256
    sta map_left
@allocate:
    lda M7_CACHE_FREE
    inc a
    and #255
    sta M7_CACHE_FREE
    tax
    lda M7_NEW_VISIBLE,x
    ora M7_OLD_VISIBLE,x
    and #255
    bne @allocate_next
.ifdef SA1_WORKER
    lda f:M7_BITMAP_ENABLED
    jeq @allocated
    txa
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp f:M7_FUTURE_TAGS,x
    bne @free_untagged
    lda f:M7_FUTURE_DEADLINES,x
    cmp f:M7_RENDER_TIME
    bcc @free_untagged
    cmp M7_BITMAP_BEST
    bcc @allocate_next
    sta M7_BITMAP_BEST
    txa
    lsr a
    sta M7_BITMAP_CHOICE
    bra @allocate_next
@free_untagged:
    txa
    lsr a
    tax
    jmp @allocated
.else
    jmp @allocated
.endif
@allocate_next:
    dec map_left
    jne @allocate
.ifdef SA1_WORKER
    lda M7_BITMAP_CHOICE
    cmp #$FFFF
    beq @no_future_victim
    tax
    jmp @allocated
@no_future_victim:
.endif
    ; A dense transition can reuse an old-only slot in the final atomic
    ; commit. Ordinary uploads never touch a displayed pattern.
    lda #1
    sta M7_CACHE_SCAN
@atomic_begin:
    lda #256
    sta map_left
@atomic:
    lda M7_CACHE_FREE
    inc a
    and #255
    sta M7_CACHE_FREE
    tax
    lda M7_NEW_VISIBLE,x
    and #255
    beq @atomic_slot
    dec map_left
    bne @atomic
    lda f:M7_CACHE_ERRORS
    inc a
    sta f:M7_CACHE_ERRORS
    jmp @abort
@atomic_slot:
    lda f:M7_CACHE_ATOMIC
    inc a
    sta f:M7_CACHE_ATOMIC
    lda #2
    jmp @reserve
.if .defined(SA1_WORKER) .and .defined(SA1_WRAM_RENDERER) .and .defined(ROM_PATTERN_COUNT)
.segment "CODE"
.endif
@allocated:
    lda #1
@reserve:
    pha
    lda #1
    sta f:M7_STAGE_FORCE
    txa
    sta M7_CACHE_PHYSICAL
    ldx pattern_hi
    sep #$20
    .a8
    sta M7_LOGICAL_TO_PPU,x
    rep #$20
    .a16
    pla
    sep #$20
    .a8
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    lda M7_CACHE_PHYSICAL
    tax
    sep #$20
    .a8
    lda #2
    sta M7_NEW_VISIBLE,x
    rep #$20
    .a16
    lda f:M7_CACHE_REMAIN
    inc a
    sta f:M7_CACHE_REMAIN
@logical_next:
.ifndef SA1_WORKER
    lda msu_pcm
    bne :+
    jsr audio_pump
:
.endif
    lda M7_CACHE_ACTIVE_CURSOR
    inc a
    sta M7_CACHE_ACTIVE_CURSOR
.ifdef SA1_WORKER
    cmp M7_CACHE_MISSING_COUNT
.else
    cmp f:M7_CACHE_ACTIVE_COUNT
.endif
    jcc @logical
@retained:

.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_NO_SPILL)
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    bne @measure_map_budget
.endif
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @ordinary_budget
@measure_map_budget:
    jsr worker_bulk_row_budget
    ; Resolve the map before budgeting tile DMA. Zoomed views need not
    ; transfer their entire bounding rectangle when most cells are blank.
.ifdef ROM_WRAP_MAP
    lda f:M7_CACHE_ATOMIC
    sta NATIVE_ROW_UNDO
.endif
    jsr mode7_cache_sparse_map
    lda #1
    sta M7_MAP_PREPARED
    lda m7_row_count
    .repeat 6
    asl a
    .endrepeat
    clc
    adc m7_row_span
    sta scratch
.ifdef SA1_STREAM_BUILD
    jsr worker_stream_spill_cost
    clc
    adc scratch
    sta scratch
.endif
 .ifdef NEO_BUILD
    lda f:EARLY_DMA_ENABLE
    beq :+
    lda #7800
    bra @blank_budget
:
 .endif
    lda #4800
@blank_budget:
    sec
    sbc scratch
    bcc @minimum_budget
.ifdef SA1_STREAM_BUILD
    sta f:STREAM_DELTA_BUDGET
.endif
    ldx #0
@budget_pattern:
    cmp #120
    bcc @budget_counted
    sec
    sbc #120
    inx
    cpx #64
    bcc @budget_pattern
@budget_counted:
    txa
    bra @dynamic_budget
@minimum_budget:
    lda #0
.ifdef SA1_STREAM_BUILD
    sta f:STREAM_DELTA_BUDGET
.endif
@dynamic_budget:
    sta M7_CACHE_BUDGET
    lda f:M7_CACHE_REMAIN
    beq @batches
    lda #1
    sta f:M7_FORCE_SKIP_HUD
    bra @batches
@ordinary_budget:
.endif
    lda f:M7_CACHE_REMAIN
    cmp f:M7_CACHE_MAX_VISIBLE
    bcc :+
    sta f:M7_CACHE_MAX_VISIBLE
:
    lda f:M7_CACHE_ATOMIC
.ifdef SA1_BUILD
    cmp f:M7_UPLOAD_LIMIT
.else
    cmp #17
.endif
    bcc @batches
    ; Borrow the HUD DMA allocation for a dense atomic transition. The
    ; published track and planets still change together in VBlank.
.ifdef SA1_BUILD
    lda f:M7_UPLOAD_LIMIT
    cmp #24
    bcs @small_budget
    cmp #16
    bcs @medium_budget
    lda #16
    bra @budget_ready
@medium_budget:
    lda #24
    bra @budget_ready
@small_budget:
    ; Forty scattered CHR runs plus map/palette DMA exceed VBlank.
    ; Reserve room for the rest of the atomic scene commit.
    lda #32

@budget_ready:
.else
    lda #20
.endif
    sta M7_CACHE_BUDGET
    ; Sixteen scattered patterns plus a full visible map fit VBlank. A
    ; larger scene is prefetched over held frames, retaining its old map.
@batches:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    ; Small updates already fit the conservative count budget. Avoid a
    ; second pass over all visible slots on the common one-frame path.
    lda f:M7_CACHE_REMAIN
    cmp M7_CACHE_BUDGET
    bcc :+
    beq :+
    jsr worker_stream_fits
    bcc :+
    lda M7_CACHE_BUDGET
    pha
    lda f:M7_CACHE_REMAIN
    sta M7_CACHE_BUDGET
    lda #1
    sta M7_CACHE_FINAL
    jsr mode7_cache_queue
    pla
    sta M7_CACHE_BUDGET
    lda #0
    sta f:M7_POOL_DIRTY
    jmp @map
:
.endif
    lda #9
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda f:M7_CACHE_REMAIN
    cmp M7_CACHE_BUDGET
    jcc @final
    jeq @final
    lda f:M7_CACHE_ATOMIC
    cmp M7_CACHE_BUDGET
    beq @atomic_fits
    jcs @transition_defer
@atomic_fits:
    lda #0
    sta M7_CACHE_FINAL
.ifdef SA1_BUILD
    ; A held frame uploads no map, HUD, palette or OAM. Use that otherwise
    ; idle VBlank bandwidth for non-displayed patterns, while retaining the
    ; smaller atomic budget for the final visible scene replacement.
    lda M7_CACHE_BUDGET
    pha
    lda #40

    sta M7_CACHE_BUDGET
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    jsr worker_stream_held_budget
.endif
.endif
    jsr mode7_cache_queue
.ifdef SA1_BUILD
    pla
    sta M7_CACHE_BUDGET
.endif
    lda pattern_queue_count
    jeq @capacity_error
.ifdef SA1_WORKER
    jsr worker_pattern_runs
    lda #2
.else
    lda #1
.endif
    sta f:M7_CACHE_READY
@wait:
.ifdef SA1_WORKER
    lda f:M7_CACHE_READY
    cmp #3
    bne :+
    lda #1
    sta f:M7_CACHE_READY
:
.endif
    lda #10
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
.ifdef SA1_WORKER
    nop
.else
    wai
.endif
    lda #3
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    jsr mode7_game_service
    lda #6
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda state
    cmp #1
    bne @abort
    lda f:M7_CACHE_READY
    bne @wait
.ifdef SA1_WORKER
    jsr worker_commit_tags
.endif
    lda f:M7_CACHE_WAIT
    inc a
    sta f:M7_CACHE_WAIT
    jmp @batches
@capacity_error:
    lda f:M7_CACHE_ERRORS
    inc a
    sta f:M7_CACHE_ERRORS
    bra @abort
@transition_defer:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD) .and .defined(ROM_WRAP_MAP)
    ; Fixed-slot admission precedes the exact map DMA budget. If map work
    ; makes its atomic texture set too large, retry with movable slots now;
    ; deferring the same physical overlap can freeze presentation indefinitely.
    lda f:STREAM_ENABLED
    beq @really_defer
    lda f:M7_IDENTITY_MODE
    beq @really_defer
    lda NATIVE_ROW_UNDO
    beq @retry_versioned
    lda m7_row_count
    beq @retry_versioned
    jsr worker_undo_rows
@retry_versioned:
    stz M7_MAP_PREPARED
    stz M7_BULK_ROWS
    stz M7_ROW_CODE_VALID
    stz m7_row_count
    stz m7_row_span
    lda #1
    sta f:M7_STAGE_FORCE
    jmp @versioned
@really_defer:
.endif
    ; Both displayed and replacement scenes fit individually. If their
    ; overlap needs more atomic uploads than VBlank permits, retain the
    ; verified old scene and try the next song-clock frame.
    lda f:M7_TRANSITION_DEFERRALS
    inc a
    sta f:M7_TRANSITION_DEFERRALS
@abort:
.if .defined(SA1_WORKER) .and .defined(ROM_WRAP_MAP)
    lda NATIVE_ROW_UNDO
    beq :+
    lda m7_row_count
    beq :+
    jsr worker_undo_rows
    lda #0
    sta f:M7_CACHE_LOCAL_H
    lda #1
    sta f:M7_CACHE_DIRTY
:
.endif
    lda #1
    sta f:M7_CACHE_ABORT
    stz pattern_queue_count
    stz m7_row_count
    stz m7_row_span
    rts
@final:
    lda #1
    sta M7_CACHE_FINAL
    jsr mode7_cache_queue
    lda #0
    sta f:M7_POOL_DIRTY
@map:
.ifdef SA1_WORKER
    jsr worker_spill_map_begin
.endif
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_NO_SPILL)
    lda M7_MAP_PREPARED
    bne :+
.endif
    jsr mode7_cache_sparse_map
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_NO_SPILL)
:
.endif
.ifdef SA1_WORKER
    jsr worker_spill_cells
.endif
.ifdef SA1_BUILD
    lda f:M7_VIEW_X
.else
    lda cam_x
    jsr mode7_floor8
.endif
    sta f:M7_CACHE_LOCAL_X
.ifdef SA1_BUILD
    lda f:M7_VIEW_Y
.else
    lda cam_y
    clc
    adc #32
    jsr mode7_floor8
.endif
    sta f:M7_CACHE_LOCAL_Y
    lda view_count
    sta f:M7_CACHE_LOCAL_W
.ifdef SA1_BUILD
    lda f:M7_VIEW_H
.else
    lda cam_y
    and #7
    beq :+
    lda #1
:
    clc
    adc #16
.endif
    sta f:M7_CACHE_LOCAL_H
    lda #0
    sta f:M7_CACHE_DIRTY
    jsr mode7_cache_future
    rts

mode7_cache_queue:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda f:STREAM_ENABLED
    beq :+
    lda f:M7_IDENTITY_MODE
    beq :+
    jmp mode7_cache_fixed_queue
:
.endif
    stz pattern_queue_count
    stz m7_upload_slots
    lda f:M7_CACHE_REMAIN
    bne :+
    rts
:
    ldy #0
@slot:
    tyx
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
    lda M7_PATTERN_SELECTED,x
    and #255
    beq @next
    cmp #2
    bne @add
    lda M7_CACHE_FINAL
    beq @next
@add:
    sep #$20
    .a8
    lda #0
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    lda M7_LOGICAL_TO_PPU,x
    and #255
    sta M7_CACHE_PHYSICAL
    phy
    jsr mode7_queue_slot
    ply
    lda f:M7_CACHE_REMAIN
    dec a
    sta f:M7_CACHE_REMAIN
    beq @done
    lda m7_upload_slots
    cmp M7_CACHE_BUDGET
    bcs @done
@next:
    iny
    tya
    cmp f:M7_CACHE_ACTIVE_COUNT
    jcc @slot
@done:
    rts

; Append one immutable RAM pattern and its physical destination.
mode7_queue_slot:
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_PAGED)
    lda #0
    sta ROM_SOURCE_PAGE
.endif
 .if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_ADDR)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @wram_source
    lda pattern_hi
    asl a
    tax
    lda f:PATTERN_CURRENT,x
.ifdef ROM_PATTERN_COUNT
    cmp #ROM_PATTERN_COUNT
    bcs @wram_source
.endif
    jsr worker_rom_source
    lda transfer_ptr
    sta transfer_dest
    lda transfer_ptr+2
    sec
    sbc #$7E
    sta transfer_wbank
    bra @source_ready
@wram_source:
.endif
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda f:STREAM_ENABLED
    beq @normal_pattern_source
    lda f:NATIVE_READY
    beq @normal_pattern_source
    lda pattern_hi
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(STREAM_CHR)
    sta transfer_dest
    lda #(.bankbyte(STREAM_CHR)-$7E)&$FFFF
    sta transfer_wbank
    bra @source_ready
@normal_pattern_source:
.endif
    lda pattern_hi
    jsr mode7_pattern_destination
@source_ready:
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
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_PAGED)
    lda ROM_SOURCE_PAGE
    sta f:PATTERN_QUEUE+10,x
.endif
    lda M7_CACHE_PHYSICAL
    .repeat 6
    asl a
    .endrepeat
    sta f:PATTERN_QUEUE+4,x
    lda #64
    sta f:PATTERN_QUEUE+6,x
    phx
    lda pattern_hi
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    plx
    sta f:PATTERN_QUEUE+8,x
    inc pattern_queue_count
    inc m7_upload_slots
    lda m7_upload_slots
    cmp pattern_peak_queued
    bcc :+
    sta pattern_peak_queued
:
    rts

; Prefer the compiler's own slot assignments. Most scenes can be committed
; directly after inexpensive, unused-slot prefetch; dense transitions retain
; the versioned allocator as a fallback.
mode7_cache_identity:
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    jsr mode7_cache_hash
:
.endif
    lda #0
    sta f:M7_DIRECT_COUNT
    ldy #0
@check:
    tyx
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp f:M7_PATTERN_VRAM,x
    beq @next
    lda f:M7_DIRECT_COUNT
.ifdef SA1_BUILD
    cmp f:M7_UPLOAD_LIMIT
.else
    cmp #20
.endif
    bcc :+
    clc
    rts
:
    tax
    inc a
    sta f:M7_DIRECT_COUNT
    lda pattern_hi
    sep #$20
    .a8
    sta f:M7_DIRECT_LIST,x
    rep #$20
    .a16
@next:
    iny
    tya
    cmp f:M7_CACHE_ACTIVE_COUNT
    bcc @check
    lda f:M7_IDENTITY_MODE
    bne @identity_ready
    lda #1
    sta f:M7_IDENTITY_MODE
    sta f:M7_STAGE_FORCE
    ldx #0
    sep #$20
    .a8
@identity:
    txa
    sta M7_LOGICAL_TO_PPU,x
    inx
    cpx #256
    bcc @identity
    rep #$20
    .a16
@identity_ready:
    lda f:M7_GLOBAL_REFS_ACTIVE
    cmp #2
    bne @copy_visible
    ; Build visibility on the SA-1 from the compact list, rather than having
    ; the SNES construct and then copy a 256-byte flag array every update.
    lda #0
    ldx #0
@clear_visible:
    sta M7_NEW_VISIBLE,x
    sta f:M7_VISIBLE_PATTERNS,x
    inx
    inx
    cpx #256
    bcc @clear_visible
    ldy #0
@visible:
    tyx
    lda f:M7_VISIBLE_LIST,x
    and #255
    tax
    sep #$20
    .a8
    lda #1
    sta M7_NEW_VISIBLE,x
    sta f:M7_VISIBLE_PATTERNS,x
    rep #$20
    .a16
    iny
    tya
    cmp f:M7_CACHE_ACTIVE_COUNT
    bcc @visible
    bra @visibility_ready
@copy_visible:
    phb
    lda #255
    ldx #.loword(M7_VISIBLE_PATTERNS)
    ldy #.loword(M7_NEW_VISIBLE)
    mvn #.bankbyte(M7_VISIBLE_PATTERNS),#.bankbyte(M7_NEW_VISIBLE)
    plb
@visibility_ready:
    stz pattern_queue_count
    stz m7_upload_slots
    ldy #0
@missing:
    tya
    cmp f:M7_DIRECT_COUNT
    bcs @ready
    tyx
    lda f:M7_DIRECT_LIST,x
    and #255
    sta pattern_hi
    sta M7_CACHE_PHYSICAL
    jsr mode7_queue_slot
    iny
    bra @missing
@ready:
    lda f:M7_DIRECT_COUNT
    sta f:M7_CACHE_ATOMIC
    lda #0
    sta f:M7_CACHE_REMAIN
    sec
    rts

.if .defined(SA1_WORKER) .and .defined(ROM_DIRECT_UNTIL)
; Compiler slots are a direct PPU map while their authored reuse schedule
; leaves the previous scene intact. Keep the general allocator for later
; sections with simultaneous reuse of many displayed slots.
mode7_cache_fixed_prepare:
.ifdef SA1_WRAM_RENDERER
    lda M7_CACHE_CODE_VALID
    cmp #3
    beq @loaded
    phb
    lda #__HOTFIXED_SIZE__-1
    ldx #__HOTFIXED_LOAD__
    ldy #__HOTFIXED_RUN__
    mvn #$01,#$00
    plb
    lda #3
    sta M7_CACHE_CODE_VALID
@loaded:
    jmp mode7_cache_fixed_kernel
.segment "HOTFIXED"
mode7_cache_fixed_kernel:
.endif
    lda f:M7_IDENTITY_MODE
    bne :+
    lda #1
    sta f:M7_STAGE_FORCE
    ldx #0
    sep #$20
    .a8
@identity:
    txa
    sta M7_LOGICAL_TO_PPU,x
    inx
    cpx #256
    bcc @identity
    rep #$20
    .a16
:
    lda #1
    sta f:M7_IDENTITY_MODE
    lda #0
    sta f:M7_CACHE_REMAIN
    sta f:M7_CACHE_ATOMIC
    sta f:M7_DIRECT_COUNT
    ldx #0
@clear:
    .repeat 8, word
    sta M7_NEW_VISIBLE+word*2,x
    sta M7_PATTERN_SELECTED+word*2,x
    sta f:M7_VISIBLE_PATTERNS+word*2,x
    .endrepeat
    txa
    clc
    adc #16
    tax
    lda #0
    cpx #256
    bcc @clear
    ldy #0
@active:
    tyx
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
    sep #$20
    .a8
    lda #1
    sta M7_NEW_VISIBLE,x
    sta f:M7_VISIBLE_PATTERNS,x
    rep #$20
    .a16
    txa
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    cmp f:M7_PATTERN_VRAM,x
    beq @next
    lda f:M7_DIRECT_COUNT
    tax
    lda pattern_hi
    sep #$20
    .a8
    sta f:M7_DIRECT_LIST,x
    rep #$20
    .a16
    txa
    inc a
    sta f:M7_DIRECT_COUNT
    lda f:M7_CACHE_REMAIN
    inc a
    sta f:M7_CACHE_REMAIN
    ldx pattern_hi
    lda M7_OLD_VISIBLE,x
    and #255
    beq @free
    lda f:M7_CACHE_ATOMIC
    inc a
    sta f:M7_CACHE_ATOMIC
    lda #2
    bra @mark
@free:
    lda #1
@mark:
    sep #$20
    .a8
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
@next:
    iny
    tya
    cmp f:M7_CACHE_ACTIVE_COUNT
    bcc @active
    rts
.ifdef SA1_WRAM_RENDERER
.segment "CODE"
.endif
.endif

.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
; Fixed preparation already found the missing slots. Queue that short list
; rather than searching the complete visible set again for every batch.
mode7_cache_fixed_queue:
    stz pattern_queue_count
    stz m7_upload_slots
    lda f:M7_CACHE_REMAIN
    beq @done
    ldy #0
@slot:
    tyx
    lda f:M7_DIRECT_LIST,x
    and #255
    sta pattern_hi
    sta M7_CACHE_PHYSICAL
    tax
    lda M7_PATTERN_SELECTED,x
    and #255
    beq @next
    cmp #2
    bne @add
    lda M7_CACHE_FINAL
    beq @next
@add:
    sep #$20
    .a8
    lda #0
    sta M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    phy
    jsr mode7_queue_slot
    ply
    lda f:M7_CACHE_REMAIN
    dec a
    sta f:M7_CACHE_REMAIN
    beq @done
    lda m7_upload_slots
    cmp M7_CACHE_BUDGET
    bcs @done
@next:
    iny
    tya
    cmp f:M7_DIRECT_COUNT
    bcc @slot
@done:
    rts
.endif

; Use spare transfer capacity to fill future compiler slots while their
; physical cells are absent from both displayed and staged scenes.
mode7_cache_future:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda f:STREAM_DELTA_FLAGS
    bpl :+
    lda f:STREAM_ENABLED
    beq :+
    lda f:STREAM_PAGE
    bne :+
    lda f:M7_IDENTITY_MODE
    beq :+
    lda f:NATIVE_READY
    beq :+
    jmp worker_delta_future
:
.endif

.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    lda f:M7_BITMAP_ENABLED
    bne :+
.ifdef ROM_DIRECT_UNTIL
    lda f:M7_RENDER_TIME
    cmp #ROM_DIRECT_UNTIL
    bcs @no_fixed_future
    lda f:M7_IDENTITY_MODE
    beq @no_fixed_future
    jmp mode7_cache_fixed_future
@no_fixed_future:
.endif
    rts
:
.endif
.ifdef SA1_WORKER
    lda f:M7_BITMAP_ENABLED
    beq :+
    jmp worker_prefetch_bitmaps
:
.endif
    lda f:M7_PREFETCH_CURSOR
    tax
    ldy #64
@slot:
    lda m7_upload_slots
.ifdef SA1_BUILD
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    pha
    lda f:STREAM_ENABLED
    beq @ordinary_future_limit
    pla
    cmp M7_CACHE_BUDGET
    bra @future_limit_checked
@ordinary_future_limit:
    pla
.endif
    cmp f:M7_UPLOAD_LIMIT
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
@future_limit_checked:
.endif
.else
    cmp #16
.endif
    jcs @done
    txa
    inc a
    and #255
    tax
    lda M7_NEW_VISIBLE,x
    ora M7_OLD_VISIBLE,x
    and #255
    bne @next
    phx
    txa
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    beq @restore
    cmp f:M7_PATTERN_VRAM,x
    beq @restore
    pla
    pha
    sta pattern_hi
    sta M7_CACHE_PHYSICAL
    phy
    jsr mode7_queue_slot
    ply
@restore:
    plx
@next:
    dey
    jne @slot
@done:
    txa
    sta f:M7_PREFETCH_CURSOR
    rts

.if .defined(SA1_WORKER) .and .defined(ROM_DIRECT_UNTIL)
mode7_cache_fixed_future:
    ; Scan with X in slot order. New scene visibility is sufficient because
    ; these speculative writes publish with the new map in the same NMI.
    ldx #1
@slot:
    lda m7_upload_slots
    cmp M7_CACHE_BUDGET
    bcs @done
    lda M7_NEW_VISIBLE,x
    and #255
    bne @next
    txa
    sta pattern_hi
    asl a
    tay
    phx
    tyx
    lda f:PATTERN_CURRENT,x
    beq @restore
    cmp f:M7_PATTERN_VRAM,x
    beq @restore
    lda pattern_hi
    sta M7_CACHE_PHYSICAL
    jsr mode7_queue_slot
@restore:
    plx
@next:
    inx
    cpx #256
    bcc @slot
@done:
    rts
.endif

; Reuse a raw bitmap already resident under another logical lease. Without
; this lookup repeated shapes were uploaded again into new physical slots,
; wasting VBlank time and overflowing old/new scene residency at speed.
mode7_cache_hash:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda f:STREAM_ENABLED
    beq :+
    jmp worker_rom_hash
:
.endif
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    jmp worker_rom_hash
:
.endif
    lda f:M7_HASH_DIRTY
    bne :+
    rts
:
    lda #0
    sta f:M7_HASH_DIRTY
    lda #$FFFF
    ldx #0
@clear:
    sta M7_RESIDENT_HASH,x
    inx
    inx
    cpx #512
    bcc @clear
    ldy #0
@slot:
    tya
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    bne @add
    cpy #0
    bne @next
@add:
    sta scratch
    xba
    eor scratch
    and #255
    asl a
    tax
    lda M7_RESIDENT_HASH,x
    sta scratch2
    tya
    sta M7_RESIDENT_HASH,x
    asl a
    tax
    lda scratch2
    sta f:M7_RESIDENT_NEXT,x
@next:
    iny
    cpy #256
    bcc @slot
    rts

mode7_cache_find:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    pha
    lda f:STREAM_ENABLED
    beq :+
    pla
    jmp worker_rom_find
:
    pla
.endif
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_COUNT)
    pha
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    pla
    jmp worker_rom_find
:
    pla
.endif
    sta M7_CACHE_LOGICAL
    sta scratch
    xba
    eor scratch
    and #255
    asl a
    tax
    lda M7_RESIDENT_HASH,x
@slot:
    cmp #$FFFF
    beq @done
    sta M7_CACHE_PHYSICAL
    tax
    lda M7_NEW_VISIBLE,x
    and #255
    cmp #2
    beq @next
    txa
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp M7_CACHE_LOGICAL
    beq @found
@next:
    lda M7_CACHE_PHYSICAL
    asl a
    tax
    lda f:M7_RESIDENT_NEXT,x
    bra @slot
@found:
    lda M7_CACHE_PHYSICAL
@done:
    rts

; Scroll inside a coarse 64x32-cell origin. Unchanged cells retain their
; physical PPU mapping; only dirty row spans enter the immutable DMA buffer.
mode7_cache_sparse_map:
    lda #11
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    stz m7_row_count
    stz m7_row_span
.ifdef SA1_BUILD
    lda f:M7_VIEW_X
.else
    lda cam_x
    jsr mode7_floor8
.endif
    pha
.ifdef SA1_BUILD
.ifdef ROM_WRAP_MAP
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    lda f:M7_VIEW_W
    lsr a
    clc
    adc f:M7_VIEW_X
    and #$FF80
    sta f:M7_STAGE_BASE_X
    jmp @keep_origin_x
:
    lda 1,s
.endif
    sec
    sbc f:M7_STAGE_BASE_X
    bmi @move_origin_x
    clc
    adc f:M7_VIEW_W
    cmp #129
    bcc @keep_origin_x
@move_origin_x:
    lda f:M7_VIEW_X
.else
    and #$FFC0
.endif
    cmp f:M7_STAGE_BASE_X
    beq :+
    sta f:M7_STAGE_BASE_X
    lda #1
    sta f:M7_STAGE_FORCE
:
.ifdef SA1_BUILD
@keep_origin_x:
.endif
    pla
    and #127
    sta view_x
.ifdef SA1_BUILD
    lda f:M7_VIEW_W
.else
    lda cam_x
    and #7
    beq :+
    lda #1
:
    clc
    adc #32
.endif
    sta view_count
    sta f:M7_EXPOSE_FIRST
    lda #0
    sta f:M7_EXPOSE_END
.ifdef SA1_BUILD
    lda f:M7_VIEW_X
.else
    lda cam_x
    jsr mode7_floor8
.endif
    sta scratch
    lda f:M7_CACHE_LOCAL_X
    sec
    sbc scratch
    sta scratch2
    beq @right_edge
    bmi @right_edge
    cmp view_count
    bcc :+
    lda view_count
:
    sta f:M7_EXPOSE_END
    lda #0
    sta f:M7_EXPOSE_FIRST
@right_edge:
    lda scratch2
    clc
    adc f:M7_CACHE_LOCAL_W
    bpl :+
    lda #0
:
    cmp view_count
    bcs @columns_ready
    cmp f:M7_EXPOSE_FIRST
    bcs :+
    sta f:M7_EXPOSE_FIRST
:
    lda view_count
    sta f:M7_EXPOSE_END
@columns_ready:
.ifdef SA1_BUILD
    lda f:M7_VIEW_Y
.else
    lda cam_y
    clc
    adc #32
    jsr mode7_floor8
.endif
    sta view_y
.ifdef SA1_BUILD
.ifdef ROM_WRAP_MAP
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    lda f:M7_VIEW_H
    lsr a
    clc
    adc view_y
    and #$FF80
    sta f:M7_STAGE_BASE_Y
    jmp @keep_origin_y
:
    lda view_y
.endif
    sec
    sbc f:M7_STAGE_BASE_Y
    bmi @move_origin_y
    clc
    adc f:M7_VIEW_H
    cmp #129
    bcc @keep_origin_y
@move_origin_y:
    lda view_y
.else
    and #$FFE0
.endif
    cmp f:M7_STAGE_BASE_Y
    beq :+
    sta f:M7_STAGE_BASE_Y
    lda #1
    sta f:M7_STAGE_FORCE
:
.ifdef SA1_BUILD
@keep_origin_y:
.endif
.ifdef SA1_BUILD
    lda f:M7_VIEW_H
.else
    lda cam_y
    and #7
    beq :+
    lda #1
:
    clc
    adc #16
.endif
    sta view_rows
@row:
    lda view_y
    and #127
    tax
    lda #0
    sta f:M7_STAGE_FIRST
    lda view_count
    sta transfer_len
    lda f:M7_STAGE_FORCE
    jne @copy
    lda view_y
    sec
    sbc f:M7_CACHE_LOCAL_Y
    cmp f:M7_CACHE_LOCAL_H
    jcs @copy
    lda f:M7_DIRTY_BITS,x
    and #255
    beq @exposed_only
    ; Wrapped logical rows use a full contiguous PPU span.
    lda view_x
    clc
    adc view_count
    cmp #129
    jcs @copy
    txa
    asl a
    tax
    lda f:M7_DIRTY_BOUNDS,x
    and #255
    sec
    sbc view_x
    bpl :+
    lda #0
:
    cmp view_count
    bcs @exposed_only
    sta f:M7_STAGE_FIRST
    lda f:M7_DIRTY_BOUNDS+1,x
    and #255
    sec
    sbc view_x
    bpl :+
    bra @exposed_only
:
    inc a
    cmp view_count
    bcc :+
    lda view_count
:
    cmp f:M7_EXPOSE_END
    bcs :+
    lda f:M7_EXPOSE_END
:
    sta transfer_len
    lda f:M7_EXPOSE_FIRST
    cmp f:M7_STAGE_FIRST
    bcs :+
    sta f:M7_STAGE_FIRST
:
    lda transfer_len
    bra @length
@exposed_only:
    lda f:M7_EXPOSE_FIRST
    sta f:M7_STAGE_FIRST
    lda f:M7_EXPOSE_END
@length:
    cmp f:M7_STAGE_FIRST
    jcc @next
    jeq @next
    sec
    sbc f:M7_STAGE_FIRST
    sta transfer_len
@copy:
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda M7_BULK_ROWS
    cmp #2
    bne @copy_measured
    lda transfer_len
    clc
    adc #64
    clc
    adc m7_row_span
    sta m7_row_span
    jmp @next
@copy_measured:
.endif
    lda view_y
    and #127
    .repeat 7
    asl a
    .endrepeat
    clc
    adc #.loword(M7_MAP)
    sta map_ptr
    lda view_y
    sec
    sbc f:M7_STAGE_BASE_Y
    .repeat 7
    asl a
    .endrepeat
    sta map_dest
    lda view_x
.ifdef SA1_BUILD
    sec
    sbc f:M7_STAGE_BASE_X
    and #127
.else
    and #63
.endif
    clc
    adc f:M7_STAGE_FIRST
.ifdef ROM_WRAP_MAP
    pha
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    beq @wrap_column
    pla
    bra @column_ready
@wrap_column:
    pla
    and #127
@column_ready:
.endif
    clc
    adc map_dest
    sta map_dest
.ifdef ROM_WRAP_MAP
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    lda map_dest
    and #M7_STAGE_MASK
    sta map_dest
:
    lda map_dest
.endif
    and #M7_STAGE_MASK
    clc
    adc #.loword(M7_STAGE_MAP)
    sta map_base_ptr
    lda view_x
    clc
    adc f:M7_STAGE_FIRST
    and #127
    tay
    sta map_left
    lda map_base_ptr
    sec
    sbc map_left
    sta map_base_ptr
    sep #$20
    .a8
    lda #.bankbyte(M7_MAP)
    sta map_ptr+2
    lda #.bankbyte(M7_STAGE_MAP)
    sta map_base_ptr+2
    rep #$20
    .a16
.if .defined(SA1_WORKER) .and .defined(ROM_WRAP_MAP)
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @ordinary_copy
    tya
    clc
    adc transfer_len
    cmp #129
    bcc @wrapped_one
    ; The hardware texture wraps columns within a row, not into the next
    ; row. Split both the staged bytes and their VBlank DMA descriptors.
    sec
    sbc #128
    sta NATIVE_ROW_TAIL
    lda map_dest
    and #$3F80
    sta NATIVE_ROW_BASE
    lda transfer_len
    sec
    sbc NATIVE_ROW_TAIL
    sta transfer_len
    jsr worker_translate_row
    bcc :+
    jsr mode7_cache_stage_span
:
    lda NATIVE_ROW_BASE
    sta map_dest
    lda NATIVE_ROW_TAIL
    sta transfer_len
    ldy #0
@wrapped_one:
    jsr worker_translate_row
    jcc @next
    jmp @copied
@ordinary_copy:
    ; Short scalar/identity rows also need rollback, but copying their
    ; few old bytes directly is cheaper than two IRAM DMA round trips.
    lda NATIVE_ROW_UNDO
    beq :+
    lda transfer_len
    cmp #16
    bcs :+
    jsr worker_save_short_row
:
.endif
.if .defined(SA1_WORKER) .and .defined(ROM_DIRECT_UNTIL)
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    beq :+
    lda M7_BULK_ROWS
    bne @skip_direct_row
    bra @direct_row_allowed
:
.endif
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @skip_direct_row
@direct_row_allowed:
    lda f:M7_IDENTITY_MODE
    beq @skip_direct_row
    lda transfer_len
    cmp #16
    bcc @skip_direct_row
    jsr worker_translate_row
    jcc @next
    jmp @copied
@skip_direct_row:
.endif
    lda f:M7_IDENTITY_MODE
    beq @translate
.ifdef SA1_WORKER
    ; Wide zoomed views contain mostly empty cells. Copying every row on
    ; an origin change can overrun VBlank even with only one new pattern.
    ; Compare the staged physical map and upload only changed row spans.
.ifdef SA1_STREAM_BUILD
    lda M7_BULK_ROWS
    bne @bulk_identity_copy
.endif
    lda f:M7_VIEW_H
    cmp #32
    bcs @translate
.ifdef SA1_STREAM_BUILD
@bulk_identity_copy:
.endif
.endif
    tya
    sta map_left
    lda #128
    sec
    sbc map_left
    cmp transfer_len
    bcc :+
    lda transfer_len
:
    sta m7_run_index
    tya
    clc
    adc map_ptr
    tax
    lda map_dest
    and #M7_STAGE_MASK
    clc
    adc #.loword(M7_STAGE_MAP)
    tay
    lda m7_run_index
    dec a
    phb
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_STAGE_MAP)
    plb
    lda transfer_len
    sec
    sbc m7_run_index
    jeq @copied
    dec a
    ldx map_ptr
    phb
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_STAGE_MAP)
    plb
    jmp @copied
@translate:
.if .defined(SA1_WORKER) .and .defined(ROM_PATTERN_NO_SPILL)
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    bne @accelerated_row_allowed
.endif
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @skip_accel_row
@accelerated_row_allowed:
    lda transfer_len
    cmp #16
    bcc @skip_accel_row
    jsr worker_translate_row
    jcc @next
    jmp @copied
@skip_accel_row:
.endif
    lda transfer_len
    sta map_left
    stz m7_run_index
    stz map_scan_x
.ifdef SA1_WORKER
    lda SPILL_MAP_ACTIVE
    beq @plain_translate
    lda view_y
    asl a
    asl a
    asl a
    sec
    sbc f:M7_RASTER_Y
    cmp #25
    bcc @plain_translate
    cmp #177
    bcs @plain_translate
    sta SPILL_Y
    lda #0
    sep #$20
    .a8
@spill_pixel:
    lda [map_ptr],y
    tax
    lda f:SPILL_LOGICAL,x
    beq @spill_blank
    jsr worker_spill_map_pixel
@spill_blank:
    lda M7_LOGICAL_TO_PPU,x
    cmp [map_base_ptr],y
    beq @spill_same
    sta [map_base_ptr],y
    rep #$20
    .a16
    lda m7_run_index
    bne :+
    lda map_left
    sta m7_run_index
:
    lda map_left
    sta map_scan_x
    lda #0
    sep #$20
    .a8
@spill_same:
    iny
    cpy #128
    bcc :+
    ldy #0
    rep #$20
    .a16
    lda map_base_ptr
    clc
    adc #128
    sta map_base_ptr
    lda #0
    sep #$20
    .a8
:
    dec map_left
    lda map_left
    bne @spill_pixel
    rep #$20
    .a16
    bra @translated
@plain_translate:
.endif
    lda #0
    sep #$20
    .a8
@pixel:
    lda [map_ptr],y
    tax
    lda M7_LOGICAL_TO_PPU,x
    cmp [map_base_ptr],y
    beq @same_pixel
    sta [map_base_ptr],y
    rep #$20
    .a16
    lda m7_run_index
    bne :+
    lda map_left
    sta m7_run_index
:
    lda map_left
    sta map_scan_x
    lda #0
    sep #$20
    .a8
@same_pixel:
    iny
    cpy #128
    bcc :+
    ldy #0
    rep #$20
    .a16
    lda map_base_ptr
    clc
    adc #128
    sta map_base_ptr
    lda #0
    sep #$20
    .a8
:
    dec map_left
    lda map_left
    bne @pixel
    rep #$20
    .a16
@translated:
    lda m7_run_index
    jeq @next
    lda transfer_len
    sec
    sbc m7_run_index
    clc
    adc map_dest
    sta map_dest
    lda m7_run_index
    sec
    sbc map_scan_x
    inc a
    sta transfer_len
@copied:
    jsr mode7_cache_stage_span
@next:
.ifndef SA1_WORKER
    jsr audio_pump
.endif
    inc view_y
    dec view_rows
    jne @row
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
    lda M7_BULK_ROWS
    cmp #2
    beq @measured_rows_done
.endif
    lda #0
    ldx #0
@clean:
    sta f:M7_DIRTY_BITS,x
    inx
    inx
    cpx #128
    bcc @clean
.if .defined(SA1_WORKER) .and .defined(SA1_STREAM_BUILD)
@measured_rows_done:
.endif
    rts

mode7_cache_stage_span:
    lda m7_row_count
    asl a
    asl a
    tax
    lda map_dest
    sta f:M7_DMA_LIST,x
    lda transfer_len
    sta f:M7_DMA_LIST+2,x
    clc
    adc m7_row_span
    sta m7_row_span
    inc m7_row_count
    rts
