; Logical chart slots and physical PPU slots have independent generations.
; Keep the old viewport resident until its replacement is complete.
mode7_cache_reset:
    lda #0
    sta f:M7_CACHE_READY
    sta f:M7_CACHE_FREE
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
    sta f:M7_LOGICAL_TO_PPU,x
    sta f:M7_DISPLAY_TO_PPU,x
    lda #0
    sta f:M7_NEW_VISIBLE,x
    sta f:M7_OLD_VISIBLE,x
    sta f:M7_PATTERN_SELECTED,x
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
    lda f:M7_MASKS_CHANGED
    beq @done
    lda f:M7_CACHE_UNCHANGED
    bne @done
    lda display_state
    cmp #1
    bne @done
.ifdef SA1_BUILD
.ifndef SA1_WORKER
    jmp sa1_cache_commit
.endif
.endif
    phb
    lda #255
    ldx #.loword(M7_NEW_VISIBLE)
    ldy #.loword(M7_OLD_VISIBLE)
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_MAP)
    lda f:M7_IDENTITY_MODE
    beq @mapping
    lda f:M7_STAGE_FORCE
    beq @mapped
@mapping:
    lda #255
    ldx #.loword(M7_LOGICAL_TO_PPU)
    ldy #.loword(M7_DISPLAY_TO_PPU)
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_MAP)
@mapped:
    plb
@done:
    rts

mode7_cache_prepare:
.ifdef SA1_BUILD
.ifndef SA1_WORKER
    jmp sa1_cache_prepare
.endif
.endif
    lda #0
    sta f:M7_CACHE_UNCHANGED
    sta f:M7_MASKS_CHANGED
    sta f:M7_STAGE_FORCE
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
    jsr mode7_cache_identity
    bcc @versioned
    lda #0
    sta f:M7_POOL_DIRTY
    jmp @map
@versioned:
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
    sta f:M7_CACHE_BUDGET
    lda #7
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda #0
    sta f:M7_CACHE_REMAIN
    sta f:M7_CACHE_ATOMIC
    sta f:M7_CACHE_SCAN
    ldx #0
@clear:
    sta f:M7_NEW_VISIBLE,x
    sta f:M7_PATTERN_SELECTED,x
    inx
    inx
    cpx #256
    bcc @clear
    ; Protect every resident pattern needed by the new scene before an
    ; allocator may evict anything, regardless of logical scan order.
    lda #0
    sta f:M7_CACHE_ACTIVE_CURSOR
@retain:
    lda f:M7_CACHE_ACTIVE_CURSOR
    tax
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
    lda f:M7_LOGICAL_TO_PPU,x
    and #255
    sta f:M7_CACHE_PHYSICAL
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
    beq @retain_next
    sta f:M7_CACHE_PHYSICAL
    ldx pattern_hi
    sep #$20
    .a8
    sta f:M7_LOGICAL_TO_PPU,x
    rep #$20
    .a16
@resident:
    ldx pattern_hi
    lda f:M7_DISPLAY_TO_PPU,x
    and #255
    cmp f:M7_CACHE_PHYSICAL
    beq :+
    lda #1
    sta f:M7_STAGE_FORCE
:
    lda f:M7_CACHE_PHYSICAL
    tax
    sep #$20
    .a8
    lda #1
    sta f:M7_NEW_VISIBLE,x
    rep #$20
    .a16
@retain_next:
    lda msu_pcm
    bne :+
    jsr audio_pump
:
    lda f:M7_CACHE_ACTIVE_CURSOR
    inc a
    sta f:M7_CACHE_ACTIVE_CURSOR
    cmp f:M7_CACHE_ACTIVE_COUNT
    jcc @retain
    lda #0
    sta f:M7_CACHE_ACTIVE_CURSOR
@logical:
    lda #8
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda f:M7_CACHE_ACTIVE_CURSOR
    tax
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
    lda f:M7_LOGICAL_TO_PPU,x
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
    sta f:M7_CACHE_LOGICAL
    lda #256
    sta map_left
@allocate:
    lda f:M7_CACHE_FREE
    inc a
    and #255
    sta f:M7_CACHE_FREE
    tax
    lda f:M7_NEW_VISIBLE,x
    ora f:M7_OLD_VISIBLE,x
    and #255
    beq @allocated
    dec map_left
    bne @allocate
    ; A dense transition can reuse an old-only slot in the final atomic
    ; commit. Ordinary uploads never touch a displayed pattern.
    lda #256
    sta map_left
@atomic:
    lda f:M7_CACHE_FREE
    inc a
    and #255
    sta f:M7_CACHE_FREE
    tax
    lda f:M7_NEW_VISIBLE,x
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
    bra @reserve
@allocated:
    lda #1
@reserve:
    pha
    lda #1
    sta f:M7_STAGE_FORCE
    txa
    sta f:M7_CACHE_PHYSICAL
    ldx pattern_hi
    sep #$20
    .a8
    sta f:M7_LOGICAL_TO_PPU,x
    rep #$20
    .a16
    pla
    sep #$20
    .a8
    sta f:M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    lda f:M7_CACHE_PHYSICAL
    tax
    sep #$20
    .a8
    lda #2
    sta f:M7_NEW_VISIBLE,x
    rep #$20
    .a16
    lda f:M7_CACHE_REMAIN
    inc a
    sta f:M7_CACHE_REMAIN
@logical_next:
    lda msu_pcm
    bne :+
    jsr audio_pump
:
    lda f:M7_CACHE_ACTIVE_CURSOR
    inc a
    sta f:M7_CACHE_ACTIVE_CURSOR
    cmp f:M7_CACHE_ACTIVE_COUNT
    jcc @logical
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
    bcc :+
    ; Borrow the HUD DMA allocation for a dense atomic transition. The
    ; published track and planets still change together in VBlank.
.ifdef SA1_BUILD
    lda f:M7_UPLOAD_LIMIT
.else
    lda #20
.endif
    sta f:M7_CACHE_BUDGET
:
    ; Sixteen scattered patterns plus a full visible map fit VBlank. A
    ; larger scene is prefetched over held frames, retaining its old map.
@batches:
    lda #9
    sta profile_phase
.ifdef SA1_WORKER
    sta f:$400030
.endif
    lda f:M7_CACHE_REMAIN
    cmp f:M7_CACHE_BUDGET
    jcc @final
    jeq @final
    lda f:M7_CACHE_ATOMIC
    cmp f:M7_CACHE_BUDGET
    beq :+
    bcs @transition_defer
:
    lda #0
    sta f:M7_CACHE_FINAL
.ifdef SA1_BUILD
    ; A held frame uploads no map, HUD, palette or OAM. Use that otherwise
    ; idle VBlank bandwidth for non-displayed patterns, while retaining the
    ; smaller atomic budget for the final visible scene replacement.
    lda f:M7_CACHE_BUDGET
    pha
    lda #32
    sta f:M7_CACHE_BUDGET
.endif
    jsr mode7_cache_queue
.ifdef SA1_BUILD
    pla
    sta f:M7_CACHE_BUDGET
.endif
    lda pattern_queue_count
    beq @capacity_error
    lda #1
    sta f:M7_CACHE_READY
@wait:
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
    ; Both displayed and replacement scenes fit individually. If their
    ; overlap needs more atomic uploads than VBlank permits, retain the
    ; verified old scene and try the next song-clock frame.
    lda f:M7_TRANSITION_DEFERRALS
    inc a
    sta f:M7_TRANSITION_DEFERRALS
@abort:
    lda #1
    sta f:M7_CACHE_ABORT
    stz pattern_queue_count
    stz m7_row_count
    stz m7_row_span
    rts
@final:
    lda #1
    sta f:M7_CACHE_FINAL
    jsr mode7_cache_queue
    lda #0
    sta f:M7_POOL_DIRTY
@map:
    jsr mode7_cache_sparse_map
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
    stz pattern_queue_count
    stz m7_upload_slots
    lda f:M7_CACHE_REMAIN
    bne :+
    rts
:
    lda #0
    sta f:M7_CACHE_ACTIVE_CURSOR
@slot:
    lda f:M7_CACHE_ACTIVE_CURSOR
    tax
    lda f:M7_VISIBLE_LIST,x
    and #255
    sta pattern_hi
    tax
    lda f:M7_PATTERN_SELECTED,x
    and #255
    beq @next
    cmp #2
    bne @add
    lda f:M7_CACHE_FINAL
    beq @next
@add:
    sep #$20
    .a8
    lda #0
    sta f:M7_PATTERN_SELECTED,x
    rep #$20
    .a16
    lda f:M7_LOGICAL_TO_PPU,x
    and #255
    sta f:M7_CACHE_PHYSICAL
    jsr mode7_queue_slot
    lda f:M7_CACHE_REMAIN
    dec a
    sta f:M7_CACHE_REMAIN
    lda m7_upload_slots
    cmp f:M7_CACHE_BUDGET
    bcs @done
@next:
    lda f:M7_CACHE_ACTIVE_CURSOR
    inc a
    sta f:M7_CACHE_ACTIVE_CURSOR
    cmp f:M7_CACHE_ACTIVE_COUNT
    jcc @slot
@done:
    rts

; Append one immutable RAM pattern and its physical destination.
mode7_queue_slot:
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
    lda f:M7_CACHE_PHYSICAL
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
    sta f:M7_LOGICAL_TO_PPU,x
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
    sta f:M7_NEW_VISIBLE,x
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
    sta f:M7_NEW_VISIBLE,x
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
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_MAP)
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
    sta f:M7_CACHE_PHYSICAL
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

; Use spare transfer capacity to fill future compiler slots while their
; physical cells are absent from both displayed and staged scenes.
mode7_cache_future:
    lda #0
    sta f:M7_PREFETCH_SCANNED
@slot:
    lda m7_upload_slots
.ifdef SA1_BUILD
    cmp f:M7_UPLOAD_LIMIT
.else
    cmp #16
.endif
    bcs @done
    lda f:M7_PREFETCH_CURSOR
    inc a
    and #255
    sta f:M7_PREFETCH_CURSOR
    sta pattern_hi
    tax
    lda f:M7_NEW_VISIBLE,x
    ora f:M7_OLD_VISIBLE,x
    and #255
    bne @next
    txa
    asl a
    tax
    lda f:PATTERN_CURRENT,x
    beq @next
    cmp f:M7_PATTERN_VRAM,x
    beq @next
    lda pattern_hi
    sta f:M7_CACHE_PHYSICAL
    jsr mode7_queue_slot
@next:
    lda f:M7_PREFETCH_SCANNED
    inc a
    sta f:M7_PREFETCH_SCANNED
    cmp #64
    bcc @slot
@done:
    rts

; Reuse a raw bitmap already resident under another logical lease. Without
; this lookup repeated shapes were uploaded again into new physical slots,
; wasting VBlank time and overflowing old/new scene residency at speed.
mode7_cache_hash:
    lda f:M7_HASH_DIRTY
    bne :+
    rts
:
    lda #0
    sta f:M7_HASH_DIRTY
    lda #$FFFF
    ldx #0
@clear:
    sta f:M7_RESIDENT_HASH,x
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
    lda f:M7_RESIDENT_HASH,x
    sta scratch2
    tya
    sta f:M7_RESIDENT_HASH,x
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
    sta f:M7_CACHE_LOGICAL
    sta scratch
    xba
    eor scratch
    and #255
    asl a
    tax
    lda f:M7_RESIDENT_HASH,x
@slot:
    cmp #$FFFF
    beq @done
    sta f:M7_CACHE_PHYSICAL
    tax
    lda f:M7_NEW_VISIBLE,x
    and #255
    cmp #2
    beq @next
    txa
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp f:M7_CACHE_LOGICAL
    beq @found
@next:
    lda f:M7_CACHE_PHYSICAL
    asl a
    tax
    lda f:M7_RESIDENT_NEXT,x
    bra @slot
@found:
    lda f:M7_CACHE_PHYSICAL
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
    clc
    adc map_dest
    sta map_dest
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
    lda f:M7_IDENTITY_MODE
    beq @translate
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
    beq @copied
    dec a
    ldx map_ptr
    phb
    mvn #.bankbyte(M7_MAP),#.bankbyte(M7_STAGE_MAP)
    plb
    bra @copied
@translate:
    lda transfer_len
    sta map_left
    lda #0
    sep #$20
    .a8
@pixel:
    lda [map_ptr],y
    tax
    lda f:M7_LOGICAL_TO_PPU,x
    sta [map_base_ptr],y
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
@copied:
    jsr mode7_cache_stage_span
@next:
    jsr audio_pump
    inc view_y
    dec view_rows
    jne @row
    lda #0
    ldx #0
@clean:
    sta f:M7_DIRTY_BITS,x
    inx
    inx
    cpx #128
    bcc @clean
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


