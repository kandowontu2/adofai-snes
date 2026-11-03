; Shared animation format with an ordinary ROM source. Split DMA reads at
; bank boundaries: SNES DMA wraps its 16-bit source address within a bank.
; rom_data_ptr is independent of the logical animation and audio cursors.
rom_data_dma:
    lda transfer_len
    pha
    lda transfer_dest
    sta $2181
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    stz $4300
    lda #$80
    sta $4301
    rep #$20
    .a16
@run:
    lda transfer_len
    beq @done
    pha
    lda rom_data_ptr
    eor #$FFFF
    inc a
    beq @count_ready
    cmp transfer_len
    bcs @count_ready
    sta transfer_len
@count_ready:
    lda transfer_len
    sta $4305
    lda rom_data_ptr
    sta $4302
    sep #$20
    .a8
    lda rom_data_ptr+2
    sta $4304
    lda #1
    sta $420B
    rep #$20
    .a16
    lda rom_data_ptr
    clc
    adc transfer_len
    sta rom_data_ptr
    bcc @next
    sep #$20
    .a8
    inc rom_data_ptr+2
.ifdef SA1_BUILD
    bne :+
    jsr sa1_next_rom_page
:
.endif
    rep #$20
    .a16
@next:
    pla
    sec
    sbc transfer_len
    sta transfer_len
    bra @run
@done:
    pla
    sta transfer_len
    rts


.ifdef SA1_BUILD
; Called with A8, after a sequential read crosses the mapped 1-MiB window.
sa1_next_rom_page:
    .a8
    lda f:$40000C
    inc a
    and #7
    sta f:$40000C
    sta $2223
    lda #$F0
    sta rom_data_ptr+2
    rts
    .a16
.endif
