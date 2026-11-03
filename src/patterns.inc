; The compiler prefetches at most 12 patterns per source frame, into slots
; that are no longer referenced. Staged transfers commit with the BG map.
load_patterns:
    lda selected_level
    asl a
    asl a
    asl a
    tax
    lda pattern_descriptors,x
    sta pattern_base
    lda pattern_descriptors+2,x
    and #255
    sta pattern_base+2
    lda pattern_descriptors+6,x
    sta pattern_nodes
    beq @done
    lda pattern_descriptors+3,x
    sta transfer_ptr
    sep #$20
    .a8
    lda pattern_descriptors+5,x
    sta transfer_ptr+2
    rep #$20
    .a16
    lda #2048
    sta transfer_len
    lda #.loword(PATTERN_CURRENT)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr upload_wram
    lda #0
    ldx #0
@next:
    sta f:PATTERN_NEXT,x
    inx
    inx
    cpx #2048
    bcc @next
    stz pattern_global_next
@done:
    rts

pattern_address:
    stz pattern_hi
    .repeat 4
    asl a
    rol pattern_hi
    .endrepeat
    clc
    adc pattern_base
    sta transfer_ptr
    lda pattern_base+2
    adc pattern_hi
    sep #$20
    .a8
    sta transfer_ptr+2
    rep #$20
    .a16
    rts

update_pattern_cache:
    stz pattern_queue_count
    lda pattern_nodes
    jeq @done
    lda pattern_global_next
    cmp chart_time
    jeq @scan
    jcc @scan
    rts
@scan:
    lda #$FFFF
    sta pattern_next_min
    stz pattern_slot
@slot:
    ldx pattern_slot
    lda f:PATTERN_NEXT,x
    cmp chart_time
    bcc @update
    beq @update
    bra @minimum
@update:
    txa
    lsr a
    clc
    adc pattern_nodes
    jsr resolve_visibility_node
    sta pattern_raw
    ldx pattern_slot
    lda visibility_next
    sta f:PATTERN_NEXT,x
    lda pattern_raw
    cmp f:PATTERN_CURRENT,x
    beq @deadline
    sta f:PATTERN_CURRENT,x
    jsr pattern_address
    lda pattern_queue_count
    asl a
    asl a
    asl a
    tax
    lda transfer_ptr
    sta f:PATTERN_QUEUE,x
    lda transfer_ptr+2
    and #255
    sta f:PATTERN_QUEUE+2,x
    lda pattern_slot
    asl a
    asl a
    asl a
    sta f:PATTERN_QUEUE+4,x
    inc pattern_queue_count
@deadline:
    ldx pattern_slot
    lda f:PATTERN_NEXT,x
@minimum:
    cmp pattern_next_min
    bcs @next
    sta pattern_next_min
@next:
    inc pattern_slot
    inc pattern_slot
    lda pattern_slot
    cmp #2048
    bcc @slot
    lda pattern_next_min
    sta pattern_global_next
@done:
    rts

restore_pattern_cache:
    lda pattern_nodes
    jeq @done
    stz pattern_slot
    stz pattern_queue_count
@slot:
    lda pattern_slot
    lsr a
    clc
    adc pattern_nodes
    jsr resolve_visibility_node
    ldx pattern_slot
    sta f:PATTERN_CURRENT,x
    pha
    lda visibility_next
    sta f:PATTERN_NEXT,x
    pla
    jsr pattern_address
    lda pattern_slot
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
@copy:
    lda [transfer_ptr],y
    sta f:CHR_RAM,x
    iny
    iny
    inx
    inx
    cpy #16
    bcc @copy
    lda #0
@zero:
    sta f:CHR_RAM,x
    inx
    inx
    iny
    iny
    cpy #32
    bcc @zero
    inc pattern_slot
    inc pattern_slot
    lda pattern_slot
    cmp #2048
    bcc @slot
    sep #$20
    .a8
    lda #$80
    sta $2100
    rep #$20
    .a16
    GFX CHR_RAM,0,32768
    DESC_PTR 0
    jsr load_chart_arrays
    stz pattern_global_next
    lda #1
    sta pattern_blanked
@done:
    rts
