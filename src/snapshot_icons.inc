; One byte per floor, built during loading/retry, never per display frame.
; bits 0..1 speed, 2..3 twirl, 4..6 hold/release/planet/stack, 7 checkpoint.
.ifdef EXTENDED_CHART_BUILD
.segment "NEOCODE"
snapshot_icons_seed:
    lda selected_level
    asl a
    tax
    lda f:neo_preview_counts,x
    sta f:SNAPSHOT_ICON_HAS_PREVIEWS
    stz render_i
@floor:
    ldx render_i
    lda f:NOTE_FLAGS,x
    bit #128
    jne @hidden
    pha
    and #3
    sta event_end
    pla
    pha
    and #4
    beq @special
    lda f:NOTE_CCW,x
    and #1
    inc a
    asl a
    asl a
    ora event_end
    sta event_end
@special:
    pla
    pha
    and #48
    beq @checkpoint
    lda #$70
    ora event_end
    sta event_end
    pla
    pha
    and #32
    beq @checkpoint
    txa
    asl a
    tax
    lda f:NOTE_PAUSE,x
    bpl @release
    lda render_i
    jsl neo_far_hold_style
    inc a
    bra @kind
@release:
    cpx #0
    beq @checkpoint
    lda f:NOTE_PAUSE-2,x
    bpl @planets
    lda render_i
    dec a
    jsl neo_far_hold_style
    clc
    adc #3
    bra @kind
@planets:
    ldx render_i
    lda f:NOTE_CCW,x
    eor f:NOTE_CCW-1,x
    and #2
    beq @checkpoint
    lda f:NOTE_CCW,x
    and #2
    beq @two
    lda #5
    bra @kind
@two:
    lda #6
@kind:
    asl a
    asl a
    asl a
    asl a
    sta event_cursor
    lda event_end
    and #15
    ora event_cursor
    sta event_end
@checkpoint:
    pla
    and #64
    asl a
    ora event_end
    bra @store
@hidden:
    lda #0
@store:
    ldx render_i
    sep #$20
    .a8
    sta f:SNAPSHOT_ICON_INFO,x
    rep #$20
    .a16
    inc render_i
    lda render_i
    cmp last_note
    jcc @floor
    jeq @floor
    rtl

; Draw guides after the essential event symbols. The worker already
; produced their live projected floor list; only 2->3 entries need work.
snapshot_icon_previews:
    lda f:STREAM_MODE1
    cmp #3
    bne @done
    lda selected_level
    asl a
    tax
    lda f:neo_preview_counts,x
    beq @done
    stz event_cursor
@floor:
    lda event_cursor
    cmp f:SYMBOL_VISIBLE_COUNT
    bcs @done
    tax
    lda f:SYMBOL_VISIBLE,x
    sta render_i
    tax
    lda f:SNAPSHOT_ICON_INFO,x
    and #$70
    cmp #$50
    bne @next
    lda f:FLOOR_ALPHA,x
    and #255
    beq @next
    jsl neo_far_planet_preview
@next:
    inc event_cursor
    inc event_cursor
    bra @floor
@done:
    rtl
.segment "CODE"
.endif
