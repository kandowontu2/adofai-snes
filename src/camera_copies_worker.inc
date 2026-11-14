; Signed Q4 positions and Q8 rotations. Planets remain upright billboards;
; the four artwork quadrants share a transformed parent center.
.segment "CODE"
C_SRC=$0500
C_VIEW=C_SRC+2
C_N=C_SRC+4
C_HALF=C_SRC+6
C_HI=C_SRC+8
C_TILE=C_SRC+10
C_X=C_SRC+12
C_Y=C_SRC+14
C_DX=C_SRC+16
C_DY=C_SRC+18
C_OX=C_SRC+20
C_OY=C_SRC+22
C_COS=C_SRC+24
C_SIN=C_SRC+26
C_PHASE=C_SRC+28
C_MUL=C_SRC+30
C_LEFT=C_SRC+32
C_RIGHT=C_SRC+34
C_OLD=C_SRC+36
C_NEW=C_SRC+38
C_ROW=C_SRC+40
C_EXACT=C_SRC+42
C_BIN_FIRST=C_SRC+44
C_BIN_LAST=C_SRC+46
worker_camera_copies:
    phb
    ldx #__HOTCOPIES_LOAD__
    ldy #__HOTCOPIES_RUN__
    lda #__HOTCOPIES_SIZE__-1
    mvn #$01,#$00
    plb
    jmp worker_camera_copies_hot
.segment "HOTCOPIES"
worker_camera_copies_hot:
    phb
    sep #$20
    .a8
    lda #0
    pha
    plb
    lda #0
    sta f:$002250
    rep #$20
    .a16
    lda #0
    sta a:C_N
    sta a:C_SRC
    sta a:C_EXACT
    ldx #0
@coarse_clear:
    sta f:CLONE_LINES,x
    sta a:$0480,x
    inx
    inx
    cpx #64
    bcc @coarse_clear
    ldx #0
@clear:
    sta a:$0530,x
    inx
    inx
    cpx #448
    bcc @clear
    ldx #0
@high:
    sta f:CLONE_OUTPUT+512,x
    inx
    inx
    cpx #32
    bcc @high
@source:
    ldx a:C_SRC
    txa
    cmp f:CLONE_INPUT_BYTES
    jcs @done
    lda f:CLONE_INPUT+1,x
    and #255
    cmp #224
    jeq @next_source
    sta a:C_Y
    lda f:CLONE_INPUT+2,x
    sta a:C_TILE
    txa
    and #12
    lsr a
    tax
    lda f:$010000+clone_shifts,x
    tay
    lda a:C_SRC
    .repeat 4
    lsr a
    .endrepeat
    tax
    lda f:CLONE_INPUT+512,x
@shift:
    cpy #0
    beq @shift_done
    lsr a
    dey
    bra @shift
@shift_done:
    and #3
    sta a:C_HI
    ldx a:C_SRC
    lda f:CLONE_INPUT,x
    and #255
    ldy a:C_HI
    tya
    and #1
    beq @positive
    lda f:CLONE_INPUT,x
    ora #$FF00
    bra @have_x
@positive:
    lda f:CLONE_INPUT,x
    and #255
@have_x:
    sta a:C_X
    lda #4
    ldy a:C_HI
    cpy #2
    bcc :+
    lda #8
:
    sta a:C_HALF
    lda #0
    sta a:C_DX
    sta a:C_DY
    lda a:C_SRC
    cmp #32
    bcs @views
    and #$FFF0
    tax
    lda f:CLONE_INPUT+9,x
    and #255
    cmp #224
    beq @views
    lda a:C_SRC
    and #4
    beq :+
    lda #8
    bra @quad_x
:
    lda #$FFF8
@quad_x:
    sta a:C_DX
    lda a:C_SRC
    and #8
    beq :+
    lda #8
    bra @quad_y
:
    lda #$FFF8
@quad_y:
    sta a:C_DY
@views:
    lda f:CLONE_COUNT
    dec a
    sta a:C_VIEW
@view:
    lda a:C_VIEW
    cmp #$FFFF
    jeq @next_source
    ldx a:C_SRC
    lda f:CLONE_INPUT+2,x
    sta a:C_TILE
    lda a:C_VIEW
    asl a
    asl a
    clc
    adc a:C_VIEW
    asl a
    tax
    lda f:CLONE_PARAMS,x
    sta a:C_COS
    lda f:CLONE_PARAMS+2,x
    sta a:C_SIN
    lda f:CLONE_PARAMS+8,x
    sta a:C_PHASE
    phx
    jsr clone_arc_setup
    plx
    lda a:C_X
    clc
    adc a:C_HALF
    sec
    sbc a:C_DX
    sec
    sbc #128
    .repeat 4
    asl a
    .endrepeat
    clc
    adc f:CLONE_PARAMS+4,x
    sta a:C_OX
    lda a:C_Y
    clc
    adc a:C_HALF
    sec
    sbc a:C_DY
    sec
    sbc #104
    .repeat 4
    asl a
    .endrepeat
    clc
    adc f:CLONE_PARAMS+6,x
    sta a:C_OY
    jsr clone_rotate_parent
    jsr clone_arc_finish
    lda a:C_LEFT
    jsr clone_round
    clc
    adc #128
    clc
    adc a:C_DX
    sec
    sbc a:C_HALF
    sta a:C_LEFT
    bmi @negative_x
    cmp #256
    jcs @next_view
    bra @clip_y
@negative_x:
    clc
    adc a:C_HALF
    adc a:C_HALF
    bpl @clip_y
    jmp @next_view
@clip_y:
    lda a:C_RIGHT
    jsr clone_round
    clc
    adc #104
    clc
    adc a:C_DY
    sec
    sbc a:C_HALF
    sta a:C_RIGHT
    cmp #177
    jcs @next_view
    clc
    adc a:C_HALF
    adc a:C_HALF
    cmp #33
    jcc @next_view
    lda a:C_N
    cmp #512
    jcs @done
    lda a:C_RIGHT
    cmp #32
    bcs :+
    lda #32
:
    sta a:C_ROW
    tax
    lda a:C_RIGHT
    clc
    adc a:C_HALF
    adc a:C_HALF
    cmp #177
    bcc :+
    lda #177
:
    sta scratch2
    lda a:C_HALF
    lsr a
    lsr a
    sta scratch
    jsr clone_coarse_budget
    bcc @copy_output
    ldx a:C_ROW
@budget:
    lda a:$0530,x
    and #255
    cmp #32
    jcs @next_view
    lda a:$0610,x
    and #255
    clc
    adc scratch
    cmp #35
    jcs @next_view
    inx
    cpx scratch2
    bcc @budget
    ldx a:C_ROW
    sep #$20
    .a8
@charge:
    lda a:$0530,x
    inc a
    sta a:$0530,x
    lda a:$0610,x
    clc
    adc scratch
    sta a:$0610,x
    inx
    cpx scratch2
    bcc @charge
    rep #$20
    .a16
@copy_output:
    ldx a:C_N
    lda a:C_RIGHT
    xba
    and #$FF00
    sta scratch
    lda a:C_LEFT
    and #255
    ora scratch
    sta f:CLONE_OUTPUT,x
    lda a:C_TILE
    sta f:CLONE_OUTPUT+2,x
    lda a:C_HI
    and #2
    sta scratch
    lda a:C_LEFT
    bpl :+
    inc scratch
:
    txa
    and #12
    lsr a
    tax
    lda f:$010000+clone_shifts,x
    tay
    lda scratch
@encode_high:
    cpy #0
    beq @encode_done
    asl a
    dey
    bra @encode_high
@encode_done:
    sta scratch
    lda a:C_N
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda f:CLONE_OUTPUT+512,x
    ora scratch
    sta f:CLONE_OUTPUT+512,x
    rep #$20
    .a16
    lda a:C_N
    clc
    adc #4
    sta a:C_N
@next_view:
    lda a:C_VIEW
    dec a
    sta a:C_VIEW
    jmp @view
@next_source:
    lda a:C_SRC
    clc
    adc #4
    sta a:C_SRC
    jmp @source
@done:
    lda a:C_N
    sta f:CLONE_OUTPUT_BYTES
    lda #0
    sta M7_CACHE_CODE_VALID
    sta M7_ROW_CODE_VALID
    lda #1
    sta f:M7_HASH_DIRTY
    plb
    rts

clone_multiply:
    sta f:$002251
    txa
    sta f:$002253
    nop
    nop
    nop
    nop
    lda f:$002307
    rts
clone_round:
    clc
    adc #8
    .repeat 4
    cmp #$8000
    ror a
    .endrepeat
    rts
clone_shifts: .word 0,2,4,6

.segment "CODE"
clone_rotate_parent:
    ; Quadrants and streak cells share the same parent center. Keep one
    ; exact fixed-point result per camera; no phase/position quantization.
    lda a:C_VIEW
    asl a
    asl a
    asl a
    asl a
    tax
    lda a:$0480,x
    beq @calculate
    lda a:$0482,x
    cmp a:C_OX
    bne @calculate
    lda a:$0484,x
    cmp a:C_OY
    bne @calculate
    lda a:$0486,x
    sta a:C_LEFT
    lda a:$0488,x
    sta a:C_RIGHT
    rts
@calculate:
    phx
    lda a:C_OX
    ldx a:C_COS
    jsr clone_multiply
    sta a:C_MUL
    lda a:C_OY
    ldx a:C_SIN
    jsr clone_multiply
    eor #$FFFF
    inc a
    clc
    adc a:C_MUL
    sta a:C_LEFT
    lda a:C_OX
    ldx a:C_SIN
    jsr clone_multiply
    sta a:C_MUL
    lda a:C_OY
    ldx a:C_COS
    jsr clone_multiply
    clc
    adc a:C_MUL
    sta a:C_RIGHT
    plx
    sta a:$0488,x
    lda a:C_LEFT
    sta a:$0486,x
    lda a:C_OX
    sta a:$0482,x
    lda a:C_OY
    sta a:$0484,x
    lda #1
    sta a:$0480,x
    rts

clone_coarse_budget:
    ; Most copied scenes fit comfortably in coarse eight-line bins. The
    ; first conservative rejection reconstructs exact scanline counts from
    ; all admitted objects, then uses the exact path for the rest of the job.
    ; A coarse overflow therefore never discards a sprite.
    lda a:C_EXACT
    bne @exact
    lda a:C_ROW
    lsr a
    lsr a
    lsr a
    asl a
    sta a:C_BIN_FIRST
    tax
    lda scratch2
    dec a
    lsr a
    lsr a
    lsr a
    asl a
    sta a:C_BIN_LAST
@check:
    lda f:CLONE_LINES,x
    and #255
    cmp #32
    bcs @rebuild
    lda f:CLONE_LINES,x
    xba
    and #255
    clc
    adc scratch
    cmp #35
    bcs @rebuild
    inx
    inx
    cpx a:C_BIN_LAST
    bcc @check
    beq @check
    lda scratch
    xba
    ora #1
    pha
    ldx a:C_BIN_FIRST
@charge:
    lda f:CLONE_LINES,x
    clc
    adc 1,s
    sta f:CLONE_LINES,x
    inx
    inx
    cpx a:C_BIN_LAST
    bcc @charge
    beq @charge
    pla
    clc
    rts
@rebuild:
    lda scratch
    pha
    lda scratch2
    pha
    jsr clone_rebuild_lines
    pla
    sta scratch2
    pla
    sta scratch
    lda #1
    sta a:C_EXACT
@exact:
    sec
    rts

clone_rebuild_lines:
    stz map_left
@object:
    lda map_left
    cmp a:C_N
    bcs @done
    and #12
    lsr a
    tax
    lda f:$010000+clone_shifts,x
    tay
    lda map_left
    .repeat 4
    lsr a
    .endrepeat
    tax
    lda f:CLONE_OUTPUT+512,x
@shift:
    cpy #0
    beq @size
    lsr a
    dey
    bra @shift
@size:
    and #2
    lsr a
    inc a
    sta scratch
    asl a
    asl a
    asl a
    sta map_dest
    ldx map_left
    lda f:CLONE_OUTPUT+1,x
    and #255
    tax
    clc
    adc map_dest
    cmp #177
    bcc :+
    lda #177
:
    sta map_scan_x
    cpx #32
    bcs :+
    ldx #32
:
    sep #$20
    .a8
@line:
    lda a:$0530,x
    inc a
    sta a:$0530,x
    lda a:$0610,x
    clc
    adc scratch
    sta a:$0610,x
    inx
    cpx map_scan_x
    bcc @line
    rep #$20
    .a16
    lda map_left
    clc
    adc #4
    sta map_left
    bra @object
@done:
    rts

clone_arc_setup:
    ; Planet billboards keep their original pixels. Trail cells use the
    ; matching pre-rendered arc orientation and its own rotated origin.
    lda a:C_SRC
    cmp #32
    jcc @done
    lda a:C_TILE
    and #255
    cmp #128
    jcc @done
    and #15
    sta a:C_OLD
    lda a:C_TILE
    and #$C000
    cmp #$4000
    beq @mirror
    cmp #$8000
    bne @phase
@mirror:
    lda #15
    sec
    sbc a:C_OLD
    sta a:C_OLD
@phase:
    lda a:C_TILE
    and #$8000
    beq :+
    lda #32
:
    sta scratch
    lda a:C_TILE
    and #$C000
    cmp #$8000
    bne :+
    lda #48
    sta scratch
:
    lda a:C_TILE
    and #$C000
    cmp #$4000
    bne :+
    lda #16
    sta scratch
:
    lda a:C_OLD
    clc
    adc scratch
    sta a:C_OLD
    clc
    adc a:C_PHASE
    and #63
    sta a:C_NEW
    tax
    lda f:orbit_arc_tiles,x
    and #255
    sta scratch
    lda a:C_TILE
    and #$3F70
    ora scratch
    sta a:C_TILE
    lda f:orbit_arc_flips,x
    and #255
    xba
    ora a:C_TILE
    sta a:C_TILE
    lda a:C_OLD
    asl a
    tax
    lda f:orbit_arc_x,x
    clc
    adc #4
    sta a:C_DX
    lda f:orbit_arc_y,x
    clc
    adc #4
    sta a:C_DY
@done:
    rts

clone_arc_finish:
    lda a:C_SRC
    cmp #32
    bcc @done
    lda a:C_TILE
    and #255
    cmp #128
    bcc @done
    lda a:C_NEW
    asl a
    tax
    lda f:orbit_arc_x,x
    clc
    adc #4
    sta a:C_DX
    lda f:orbit_arc_y,x
    clc
    adc #4
    sta a:C_DY
@done:
    rts
