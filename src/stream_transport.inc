; The first record can describe one direct-to-OBJ image. Keep its logical
; byte range in the packet, but route that range to bank $43 instead of $42.
; All other bytes, including the terminator and camera snapshot, retain their
; original packet offsets. The worker never reads the routed image hole.
.segment "CAMERA"
stream_copy_packet_chunk:
    sta map_left
    stx map_scan_x
    lda stream_length
    sec
    sbc stream_remaining
    sta scratch2
    bne @check_route
    lda #$FFFF
    sta f:STREAM_ROUTE_BEGIN
    sta f:STREAM_ROUTE_END
    lda #0
    sta f:STREAM_ROUTE_LEFT
    lda f:M7_CHR_LOW+2
    and #255
    cmp #33
    beq @table
    cmp #44
    beq @snapshot
    cmp #32
    bne @check_route
    lda #.loword(SPILL_CHR)
    sta f:STREAM_ROUTE_DEST
    lda f:M7_CHR_LOW+3
    sta f:STREAM_ROUTE_BEGIN
    clc
    adc f:M7_CHR_LOW+5
    sta f:STREAM_ROUTE_END
    bra @check_route
@snapshot:
    jsl stream_route_raw_snapshot
    bra @check_route
@table:
    lda f:M7_CHR_LOW+3
    dec a
    sta f:STREAM_ROUTE_LEFT
    lda #6
    sta f:STREAM_ROUTE_INDEX
    lda f:M7_CHR_LOW+7
    sta f:STREAM_ROUTE_BEGIN
    clc
    adc f:M7_CHR_LOW+9
    sta f:STREAM_ROUTE_END
    lda f:M7_CHR_LOW+11
    sta f:STREAM_ROUTE_DEST
@check_route:
    lda f:STREAM_ROUTE_BEGIN
    cmp #$FFFF
    bne @piece
    lda map_left
    ldx map_scan_x
 .ifdef SA1_FASTROM_MIRROR
    jml $800000+stream_copy_plain_chunk
.else
    jml stream_copy_plain_chunk
.endif
@piece:
    lda #$42
    sta map_dest
    lda scratch2
    clc
    adc #.loword(STREAM_BUFFER)
    sta view_rows
    lda scratch2
    cmp f:STREAM_ROUTE_BEGIN
    bcc @before
    cmp f:STREAM_ROUTE_END
    bcc @image
    lda f:STREAM_ROUTE_LEFT
    beq @tail
    dec a
    sta f:STREAM_ROUTE_LEFT
    lda f:STREAM_ROUTE_INDEX
    tax
    lda f:STREAM_BUFFER+7,x
    sta f:STREAM_ROUTE_BEGIN
    clc
    adc f:STREAM_BUFFER+9,x
    sta f:STREAM_ROUTE_END
    lda f:STREAM_BUFFER+11,x
    sta f:STREAM_ROUTE_DEST
    txa
    clc
    adc #6
    sta f:STREAM_ROUTE_INDEX
    jmp @piece
@tail:
    lda map_left
    bra @size
@before:
    lda f:STREAM_ROUTE_BEGIN
    sec
    sbc scratch2
    bra @size
@image:
    lda #$43
    sta map_dest
    lda scratch2
    sec
    sbc f:STREAM_ROUTE_BEGIN
    clc
    adc f:STREAM_ROUTE_DEST
    sta view_rows
    lda f:STREAM_ROUTE_END
    sec
    sbc scratch2
@size:
    cmp map_left
    bcc :+
    lda map_left
:
    sta transfer_len
    sta $4305
    lda view_rows
    sta $4302
    ldx map_scan_x
    stx $2181
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    lda map_dest
    sta $4304
    lda #$80
    sta $4300
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    lda map_scan_x
    clc
    adc transfer_len
    sta map_scan_x
    lda scratch2
    clc
    adc transfer_len
    sta scratch2
    lda map_left
    sec
    sbc transfer_len
    sta map_left
    jne @piece
    rtl
.segment "CODE"
stream_copy_plain_chunk:
    jsr native_seed_span
    rtl
.segment "NEOCODE"
stream_route_raw_snapshot:
    lda f:M1_FRONT_BANK
    eor #$0200
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #32
    sta f:STREAM_ROUTE_DEST
    lda #1319
    sta f:STREAM_ROUTE_BEGIN
    lda f:M7_CHR_LOW+3
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #1319
    sta f:STREAM_ROUTE_END
    rtl
.segment "CODE"
