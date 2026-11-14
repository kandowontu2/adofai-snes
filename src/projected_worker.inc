; Mode 1 projected frames stage speculative CHR well ahead of use. Several
; source timestamps may arrive in one render. Prioritize all currently
; referenced pixels, then use only the remaining VBlank for speculative CHR.
; Unsent entries remain dirty; no animation frames or source pixels are cut.
; One IRAM byte per slot: dirty=1, required=2, selected=4. This arena is
; the Mode 7 allocator's workspace, unused by the projected renderer.
M1_REQUIRED=$000100
M1_SELECTED=M1_REQUIRED
M1_REMAINING=native_time
M1_REQUIRED_BYTES=native_kind
M1_PRIORITY_BYTES=native_index
M1_PRIORITY=$422000
M1_REQUIRED_LIMIT=$422800
M1_PRIORITY_LIMIT=$422802

.segment "CODE"
worker_projected_priority:
    lda native_index
    asl a
    sta f:M1_REQUIRED_LIMIT
    lda native_value
    sta f:M1_PRIORITY_LIMIT
    beq @done
    dec a
    phb
    ldx transfer_ptr
    ldy #.loword(M1_PRIORITY)
    mvn #$42,#$42
    plb
    lda native_value
    jsr worker_native_advance
@done:
    rts

worker_projected_code:
    lda M7_CACHE_CODE_VALID
    cmp #4
    beq @ready
    phb
    lda #__HOTPROJECTED_SIZE__-1
    ldx #__HOTPROJECTED_LOAD__
    ldy #__HOTPROJECTED_RUN__
    mvn #$01,#$00
    plb
    lda #0
    sta M7_ROW_CODE_VALID
    lda #4
    sta M7_CACHE_CODE_VALID
@ready:
    rts

.segment "HOTPROJECTED"
worker_projected_runs:
    lda #0
    sta f:M1_RUN_COUNT
    phb
    ldx #.loword(M1_DIRTY)
    ldy #M1_REQUIRED
    lda #1023
    mvn #$42,#$00
    plb
    lda f:M1_REQUIRED_LIMIT
    sta M1_REQUIRED_BYTES
    lda f:M1_PRIORITY_LIMIT
    sta M1_PRIORITY_BYTES
    lda m7_row_count
    .repeat 6
    asl a
    .endrepeat
    clc
    adc m7_row_span
    sta scratch
    lda #4800
    sec
    sbc scratch
    bcs :+
    lda #0
:
    sta M1_REMAINING
    lda #.loword(M1_PRIORITY)
    sta map_base_ptr
    lda #^M1_PRIORITY
    sta map_base_ptr+2
    ldy #0
@candidate:
    cpy M1_PRIORITY_BYTES
    bcs @candidates_done
    lda [map_base_ptr],y
    tax
    lda M1_SELECTED,x
    and #1
    beq @candidate_next
    jsr worker_projected_increment
    sta scratch
    lda M1_REMAINING
    sec
    sbc scratch
    bcs @select
    cpy M1_REQUIRED_BYTES
    bcs @candidate_next
    lda #0
@select:
    sta M1_REMAINING
    sep #$20
    .a8
    lda #4
    sta M1_SELECTED,x
    rep #$20
    .a16
@candidate_next:
    iny
    iny
    bra @candidate
@candidates_done:
    ldx #0
@scan:
    lda M1_SELECTED,x
    bit #$0404
    beq @next_pair
    and #4
    beq @next
    stx scratch
@run:
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
    lda M1_SELECTED,x
    and #4
    bne @run
    cpx #1023
    bcs @run_done
    lda M1_SELECTED+1,x
    and #4
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
    bra @check
@next:
    inx
    bra @check
@next_pair:
    inx
    inx
@check:
    cpx #1024
    bcc @scan
    rts

; Exact marginal cost under the worker's one-glyph bridge rule.
worker_projected_increment:
    stz scratch
    stz scratch2
    cpx #0
    beq @right
    lda M1_SELECTED-1,x
    and #4
    beq @left_two
    inc scratch
    bra @right
@left_two:
    cpx #2
    bcc @right
    lda M1_SELECTED-2,x
    and #4
    beq @right
    lda #2
    sta scratch
@right:
    cpx #1023
    bcs @sum
    lda M1_SELECTED+1,x
    and #4
    beq @right_two
    inc scratch2
    bra @sum
@right_two:
    cpx #1022
    bcs @sum
    lda M1_SELECTED+2,x
    and #4
    beq @sum
    lda #2
    sta scratch2
@sum:
    lda scratch
    beq @one_side
    lda scratch2
    beq @one_side
    clc
    adc scratch
    cmp #3
    bcs @merge
    lda #0
    rts
@merge:
    dec a
    .repeat 5
    asl a
    .endrepeat
    sec
    sbc #60
    rts
@one_side:
    lda scratch
    clc
    adc scratch2
    bne @extension
    lda #92
    rts
@extension:
    .repeat 5
    asl a
    .endrepeat
    rts
.segment "CODE"
