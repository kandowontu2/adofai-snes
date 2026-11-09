; Published-map commits use immutable staging. Background prefetch has
; separate registers and excludes the pattern being downloaded by main.
; A held frame still has a VBlank. Prefetch only a complete pattern whose
; previous global lease has ended in the displayed scene. Channel 5 keeps
; the interrupted animation reader's channel-0 registers intact.
mode7_prefetch:
    lda f:M7_CACHE_READY
    beq @done
    jsr mode7_commit_patterns
    lda #0
    sta f:M7_CACHE_READY
    sep #$20
    .a8
    lda $4212
    bit #$80
    bne :+
    rep #$20
    .a16
    inc pattern_vblank_overruns
:
    rep #$20
    .a16
@done:
    rts

mode7_prime_hdma:
    ldx #.loword(hdma_mode1)
    lda display_state
    cmp #1
    beq @scene
    cmp #2
    bne @menu
@scene:
    lda #$1620
    sta M7_HDMA_DISPLAY
    ldx #.loword(hdma_mode7)
    phx
    ldx selected_level
    lda level_view_insets,x
    and #255
    plx
    cmp #0
    beq :+
    lda #$1628
    sta M7_HDMA_DISPLAY
    ldx #.loword(hdma_mode7_inset)
:
    stx $4362
    ldx #M7_HDMA_DISPLAY
    bra @pointer
@menu:
    stx $4362
    ldx #.loword(hdma_hide)
@pointer:
    stx $4372
    rts

.ifdef SA1_BUILD
.segment "FASTNMI"
.endif
mode7_commit_map:
    stz pattern_skip_hud
.ifdef SA1_BUILD
    lda m7_row_count
    cmp #20
    bcc :+
    inc pattern_skip_hud
:
.endif
    lda display_state
    cmp #2
    bne :+
    rts
:
    lda m7_row_count
    jeq @done
    sep #$20
    .a8
    stz $2115
    stz $4300
    lda #$18
    sta $4301
    lda #.bankbyte(M7_STAGE_MAP)
    sta $4304
    rep #$20
    .a16
    ldx #0
    ldy m7_row_count
@span:
    lda f:M7_DMA_LIST,x
    sta $2116
    sta scratch
    lda f:M7_DMA_LIST+2,x
    cmp #5
    bcc @direct
    sta $4305
    lda scratch
    and #M7_STAGE_MASK
    clc
    adc #.loword(M7_STAGE_MAP)
    sta $4302
    lda #$C001
    sta $420B
    bra @span_done
@direct:
    sta pattern_raw
    phx
    lda scratch
    and #M7_STAGE_MASK
    tax
    lda pattern_raw
    cmp #2
    beq @two
    cmp #3
    beq @three
    cmp #4
    beq @four
    sep #$20
    .a8
    lda f:M7_STAGE_MAP,x
    sta $2118
    bra @direct_end
@two:
    rep #$20
    .a16
    lda f:M7_STAGE_MAP,x
    sep #$20
    .a8
    sta $2118
    xba
    sta $2118
    bra @direct_end
@three:
    rep #$20
    .a16
    lda f:M7_STAGE_MAP,x
    sep #$20
    .a8
    sta $2118
    xba
    sta $2118
    lda f:M7_STAGE_MAP+2,x
    sta $2118
    bra @direct_end
@four:
    rep #$20
    .a16
    lda f:M7_STAGE_MAP,x
    sep #$20
    .a8
    sta $2118
    xba
    sta $2118
    rep #$20
    .a16
    lda f:M7_STAGE_MAP+2,x
    sep #$20
    .a8
    sta $2118
    xba
    sta $2118
@direct_end:
    rep #$20
    .a16
    plx
@span_done:
    dey
    jeq @done
    inx
    inx
    inx
    inx
    jmp @span
@done:
    sep #$20
    .a8
    lda #$80
    sta $2115
    rep #$20
    .a16
    rts

mode7_commit_patterns:
    lda display_state
    cmp #2
    bne :+
    rts
:
    lda pattern_queue_count
    sta pattern_dma_index
    beq @done
    lda #1
    sta f:M7_HASH_DIRTY
    lda pattern_dma_index
    ldx m7_upload_slots
    cpx #4
    bcc :+
    inc pattern_skip_hud
:
    tay
    stz pattern_queue_count
    sep #$20
    .a8
    lda #$80
    sta $2115
    stz $4350
    lda #$19
    sta $4351
    lda #$7E
    sta $4354
    rep #$20
    .a16
    ldx #0
@pattern:
    lda f:PATTERN_QUEUE+4,x
    sta $2116
    lda f:PATTERN_QUEUE+2,x
    sep #$20
    .a8
    sta $4354
    rep #$20
    .a16
@source_bank:
    lda f:PATTERN_QUEUE,x
    sta $4352
    lda f:PATTERN_QUEUE+6,x
    sta $4355
    lda #$C020
    sta $420B
    phx
    lda f:PATTERN_QUEUE+8,x
    pha
    lda f:PATTERN_QUEUE+4,x
    .repeat 5
    lsr a
    .endrepeat
    tax
    pla
    sta f:M7_PATTERN_VRAM,x
    plx
    dey
    beq @done
    txa
    clc
    adc #16
    tax
    bra @pattern
@done:
    rts

.ifdef SA1_BUILD
.segment "CODE"
.endif
mode7_commit_camera:
    lda display_state
    cmp #1
    beq @scene
    cmp #2
    beq @frozen
    sep #$20
    .a8
    stz $212E
    rep #$20
    .a16
    rts
@frozen:
.ifdef SA1_BUILD
    lda f:M7_RASTER_DISPLAY_X
    sta f:M7_RASTER_X
    lda f:M7_RASTER_DISPLAY_Y
    sta f:M7_RASTER_Y
    lda f:M7_DISPLAY_BASE_X
    sta f:M7_STAGE_BASE_X
    lda f:M7_DISPLAY_BASE_Y
    sta f:M7_STAGE_BASE_Y
    lda f:M7_ROT_DISPLAY_PHASE
    sta f:M7_ROT_PHASE
    lda f:M7_ROT_DISPLAY_COS
    sta f:M7_ROT_COS
    lda f:M7_ROT_DISPLAY_SIN
    sta f:M7_ROT_SIN
.endif
    ; Death may interrupt an animation download. Keep the last published
    ; camera, map, patterns and OAM together, rather than showing a new
    ; projection against an older, partially updated texture.
    lda display_cam_x
    sta cam_x
    lda display_cam_y
    sta cam_y
    lda display_zoom
    sta camera_zoom
    lda display_inverse
    sta camera_inverse
@scene:
.ifdef SA1_BUILD
    lda f:M7_RASTER_X
    sta f:M7_RASTER_DISPLAY_X
    lda f:M7_RASTER_Y
    sta f:M7_RASTER_DISPLAY_Y
    lda f:M7_STAGE_BASE_X
    sta f:M7_DISPLAY_BASE_X
    lda f:M7_STAGE_BASE_Y
    sta f:M7_DISPLAY_BASE_Y
    lda f:M7_ROT_PHASE
    sta f:M7_ROT_DISPLAY_PHASE
    lda f:M7_ROT_COS
    sta f:M7_ROT_DISPLAY_COS
    lda f:M7_ROT_SIN
    sta f:M7_ROT_DISPLAY_SIN
.endif
    lda cam_x
    sta display_cam_x
    lda cam_y
    sta display_cam_y
    lda camera_zoom
    sta display_zoom
    lda camera_inverse
    sta display_inverse
    ldx #0
@table:
    lda M7_HDMA_STAGE,x
    sta M7_HDMA_DISPLAY,x
    inx
    inx
    cpx #32
    bcc @table
.ifdef SA1_BUILD
    lda f:M7_STAGE_BASE_X
    asl a
    asl a
    asl a
    sta scratch
    lda f:M7_RASTER_X
    sec
    sbc scratch
    clc
    adc #128
.else
    lda cam_x
    and #511
    clc
    adc #128
.endif
    sep #$20
    .a8
    sta $211F
    xba
    sta $211F
    rep #$20
    .a16
.ifdef SA1_BUILD
    lda f:M7_STAGE_BASE_Y
    asl a
    asl a
    asl a
    sta scratch
    lda f:M7_RASTER_Y
    sec
    sbc scratch
    clc
    adc #104
.else
    lda cam_y
    clc
    adc #32
    and #255
    clc
    adc #64
.endif
    sep #$20
    .a8
    sta $2120
    xba
    sta $2120
    rep #$20
    .a16
.ifdef SA1_BUILD
    lda f:M7_STAGE_BASE_X
    asl a
    asl a
    asl a
    sta scratch
    lda f:M7_RASTER_X
    sec
    sbc scratch
.else
    lda cam_x
    and #511
.endif
    sep #$20
    .a8
    sta $210D
    xba
    sta $210D
    rep #$20
    .a16
.ifdef SA1_BUILD
    lda f:M7_STAGE_BASE_Y
    asl a
    asl a
    asl a
    sta scratch
    lda f:M7_RASTER_Y
    sec
    sbc scratch
    dec a
.else
    lda cam_y
    clc
    adc #32
    and #255
    sec
    sbc #33
.endif
    sep #$20
    .a8
    sta $210E
    xba
    sta $210E
    rep #$20
    .a16
.ifdef SA1_BUILD
    lda f:M7_ROT_COS
    sep #$20
    .a8
    sta $211B
    xba
    sta $211B
    rep #$20
    .a16
    lda f:M7_ROT_COS
    sep #$20
    .a8
    sta $211E
    xba
    sta $211E
    rep #$20
    .a16
    lda f:M7_ROT_SIN
    sep #$20
    .a8
    sta $211C
    xba
    sta $211C
    rep #$20
    .a16
    lda f:M7_ROT_SIN
    eor #$FFFF
    inc a
    sep #$20
    .a8
    sta $211D
    xba
    sta $211D
    rep #$20
    .a16
.else
    lda camera_zoom
    sep #$20
    .a8
    sta $211B
    xba
    sta $211B
    rep #$20
    .a16
    lda camera_zoom
    sep #$20
    .a8
    sta $211E
    xba
    sta $211E
    stz $211C
    stz $211C
    stz $211D
    stz $211D
    rep #$20
    .a16
.endif
    sep #$20
    .a8
    stz $211A
    lda m7_window_left
    sta $2126
    lda m7_window_right
    sta $2127
    lda #$11
    sta $212E
    rep #$20
    .a16
    rts
