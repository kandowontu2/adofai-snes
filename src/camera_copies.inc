; Apply authored copy cameras to live planets/trails, after every ordinary
; object job has completed. Mode 3 owns just one pattern-run descriptor;
; the rest of that unused run arena is private to this bounded SA-1 job.
.segment "CODE"
clone_wait:
    jsr stream_wait_worker
    rtl
.segment "NEOCODE"
.export neo_camera_copies, neo_camera_copies_complete
neo_camera_copies:
    lda f:STREAM_MODE1
    cmp #3
    jne @done
    lda f:CLONE_COUNT
    jeq @done
    lda state
    cmp #1
    jne @done
    lda oam_pos
    sta f:CLONE_INPUT_BYTES
    lda #1
    sta msu_data_busy
    lda #OAM
    ldx #.loword(CLONE_INPUT)
    ldy oam_pos
    jsr clone_to_worker
    lda #OAM+512
    ldx #.loword(CLONE_INPUT+512)
    ldy #32
    jsr clone_to_worker
    ; The input is now immutable in cartridge RAM. Music refills use a
    ; different buffer and may run while SA-1 computes; only the actual
    ; WRAM-port DMA transactions need exclusive channel ownership.
    stz msu_data_busy
    lda #0
    sta f:SA1_DONE
    lda #11
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
    jsl $800000+clone_wait
    lda #1
    sta msu_data_busy
    ; Copies replace the original prefix and can contain fewer objects.
    ; Hide its discarded tail before downloading the shorter result, or
    ; NMI's previous-count upload can publish live, unbudgeted originals.
    lda f:CLONE_OUTPUT_BYTES
    tax
    lda #$E000
@hide_original_tail:
    cpx oam_pos
    bcs @download
    sta OAM,x
    inx
    inx
    inx
    inx
    bra @hide_original_tail
@download:
    lda f:CLONE_OUTPUT_BYTES
    tay
    lda #OAM
    ldx #.loword(CLONE_OUTPUT)
    jsr clone_from_worker
    lda #OAM+512
    ldx #.loword(CLONE_OUTPUT+512)
    ldy #32
    jsr clone_from_worker
    lda f:CLONE_OUTPUT_BYTES
    sta oam_pos
    stz msu_data_busy
@done:
neo_camera_copies_complete:
    rtl
clone_to_worker:
    sta $2181
    stx $4302
    sty $4305
    sep #$20
    .a8
    stz $2183
    lda #$42
    sta $4304
    lda #$80
    sta $4300
    bra clone_transfer
clone_from_worker:
    sta $2181
    stx $4302
    sty $4305
    sep #$20
    .a8
    stz $2183
    lda #$42
    sta $4304
    stz $4300
clone_transfer:
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    rts
.segment "CODE"
