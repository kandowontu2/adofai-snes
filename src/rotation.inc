.segment "CAMERA"
; Reject off-screen event symbols before starting a separate SA-1 IRQ.
; Bounds enclose the rotated viewport plus a conservative sprite margin.
camera_projection_limits:
    lda f:M7_ROT_COS
    bpl :+
    eor #$FFFF
    inc a
:
    sta scratch
    lda f:M7_ROT_SIN
    bpl :+
    eor #$FFFF
    inc a
:
    sta scratch2
    lda scratch
    asl a
    clc
    adc scratch2
    .repeat 3
    asl a
    .endrepeat
    clc
    adc scratch2
    jsr camera_projection_extent
    sta project_limit_x
    lda scratch2
    asl a
    clc
    adc scratch
    .repeat 3
    asl a
    .endrepeat
    clc
    adc scratch
    jsr camera_projection_extent
    sta project_limit_y
    rtl
camera_projection_extent:
    clc
    adc #31
    .repeat 5
    lsr a
    .endrepeat
    clc
    adc #32
    pha
    lda f:M7_RASTER_SHIFT
    beq @native
    pla
    asl a
    rts
@native:
    pla
    rts

; SA-1 cartridges keep the enlarged map staging buffer in cartridge RAM.
; The SA-1 arithmetic unit projects OBJ centers through the same matrix.
mode7_rotation_bounds:
    lda cam_x
    clc
    adc #128
    pha
    lda f:M7_RASTER_SHIFT
    beq @native_x
    pla
    cmp #$8000
    ror a
    bra @raster_x
@native_x:
    pla
@raster_x:
    sec
    sbc #128
    sta f:M7_RASTER_X
    lda cam_y
    clc
    adc #104
    pha
    lda f:M7_RASTER_SHIFT
    beq @native_y
    pla
    cmp #$8000
    ror a
    bra @raster_y
@native_y:
    pla
@raster_y:
    sec
    sbc #104
    sta f:M7_RASTER_Y
    lda f:M7_ROT_COS
    bpl :+
    eor #$FFFF
    inc a
:
    sta f:ROT_X
    lda f:M7_ROT_SIN
    bpl :+
    eor #$FFFF
    inc a
:
    sta f:ROT_Y
    lda f:ROT_X
    asl a
    clc
    adc f:ROT_Y
    .repeat 3
    asl a
    .endrepeat
    clc
    adc f:ROT_Y
    clc
    adc #31
    .repeat 5
    lsr a
    .endrepeat
    sta f:ROT_SUM
    lda f:M7_RASTER_X
    clc
    adc #128
    sec
    sbc f:ROT_SUM
    .repeat 3
    cmp #$8000
    ror a
    .endrepeat
    sta f:M7_VIEW_X
    lda f:ROT_SUM
    asl a
    clc
    adc #14
    lsr a
    lsr a
    lsr a
    sta f:M7_VIEW_W
    lda f:ROT_Y
    asl a
    clc
    adc f:ROT_X
    .repeat 3
    asl a
    .endrepeat
    clc
    adc f:ROT_X
    clc
    adc #31
    .repeat 5
    lsr a
    .endrepeat
    sta f:ROT_SUM
    lda f:M7_RASTER_Y
    clc
    adc #104
    sec
    sbc f:ROT_SUM
    .repeat 3
    cmp #$8000
    ror a
    .endrepeat
    sta f:M7_VIEW_Y
    lda f:ROT_SUM
    asl a
    clc
    adc #14
    lsr a
    lsr a
    lsr a
    sta f:M7_VIEW_H
    cmp #29
    bcs @large_view
    cmp #21
    bcs @medium_view
    lda #16
    bra @limit
@medium_view:
    lda #10
    bra @limit
@large_view:
    cmp #37
    bcc :+
    lda #4
    bra @limit
:
    ; Wide rotated views can need 37 scattered map spans. Reserve enough
    ; VBlank for their per-span setup even when all eight slots are dirty.
    lda #6
@limit:
    sta f:M7_UPLOAD_LIMIT
    rtl

.segment "FASTWRAM"
mode7_rotate_project:
    lda floor_x
    sec
    sbc cam_x
    sec
    sbc #128
    sta f:ROT_X
    bpl :+
    eor #$FFFF
    inc a
:
    cmp project_limit_x
    jcs @hidden
    lda floor_y
    sec
    sbc cam_y
    sec
    sbc #104
    sta f:ROT_Y
    bpl :+
    eor #$FFFF
    inc a
:
    cmp project_limit_y
    jcs @hidden
    lda #0
    sta f:SA1_DONE
    lda #2
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2200
    rep #$20
    .a16
@project_wait:
    lda f:SA1_DONE
    beq @project_wait
    lda f:$40002C
    clc
    adc #120
    sta sprite_x
    lda f:$40002E
    clc
    adc #96
    sta sprite_y
    rtl
@hidden:
    lda #$F000
    sta sprite_x
    sta sprite_y
    rtl

; Signed small world-space offsets, scaled independently of cache jobs.
; NMI never uses the SNES multiplier; SA-1 owns its separate multiplier.
.segment "FASTNMI"
camera_scale_offset:
    phx
    pha
    lda camera_inverse
    cmp #256
    bne @scale
    pla
    plx
    rtl
@scale:
    pla
    pha
    bpl :+
    eor #$FFFF
    inc a
:
    sep #$20
    .a8
    sta $4202
    lda camera_inverse
    sta $4203
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4216
    clc
    adc #128
    xba
    and #255
    tax
    sep #$20
    .a8
    lda camera_inverse+1
    sta $4203
    nop
    nop
    nop
    nop
    rep #$20
    .a16
    lda $4216
    pha
    txa
    clc
    adc 1,s
    tax
    pla
    pla
    bpl @positive
    txa
    eor #$FFFF
    inc a
    bra @done
@positive:
    txa
@done:
    plx
    rtl

.segment "CAMERA"
camera_scale_sprite:
    pha
    lda camera_inverse
    cmp #256
    bne @scaled
    pla
    rtl
@scaled:
    pla
    asl a
    clc
    adc #7
    jsl camera_scale_offset
    sec
    sbc #7
    cmp #$8000
    ror a
    rtl

camera_orb_radius:
    lda #7
    jsl camera_scale_offset
    cmp #3
    bcs :+
    lda #3
:
    cmp #15
    bcc :+
    lda #14
:
    rtl

.ifdef ZERO_PAUSE_TABLES
clear_pause_array:
    phx
    ldx #0
    lda #0
@clear:
    sta f:NOTE_PAUSE,x
    inx
    inx
    cpx transfer_len
    bcc @clear
    plx
    rtl
.endif

.ifdef LARGE_CHART_BUILD
; transfer_dest and transfer_wbank form a long indirect pointer here.
upload_cartridge_arrays:
    phy
    ldy #0
    sep #$20
    .a8
@byte:
    lda [transfer_ptr],y
    sta [transfer_dest],y
    iny
    cpy transfer_len
    bcc @byte
    rep #$20
    .a16
    ply
    rtl
.endif
.segment "CODE"
