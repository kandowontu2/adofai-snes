; Secondary exact-color tile cache in the unused first half of OBJ name 1.
; Hardware sprites cover only cells redirected out of the Mode 7 atlas.
worker_spill_begin:
    lda f:SPILL_VISIBLE
    beq :+
    lda #1
    sta f:M7_POOL_DIRTY
:
    lda #0
    sta f:SPILL_VISIBLE
    sta f:SPILL_COUNT
    sta f:M7_SPILL_ELIGIBLE
    sta SPILL_LIVE_COUNT
    sta SPILL_MAP_ACTIVE
    ldx #0
@clear:
    sta f:SPILL_LOGICAL,x
    inx
    inx
    cpx #256
    bcc @clear
    ldx #0
@masks:
    sta f:SPILL_NEW,x
    sta f:SPILL_QUEUED,x
    inx
    inx
    cpx #128
    bcc @masks
    lda f:M7_BITMAP_ENABLED
    beq @done
.ifdef ROM_PATTERN_NO_SPILL
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    beq @done
.endif
    lda f:M7_ROT_COS
    cmp #256
    bne @done
    lda f:M7_ROT_SIN
    ora f:M7_RASTER_SHIFT
    bne @done
    lda #1
    sta f:M7_SPILL_ELIGIBLE
@done:
    rts

worker_spill_find:
.ifdef ROM_PATTERN_COUNT
    cmp #ROM_PATTERN_COUNT
    bcs @absent
    sta scratch
    tax
    lda f:M7_RAW_TO_SPILL,x
    and #127
    tay
    asl a
    tax
    lda f:SPILL_TAGS,x
    cmp scratch
    bne @absent
    tya
    rts
@absent:
    lda #$FFFF
    rts
.else
    sta scratch
    ldx #0
@slot:
    lda f:SPILL_TAGS,x
    cmp scratch
    beq @found
    inx
    inx
    cpx #256
    bcc @slot
    lda #$FFFF
    rts
@found:
    txa
    lsr a
    rts
.endif

worker_spill_prefetch:
    lda f:M7_SPILL_ELIGIBLE
    jeq @full
    lda M7_BITMAP_TAG
    jsr worker_spill_find
    cmp #$FFFF
    jne @present
    lda f:SPILL_COUNT
    cmp #2
    bcc @room
    lda M7_BITMAP_URGENT
    jeq @full
    lda f:SPILL_COUNT
    cmp #8
    jcs @full
@room:
    lda #$FFFF
    sta SPILL_CHOICE
    lda #0
    sta SPILL_BEST
    ldy #0
@slot:
    tyx
    lda f:SPILL_NEW,x
    ora f:SPILL_OLD,x
    ora f:SPILL_QUEUED,x
    and #255
    bne @next
    tya
    asl a
    tax
    lda f:SPILL_TAGS,x
    cmp #$FFFF
    beq @free
    lda f:SPILL_DEADLINES,x
    cmp f:M7_RENDER_TIME
    bcc @free
    cmp M7_BITMAP_DEADLINE
    bcc @next
    cmp SPILL_BEST
    bcc @next
    sta SPILL_BEST
    tya
    sta SPILL_CHOICE
    bra @next
@free:
    tya
    sta SPILL_CHOICE
    bra @chosen
@next:
    iny
    cpy #128
    bcc @slot
@chosen:
    lda SPILL_CHOICE
    cmp #$FFFF
    beq @full
    tax
    sep #$20
    .a8
    lda #1
    sta f:SPILL_QUEUED,x
    rep #$20
    .a16
    lda f:SPILL_COUNT
    asl a
    asl a
    tax
    lda SPILL_CHOICE
    sta f:SPILL_QUEUE,x
    lda M7_BITMAP_TAG
    sta f:SPILL_QUEUE+2,x
    lda f:SPILL_COUNT
    inc a
    sta f:SPILL_COUNT
    jsr worker_spill_convert
    lda SPILL_CHOICE
@present:
    asl a
    tax
    lda M7_BITMAP_DEADLINE
    sta f:SPILL_DEADLINES,x
    sec
    rts
@full:
    clc
    rts

worker_spill_convert:
.ifdef SPILL_PATTERN_ADDR
    lda M7_BITMAP_TAG
    .repeat 11
    lsr a
    .endrepeat
    clc
    adc #.bankbyte(SPILL_PATTERN_ADDR)
    sta transfer_ptr+2
    lda M7_BITMAP_TAG
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #.loword(SPILL_PATTERN_ADDR)
    sta transfer_ptr
    bcc :+
    inc transfer_ptr+2
:
    lda SPILL_CHOICE
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #.loword(SPILL_CHR)
    tax
    lda #32
    jmp worker_rom_dma
.else
    lda M7_BITMAP_CURSOR
    .repeat 10
    lsr a
    .endrepeat
    clc
    adc #.bankbyte(M7_BITMAP_SRAM)
    sta transfer_ptr+2
    lda M7_BITMAP_CURSOR
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_BITMAP_SRAM)
    sta transfer_ptr
    bcc :+
    inc transfer_ptr+2
:
    lda SPILL_CHOICE
    .repeat 5
    asl a
    .endrepeat
    sta SPILL_SCAN
    tax
    lda #0
    .repeat 8,I
    sta f:SPILL_CHR+16+I*2,x
    .endrepeat
    ldy #0
@row:
    lda #0
    sta SPILL_PLANE0
    sta SPILL_PLANE1
    ldx #8
@pixel:
    lda [transfer_ptr],y
    and #255
    cmp #32
    lda SPILL_PLANE0
    rol a
    sta SPILL_PLANE0
    lda [transfer_ptr],y
    and #255
    cmp #33
    lda SPILL_PLANE1
    rol a
    sta SPILL_PLANE1
    iny
    dex
    bne @pixel
    lda SPILL_SCAN
    tax
    lda SPILL_PLANE1
    xba
    and #$FF00
    ora SPILL_PLANE0
    sta f:SPILL_CHR,x
    inx
    inx
    txa
    sta SPILL_SCAN
    cpy #64
    bcc @row
    rts
.endif

worker_spill_commit:
    phb
    lda #127
    ldx #.loword(SPILL_NEW)
    ldy #.loword(SPILL_OLD)
    mvn #$43,#$43
    plb
    rts

worker_spill_cells:
    lda SPILL_MAP_ACTIVE
    jne @done
    lda #0
    sta f:SPILL_VISIBLE
    lda f:M7_SPILL_ELIGIBLE
    jeq @done
    lda SPILL_LIVE_COUNT
    jeq @done
    lda f:M7_VIEW_Y
    sta SPILL_ROW
    lda f:M7_VIEW_H
    sta SPILL_REMAIN
    lda f:M7_VIEW_X
    asl a
    asl a
    asl a
    sec
    sbc f:M7_RASTER_X
    sta SPILL_COL
    sep #$20
    .a8
    lda #.bankbyte(M7_MAP)
    sta map_ptr+2
    rep #$20
    .a16
@row:
    ; Screen Y and the wrapped world-row pointer are invariant across
    ; this row. Keep empty cells in an eight-bit lookup loop.
    lda SPILL_ROW
    asl a
    asl a
    asl a
    sec
    sbc f:M7_RASTER_Y
    cmp #25
    jcc @row_next
    cmp #177
    jcs @row_next
    sta SPILL_Y
    lda SPILL_ROW
    and #127
    .repeat 7
    asl a
    .endrepeat
    clc
    adc #.loword(M7_MAP)
    sta map_ptr
    lda f:M7_VIEW_X
    and #127
    tay
    lda f:M7_VIEW_W
    sta map_left
    lda #0
    sep #$20
    .a8
@cell:
    lda [map_ptr],y
    tax
    lda f:SPILL_LOGICAL,x
    beq @next
    rep #$20
    .a16
    and #255
    dec a
    sta SPILL_TILE
    lda f:M7_VIEW_W
    sec
    sbc map_left
    asl a
    asl a
    asl a
    clc
    adc SPILL_COL
    cmp #$FFF9
    bcs @x_ok
    cmp #256
    bcs @next16
@x_ok:
    sta SPILL_X
    lda f:SPILL_VISIBLE
    cmp #100
    bcs @next16
    inc a
    sta f:SPILL_VISIBLE
    dec a
    asl a
    sta scratch
    asl a
    clc
    adc scratch
    tax
    lda SPILL_X
    sta f:SPILL_FRAME,x
    lda SPILL_Y
    sta f:SPILL_FRAME+2,x
    lda SPILL_TILE
    sta f:SPILL_FRAME+4,x
@next16:
    lda #0
    sep #$20
    .a8
@next:
    iny
    cpy #128
    bcc :+
    ldy #0
:
    dec map_left
    lda map_left
    jne @cell
    rep #$20
    .a16
@row_next:
    lda SPILL_ROW
    inc a
    sta SPILL_ROW
    lda SPILL_REMAIN
    dec a
    sta SPILL_REMAIN
    jne @row
@done:
    rts

; A full translated map pass already visits every overlay cell in order.
; Gather those cells during translation instead of scanning the map again.
worker_spill_map_begin:
    lda #0
    sta SPILL_MAP_ACTIVE
    sta f:SPILL_VISIBLE
    lda f:M7_SPILL_ELIGIBLE
    beq @done
    lda SPILL_LIVE_COUNT
    beq @done
    lda f:M7_STAGE_FORCE
    beq @done
    lda f:M7_IDENTITY_MODE
    bne @done
    lda #1
    sta SPILL_MAP_ACTIVE
    lda f:M7_VIEW_X
    asl a
    asl a
    asl a
    sec
    sbc f:M7_RASTER_X
    sta SPILL_COL
@done:
    rts

; A8 contains the overlay slot plus one. Preserve the row translator's
; logical X, wrapped Y, scratch, pointers, dirty bounds and span counters.
worker_spill_map_pixel:
    phx
    rep #$20
    .a16
    and #255
    dec a
    sta SPILL_TILE
    lda transfer_len
    sec
    sbc map_left
    asl a
    asl a
    asl a
    clc
    adc SPILL_COL
    cmp #$FFF9
    bcs @x_ok
    cmp #256
    bcs @done
@x_ok:
    sta SPILL_X
    lda f:SPILL_VISIBLE
    cmp #100
    bcs @done
    inc a
    sta f:SPILL_VISIBLE
    dec a
    asl a
    sta SPILL_SCAN
    asl a
    clc
    adc SPILL_SCAN
    tax
    lda SPILL_X
    sta f:SPILL_FRAME,x
    lda SPILL_Y
    sta f:SPILL_FRAME+2,x
    lda SPILL_TILE
    sta f:SPILL_FRAME+4,x
@done:
    lda #0
    sep #$20
    .a8
    plx
    rts
    .a16

worker_spill_runs:
    lda #0
    sta f:SPILL_RUN_COUNT
    lda f:SPILL_COUNT
    jeq @done
    sta map_left
    ldx #0
    lda #$FFFF
    sta scratch2
@entry:
    lda f:SPILL_QUEUE,x
    cmp scratch2
    bne @new
    phy
    lda f:SPILL_RUN_COUNT
    tay
    dey
    tya
    asl a
    sta scratch
    asl a
    clc
    adc scratch
    tay
    phx
    tyx
    lda f:SPILL_RUNS+4,x
    clc
    adc #32
    sta f:SPILL_RUNS+4,x
    plx
    ply
    bra @next
@new:
    phx
    lda f:SPILL_RUN_COUNT
    asl a
    sta scratch
    asl a
    clc
    adc scratch
    tay
    lda f:SPILL_QUEUE,x
    .repeat 4
    asl a
    .endrepeat
    clc
    adc #$7000
    tyx
    sta f:SPILL_RUNS,x
    plx
    phx
    lda f:SPILL_QUEUE,x
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #.loword(SPILL_CHR)
    tyx
    sta f:SPILL_RUNS+2,x
    lda #32
    sta f:SPILL_RUNS+4,x
    plx
    lda f:SPILL_RUN_COUNT
    inc a
    sta f:SPILL_RUN_COUNT
@next:
    lda f:SPILL_QUEUE,x
    inc a
    sta scratch2
    inx
    inx
    inx
    inx
    dec map_left
    bne @entry
@done:
    rts

worker_spill_tags:
    lda f:SPILL_TAG_COUNT
    beq @done
    sta map_left
    ldx #0
@tag:
    lda f:SPILL_QUEUE+2,x
    sta scratch
    lda f:SPILL_QUEUE,x
    asl a
    phx
    tax
    lda scratch
    sta f:SPILL_TAGS,x
.ifdef ROM_PATTERN_COUNT
    txa
    lsr a
    sta scratch2
    ldx scratch
    sep #$20
    .a8
    lda scratch2
    sta f:M7_RAW_TO_SPILL,x
    rep #$20
    .a16
.endif
    plx
    inx
    inx
    inx
    inx
    dec map_left
    bne @tag
    lda #0
    sta f:SPILL_TAG_COUNT
@done:
    rts
