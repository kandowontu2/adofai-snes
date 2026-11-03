; The authored stream leases only patterns intersecting the current camera.
; Maintain its active set as cells change, rather than rescanning 512 pixels
; and all 256 logical slots for every published frame.
mode7_references_reset:
    lda #0
    ldx #0
@clear:
    sta f:M7_REFERENCE_COUNTS,x
    inx
    inx
    cpx #512
    bcc @clear
    ldx #0
@flags:
    sta f:M7_VISIBLE_PATTERNS,x
    inx
    inx
    cpx #256
    bcc @flags
    lda #1
    sta f:M7_CACHE_ACTIVE_COUNT
    sep #$20
    .a8
    sta f:M7_VISIBLE_PATTERNS
    lda #0
    sta f:M7_VISIBLE_LIST
    sta f:M7_REFERENCE_POSITIONS
    rep #$20
    .a16
    rts

; A = old slot, animation_value = new slot. Preserve caller registers.
; Derive a slot from the count index only on a zero crossing. Ordinary
; count changes do not need the shared scratch slot or active-list work.
mode7_reference_change:
    pha
    phx
    phy
    and #255
    beq @new
    asl a
    tax
    lda f:M7_REFERENCE_COUNTS,x
    dec a
    sta f:M7_REFERENCE_COUNTS,x
    bne @new
    lda #1
    sta f:M7_POOL_DIRTY
    txa
    lsr a
    sta f:M7_REFERENCE_SLOT
    tax
    sep #$20
    .a8
    lda #0
    sta f:M7_VISIBLE_PATTERNS,x
    lda f:M7_REFERENCE_POSITIONS,x
    rep #$20
    .a16
    and #255
    sta f:M7_REFERENCE_INDEX
    lda f:M7_CACHE_ACTIVE_COUNT
    dec a
    sta f:M7_CACHE_ACTIVE_COUNT
    tax
    lda f:M7_VISIBLE_LIST,x
    and #255
    pha
    ldx #0
    lda f:M7_REFERENCE_INDEX
    tax
    pla
    sep #$20
    .a8
    sta f:M7_VISIBLE_LIST,x
    rep #$20
    .a16
    and #255
    tax
    lda f:M7_REFERENCE_INDEX
    sep #$20
    .a8
    sta f:M7_REFERENCE_POSITIONS,x
    rep #$20
    .a16
@new:
    lda animation_value
    and #255
    beq @done
    asl a
    tax
    lda f:M7_REFERENCE_COUNTS,x
    inc a
    sta f:M7_REFERENCE_COUNTS,x
    cmp #1
    bne @done
    sta f:M7_POOL_DIRTY
    txa
    lsr a
    sta f:M7_REFERENCE_SLOT
    tax
    lda f:M7_CACHE_ACTIVE_COUNT
    sep #$20
    .a8
    sta f:M7_REFERENCE_POSITIONS,x
    lda #1
    sta f:M7_VISIBLE_PATTERNS,x
    rep #$20
    .a16
    lda f:M7_CACHE_ACTIVE_COUNT
    tax
    inc a
    sta f:M7_CACHE_ACTIVE_COUNT
    lda f:M7_REFERENCE_SLOT
    sep #$20
    .a8
    sta f:M7_VISIBLE_LIST,x
    rep #$20
    .a16
@done:
    ply
    plx
    pla
    rts

mode7_references_rebuild:
    jsr mode7_references_reset
    ldx #0
@cell:
    cpx animation_cells
    bcs @done
    lda f:CELL_STATE,x
    and #255
    beq @next
    sta animation_value
    lda #0
    jsr mode7_reference_change
@next:
    inx
    bra @cell
@done:
    rts
