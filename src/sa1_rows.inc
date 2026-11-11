.ifdef ROM_PATTERN_NO_SPILL
worker_bw_to_iram:
    sta f:$002238
    txa
    sta f:$002232
    sep #$20
    .a8
    lda transfer_wbank
    sta f:$002234
    lda #0
    sta f:$002237
    lda #$81
    sta f:$002230
    rep #$20
    .a16
    tya
    sta f:$002235
    sep #$20
    .a8
    lda #0
    sta f:$002230
    lda #$20
    sta f:$00220B
    rep #$20
    .a16
    rts
worker_iram_to_bw:
    sta f:$002238
    txa
    sta f:$002232
    tya
    sta f:$002235
    sep #$20
    .a8
    lda #0
    sta f:$002234
    lda #$86
    sta f:$002230
    lda transfer_wbank
    sta f:$002237
    lda #0
    sta f:$002230
    lda #$20
    sta f:$00220B
    rep #$20
    .a16
    rts
worker_translate_row:
    lda M7_ROW_CODE_VALID
    bne @kernel_ready
    phx
    phy
    phb
    lda #__HOTROWS_SIZE__-1
    ldx #__HOTROWS_LOAD__
    ldy #__HOTROWS_RUN__
    mvn #$01,#$00
    plb
    ply
    plx
    lda #1
    sta M7_ROW_CODE_VALID
@kernel_ready:
    lda #0
    sta M7_CACHE_CODE_VALID
    lda transfer_len
    sta map_left
    sty m7_run_index
    lda #128
    sec
    sbc m7_run_index
    cmp map_left
    bcc :+
    lda map_left
:
    sta map_scan_x
    lda #.bankbyte(M7_MAP)
    sta transfer_wbank
    lda map_ptr
    clc
    adc m7_run_index
    tax
    ldy #$0500
    lda f:M7_IDENTITY_MODE
    beq :+
    ldy #$0600
:
    lda map_scan_x
    jsr worker_bw_to_iram
    lda map_left
    sec
    sbc map_scan_x
    beq @old
    pha
    lda map_scan_x
    clc
    adc #$0500
    pha
    lda f:M7_IDENTITY_MODE
    tax
    pla
    cpx #0
    beq :+
    clc
    adc #$0100
:
    tay
    ldx map_ptr
    pla
    jsr worker_bw_to_iram
@old:
    lda #.bankbyte(M7_STAGE_MAP)
    sta transfer_wbank
    lda map_dest
    and #M7_STAGE_MASK
    clc
    adc #.loword(M7_STAGE_MAP)
    tax
    ldy #$0580
    lda map_left
    jsr worker_bw_to_iram
    lda f:M7_IDENTITY_MODE
    beq :+
    lda #0
    sep #$20
    .a8
    jmp @compare
:
    .a16
    lda map_left
    and #$FFF8
    sta scratch
    ldy #0
    lda #0
    sep #$20
    .a8
    jsr worker_translate_kernel
@compare:
    lda map_left
    and #1
    beq @words
    ldx map_left
    lda #0
    sta $0580,x
    sta $0600,x
@words:
    rep #$20
    .a16
    ldy #0
@first:
    lda $0600,y
    cmp $0580,y
    bne @changed
    iny
    iny
    cpy map_left
    bcc @first
    clc
    rts
@changed:
    sty scratch
    lda map_left
    dec a
    and #$FFFE
    tay
@last:
    lda $0600,y
    cmp $0580,y
    bne @span
    dey
    dey
    bra @last
@span:
    tya
    inc a
    inc a
    cmp map_left
    bcc :+
    lda map_left
:
    sec
    sbc scratch
    sta transfer_len
    lda map_dest
    clc
    adc scratch
    sta map_dest
.ifdef ROM_WRAP_MAP
    lda NATIVE_ROW_UNDO
    beq @store_row
    lda #.bankbyte(NATIVE_STAGE_UNDO)
    sta transfer_wbank
    lda map_dest
    clc
    adc #.loword(NATIVE_STAGE_UNDO)
    tay
    lda scratch
    clc
    adc #$0580
    tax
    lda transfer_len
    jsr worker_iram_to_bw
    lda #.bankbyte(M7_STAGE_MAP)
    sta transfer_wbank
@store_row:
    lda map_dest
.endif
    and #M7_STAGE_MASK
    clc
    adc #.loword(M7_STAGE_MAP)
    tay
    lda scratch
    clc
    adc #$0600
    tax
    lda transfer_len
    jsr worker_iram_to_bw
    sec
    rts
.ifdef ROM_WRAP_MAP
; Revert only spans written by a cache attempt that never reached the PPU.
worker_undo_rows:
    stz map_scan_x
@row:
    ldx map_scan_x
    lda f:M7_DMA_LIST,x
    sta map_dest
    lda f:M7_DMA_LIST+2,x
    sta transfer_len
    lda #.bankbyte(NATIVE_STAGE_UNDO)
    sta transfer_wbank
    lda map_dest
    clc
    adc #.loword(NATIVE_STAGE_UNDO)
    tax
    ldy #$0580
    lda transfer_len
    jsr worker_bw_to_iram
    lda #.bankbyte(M7_STAGE_MAP)
    sta transfer_wbank
    lda map_dest
    clc
    adc #.loword(M7_STAGE_MAP)
    tay
    ldx #$0580
    lda transfer_len
    jsr worker_iram_to_bw
    lda map_scan_x
    clc
    adc #4
    sta map_scan_x
    lsr a
    lsr a
    cmp m7_row_count
    bcc @row
    rts
.endif
.segment "HOTROWS"
.a8
worker_translate_kernel:
    cpy scratch
    bcs @tail_check
@eight:
    .repeat 8
    lda $0500,y
    tax
    lda M7_LOGICAL_TO_PPU,x
    sta $0600,y
    iny
    .endrepeat
    cpy scratch
    bcc @eight
@tail_check:
    cpy map_left
    bcs @done
@tail:
    lda $0500,y
    tax
    lda M7_LOGICAL_TO_PPU,x
    sta $0600,y
    iny
    cpy map_left
    bcc @tail
@done:
    rts
.segment "CODE"
.a16
.endif
