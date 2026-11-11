; Playing HUD text changes only on row 3 (score), row 22 (feedback), and
; rows 24/25 (meter). Menus, transitions and calibration keep a full upload.
.segment "CODE"
.a8
.i16
hud_upload_frame:
    lda hud_dirty
    jeq @done
.ifdef ROM_WRAP_MAP
    ldx selected_level
    cpx #ROM_PATTERN_LEVEL
    beq @setup
.endif
    lda pattern_skip_hud
    jne @done
.ifdef ROM_WRAP_MAP
@setup:
.endif
    lda #1
    sta $4300
    lda #$18
    sta $4301
    stz $4304
    lda state
    cmp #1
    jne @full
    lda hud_full_dirty
    jne @full
    ; Keep pending text/glyph dirties when a near-full map snapshot needs
    ; this VBlank. The next smaller snapshot publishes the same hit history.
    rep #$20
    .a16
    lda m7_row_count
    cmp #28
    bcc @partial
    lda m7_row_span
    cmp #1536
    bcc @partial
    lda pattern_skip_hud
    jne @done_wide
@partial:
    sep #$20
    .a8
    ldx #$7800+3*32+8
    stx $2116
    ldx #HUD+3*64+16
    stx $4302
    ldx #40
    stx $4305
    lda #1
    sta $420B
    ldx #$7800+22*32+10
    stx $2116
    ldx #HUD+22*64+20
    stx $4302
    ldx #24
    stx $4305
    lda #1
    sta $420B
    lda hud_meter_dirty
    beq @meter
    ldx #$7800+24*32+7
    stx $2116
    ldx #HUD+24*64+14
    stx $4302
    ldx #34
    stx $4305
    lda #1
    sta $420B
    ldx #$7800+25*32+7
    stx $2116
    ldx #HUD+25*64+14
    stx $4302
    ldx #34
    stx $4305
    lda #1
    sta $420B
    stz hud_meter_dirty
    bra @meter
@full:
    lda state
    cmp #1
    bne @upload_full
    lda pattern_skip_hud
    jne @done
    lda pattern_queue_count
    cmp #17
    jcs @done
@upload_full:
    ldx #$7800
    stx $2116
    ldx #HUD
    stx $4302
    ldx #1792
    stx $4305
    lda #1
    sta $420B
    stz hud_full_dirty
    stz hud_meter_dirty
@meter:
    lda meter_bitmap_dirty
    beq @clean
    ldx #$5400
    stx $2116
    ldx #$DE00
    stx $4302
    lda #$7F
    sta $4304
    ldx #272
    stx $4305
    lda #1
    sta $420B
    stz meter_bitmap_dirty
@clean:
    stz hud_dirty
@done:
    stz $4304
    rts
@done_wide:
    sep #$20
    .a8
    bra @done
.a16
.segment "CODE"
