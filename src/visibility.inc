; Sparse per-cell animation timelines use the music clock through seeks,
; checkpoint count-ins, and paused/frozen scenes.
load_visibility:
    lda selected_level
    asl a
    sta visibility_middle
    asl a
    clc
    adc visibility_middle
    tax
    lda f:visibility_descriptors,x
    sta visibility_index_ptr
    sep #$20
    .a8
    lda f:visibility_descriptors+2,x
    sta visibility_index_ptr+2
    rep #$20
    .a16
    lda f:visibility_descriptors+3,x
    sta visibility_nodes
.ifdef MSU_BUILD
    asl a
    clc
    adc visibility_index_ptr
    sta visibility_ptr
    lda visibility_index_ptr+2
    and #255
    adc #0
    sep #$20
    .a8
    sta visibility_ptr+2
    rep #$20
    .a16
.endif
    lda f:visibility_descriptors+5,x
    and #255
    sta moving_tiles
    lda #$FFFF
    sta visibility_last_time
    rts

.ifndef MSU_BUILD
resolve_visibility:
    bit #$2000
    bne @animated
    pha
    lda #$FFFF
    sta visibility_next
    pla
    rts
@animated:
    pha
    and #$C000
    lsr a
    sta visibility_middle
    pla
    and #$1FFF
    ora visibility_middle
.ifdef MSU_BUILD
    phx
    tax
    lda f:CELL_STATE,x
    and #255
    plx
    pha
    stz visibility_next
    pla
    rts
.endif
.ifndef MSU_BUILD
resolve_visibility_node:
    sta visibility_middle
    stz visibility_index_hi
    asl a
    rol visibility_index_hi
    clc
    adc visibility_middle
    bcc :+
    inc visibility_index_hi
:
    clc
    adc visibility_index_ptr
    sta visibility_ptr
    lda visibility_index_ptr+2
    and #255
    adc visibility_index_hi
    sep #$20
    .a8
    sta visibility_ptr+2
    rep #$20
    .a16
    lda [visibility_ptr]
    pha
    ldy #2
    lda [visibility_ptr],y
    and #255
    sta visibility_bank
    pla
    sta visibility_ptr
    sep #$20
    .a8
    lda visibility_bank
    sta visibility_ptr+2
    rep #$20
    .a16
    lda [visibility_ptr]
    sta visibility_high
    stz visibility_low
@search:
    lda visibility_low
    cmp visibility_high
    bcs @found
    clc
    adc visibility_high
    lsr a
    sta visibility_middle
    asl a
    asl a
    inc a
    inc a
    tay
    lda [visibility_ptr],y
    cmp chart_time
    beq @later
    bcc @later
    lda visibility_middle
    sta visibility_high
    bra @search
@later:
    lda visibility_middle
    inc a
    sta visibility_low
    bra @search
@found:
    lda visibility_low
    asl a
    asl a
    tay
    lda [visibility_ptr],y
    pha
    lda visibility_low
    cmp [visibility_ptr]
    bcs @last
    iny
    iny
    lda [visibility_ptr],y
    bra @next_time
@last:
    lda #$FFFF
@next_time:
    sta visibility_next
    pla
    rts

.endif
.endif
update_dynamic_cells:
.ifdef MSU_BUILD
    rts
.else
    lda visibility_nodes
    beq @done
    lda chart_time
    cmp visibility_last_time
    beq @done
    sta visibility_last_time
    ldx #0
@cell:
    lda f:DYNAMIC_CACHE,x
    bit #$2000
    beq @next
    lda f:DYNAMIC_NEXT,x
    cmp chart_time
    beq @update
    bcs @next
@update:
    lda f:DYNAMIC_CACHE,x
    jsr resolve_visibility
    pha
    lda visibility_next
    sta f:DYNAMIC_NEXT,x
    pla
    cmp TRACK,x
    beq @next
    sta TRACK,x
    lda #1
    sta track_dirty
@next:
    inx
    inx
    cpx #2048
    bcc @cell
@done:
    rts

.endif
visible_floor:
.ifdef MSU_BUILD
    phx
    tax
    lda f:FLOOR_ALPHA,x
    and #255
    plx
    cmp #0
    rts
.else
    ldy visibility_nodes
    bne @animated
    lda #3
    rts
@animated:
    clc
    adc visibility_nodes
    jmp resolve_visibility_node
.endif

; A is a floor number. Camera, planets, symbols and trails share BG motion.
floor_position:
    sta position_i
    asl a
    tax
.ifdef ROM_NATIVE_ADDR
    lda f:NATIVE_READY
    beq @ordinary_position
.ifdef SA1_STREAM_BUILD
    lda f:STREAM_ENABLED
    bne @native_enabled
.endif
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @ordinary_position
@native_enabled:
    lda state
    cmp #1
    beq @native_position
    cmp #2
    beq @native_position
    cmp #4
    bne @ordinary_position
@native_position:
    lda f:SYMBOL_X,x
    sec
    sbc f:M7_ORIGIN_X
    sta floor_x
    lda f:SYMBOL_Y,x
    sec
    sbc f:M7_ORIGIN_Y
    sta floor_y
    rts
@ordinary_position:
.endif
    lda f:NOTE_X,x
.ifdef SA1_BUILD
    sec
    sbc f:M7_ORIGIN_X
.endif
    sta floor_x
    lda f:NOTE_Y,x
.ifdef SA1_BUILD
    sec
    sbc f:M7_ORIGIN_Y
.endif
    sta floor_y
.ifdef MSU_BUILD
    rts
.else
    lda moving_tiles
    beq @done
    lda f:POSITION_NEXT_X,x
    cmp chart_time
    bcc @x_update
    beq @x_update
    lda f:POSITION_X,x
    sta floor_x
    bra @y
@x_update:
    lda position_i
    clc
    adc visibility_nodes
    adc last_note
    inc a
    jsr resolve_visibility_node
    sta floor_x
    lda position_i
    asl a
    tax
    lda floor_x
    sta f:POSITION_X,x
    lda visibility_next
    sta f:POSITION_NEXT_X,x
@y:
    lda f:POSITION_NEXT_Y,x
    cmp chart_time
    bcc @y_update
    beq @y_update
    lda f:POSITION_Y,x
    sta floor_y
    rts
@y_update:
    lda position_i
    clc
    adc visibility_nodes
    adc last_note
    adc last_note
    inc a
    inc a
    jsr resolve_visibility_node
    sta floor_y
    lda position_i
    asl a
    tax
    lda floor_y
    sta f:POSITION_Y,x
    lda visibility_next
    sta f:POSITION_NEXT_Y,x
@done:
    rts

.endif
reset_motion_cache:
.ifdef MSU_BUILD
    rts
.else
    lda moving_tiles
    beq @done
    lda last_note
    inc a
    asl a
    sta visibility_high
    ldx #0
    lda #0
@floor:
    sta f:POSITION_NEXT_X,x
    sta f:POSITION_NEXT_Y,x
    inx
    inx
    cpx visibility_high
    bcc @floor
@done:
    rts
.endif
