.ifdef SA1_MODE1_BUILD
; Use the same icon order, clipping, and 16px OAM budget as sprite().
worker_mode1_icons:
    lda #0
    sta f:SPILL_OAM_BYTES
    stz map_x
    ldx #0
@clear:
    sta f:SPILL_OAM_HIGH,x
    inx
    inx
    cpx #32
    bcc @clear
@floor:
    lda map_x
    cmp f:SYMBOL_VISIBLE_COUNT
    jcs @done
    tax
    lda f:SYMBOL_SCREEN_X,x
    sta view_x
    lda f:SYMBOL_SCREEN_Y,x
    sta view_count
    lda f:SYMBOL_VISIBLE,x
    sta map_y
    tax
    lda f:NATIVE_ALPHA,x
    and #255
    jeq @next_floor
    txa
    .repeat 4
    asl a
    .endrepeat
    sta map_base_ptr
    tax
    ; Empty descriptor slots need only a load and branch. Most floors
    ; have one symbol; avoid walking four general-purpose loop iterations.
    .repeat 4, ICON
    lda f:M1_ICON_INFO+ICON*4,x
    beq :+
    sta map_dest
    lda #ICON*4
    sta view_rows
    jsr worker_mode1_place
    ldx map_base_ptr
:
    .endrepeat
@next_floor:
    inc map_x
    inc map_x
    jmp @floor
@done:
    rts

worker_mode1_place:
    lda map_base_ptr
    clc
    adc view_rows
    tax
    lda view_rows
    cmp #12
    bne @place
    lda f:M1_ICON_ATTACK
    bne @done
    lda f:M1_ICON_CHECKPOINT
    cmp #$FFFF
    beq @place
    cmp map_y
    bcc @place
    inc map_dest
    inc map_dest
@place:
    lda f:M1_ICON_INFO+2,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    pha
    ldx map_x
    lda f:SYMBOL_SCREEN_X,x
    clc
    adc 1,s
    sta view_x
    pla
    lda map_base_ptr
    clc
    adc view_rows
    tax
    lda f:M1_ICON_INFO+3,x
    and #255
    cmp #128
    bcc :+
    ora #$FF00
:
    clc
    adc view_count
    sta view_y
    jmp worker_mode1_icon_sprite
@done:
    rts

worker_mode1_icon_sprite:
    lda view_x
    cmp #$FFF1
    bcs worker_icon_x_inside
    cmp #256
    jcs worker_icon_done
worker_icon_x_inside:
    lda view_y
    cmp #32
    jcc worker_icon_done
    cmp #177
    jcs worker_icon_done
    lda f:SPILL_OAM_BYTES
    clc
    adc f:SPILL_OAM_PREFIX
    cmp #512
    jcs worker_icon_done
    sta map_left
    lda view_y
    lsr a
    lsr a
    lsr a
    sta scratch
    tax
    lda view_y
    clc
    adc #15
    lsr a
    lsr a
    lsr a
    sta scratch2
worker_icon_check:
    lda f:SPILL_OAM_BUDGET,x
    and #255
    cmp #32
    jcs worker_icon_done
    inx
    cpx scratch2
    bcc worker_icon_check
    beq worker_icon_check
    ldx scratch
worker_mode1_icon_charge:
    sep #$20
    .a8
worker_icon_charge:
    lda f:SPILL_OAM_BUDGET,x
    inc a
    inc a
    sta f:SPILL_OAM_BUDGET,x
    inx
    cpx scratch2
    bcc worker_icon_charge
    beq worker_icon_charge
    rep #$20
    .a16
worker_mode1_icon_append:
    lda f:SPILL_OAM_BYTES
    tax
    lda view_y
    xba
    and #$FF00
    sta scratch
    lda view_x
    and #255
    ora scratch
    sta f:SPILL_OAM_OUT,x
    lda map_dest
    sta f:SPILL_OAM_OUT+2,x
    lda map_left
    and #12
    lsr a
    tax
    lda f:$010000+mode1_icon_sizes,x
    sta scratch
    lda view_x
    bpl worker_icon_high
    lda scratch
    lsr a
    ora scratch
    sta scratch
worker_icon_high:
    lda map_left
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda f:SPILL_OAM_HIGH,x
    ora scratch
    sta f:SPILL_OAM_HIGH,x
    rep #$20
    .a16
    lda f:SPILL_OAM_BYTES
    clc
    adc #4
    sta f:SPILL_OAM_BYTES
worker_icon_done:
    rts
mode1_icon_sizes:
    .word 2,8,32,128
.endif
