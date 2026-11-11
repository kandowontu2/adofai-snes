.ifdef ROM_NATIVE_ADDR
.segment "CODE"
; Checkpoint/loading passes retain the canonical MSU decoder. Ordinary
; frames hand the same byte offset to SA-1's immutable ROM event stream.
native_animation_update:
    lda f:NATIVE_READY
    bne @ready
    jsr symbol_coords_reset
    jsr sa1_symbols
    lda #1
    sta msu_data_busy
    lda event_count
    sta f:NATIVE_SYMBOL_BYTES
    lda camera_zoom
    sta f:NATIVE_ZOOM
    lda camera_inverse
    sta f:NATIVE_INVERSE
    lda f:CAMERA_SCRIPT_X
    sta f:NATIVE_CAMERA_X
    lda f:CAMERA_SCRIPT_Y
    sta f:NATIVE_CAMERA_Y
    lda #(^FLOOR_ALPHA)&1
    sta transfer_wbank
    ldx #.loword(FLOOR_ALPHA)
    ldy #.loword(NATIVE_ALPHA)
    lda last_note
    inc a
    jsr native_seed_span
    lda #1
    sta transfer_wbank
    ldx #.loword(TRACK_PALETTE)
    ldy #.loword(NATIVE_PALETTE)
    lda #192
    jsr native_seed_span
    lda #1
    sta f:NATIVE_READY
    stz msu_data_busy
@ready:
    lda animation_cursor
    sec
    sbc animation_base
    sta f:NATIVE_OFFSET
    lda animation_cursor+2
    sbc animation_base+2
    sta f:NATIVE_OFFSET+2
    lda animation_header
    beq @offset_ready
    lda f:NATIVE_OFFSET
    sec
    sbc #7
    sta f:NATIVE_OFFSET
    lda f:NATIVE_OFFSET+2
    sbc #0
    sta f:NATIVE_OFFSET+2
@offset_ready:
    lda f:M7_RENDER_TIME
    sta f:NATIVE_TARGET
    lda #0
    sta f:SA1_DONE
    lda #8
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
    jsr sa1_service_rom_bank
    lda $2300
    and #$80
    beq @wait
    lda f:NATIVE_RESULT
    clc
    adc animation_base
    sta animation_cursor
    lda f:NATIVE_RESULT+2
    adc animation_base+2
    sta animation_cursor+2
    stz animation_header
    lda #1
    sta animation_seek_dirty
    lda f:NATIVE_ZOOM
    sta camera_zoom
    lda f:NATIVE_INVERSE
    sta camera_inverse
    lda f:NATIVE_CAMERA_X
    sta f:CAMERA_SCRIPT_X
    lda f:NATIVE_CAMERA_Y
    sta f:CAMERA_SCRIPT_Y
    lda f:NATIVE_SYMBOL_BYTES
    sta event_count
    lda f:NATIVE_ALPHA_DIRTY
    beq @palette
    lda #(^FLOOR_ALPHA)&1
    sta transfer_wbank
    lda f:NATIVE_ALPHA_BEGIN
    clc
    adc #.loword(NATIVE_ALPHA)
    tax
    lda f:NATIVE_ALPHA_BEGIN
    clc
    adc #.loword(FLOOR_ALPHA)
    tay
    lda f:NATIVE_ALPHA_END
    sec
    sbc f:NATIVE_ALPHA_BEGIN
    jsr native_receive_span
@palette:
    lda f:NATIVE_PALETTE_DIRTY
    beq @done
    cmp f:TRACK_PALETTE_DIRTY
    bcc :+
    sta f:TRACK_PALETTE_DIRTY
:
    lda #1
    sta transfer_wbank
    ldx #.loword(NATIVE_PALETTE)
    ldy #.loword(TRACK_PALETTE)
    lda f:NATIVE_PALETTE_DIRTY
    jsr native_receive_span
@done:
    rts

; X=WRAM offset, Y=BW-RAM offset, A=count, transfer_wbank=WRAM bank bit.
native_seed_span:
    sta $4305
    stx $2181
    sty $4302
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    lda #$42
    sta $4304
    lda #$80
    sta $4300
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    rts

; X=BW-RAM offset, Y=WRAM offset, A=count; source/destination reversed.
native_receive_span:
    pha
    lda #1
    sta msu_data_busy
    pla
    sta $4305
    stx $4302
    sty $2181
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    lda #$42
    sta $4304
    stz $4300
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    stz msu_data_busy
    rts
.endif
