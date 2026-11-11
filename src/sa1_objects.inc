; Append essential 8px track objects as one job. Input cells already obey
; the sprite clip bounds; keep their original order and per-line budget.
.ifdef SA1_WRAM_RENDERER
.segment "HOTOBJECTS"
.endif
worker_spill_objects:
    lda #0
    sta f:SPILL_OAM_BYTES
    stz map_scan_x
    stz m7_run_index
    ldx #0
@clear_high:
    sta f:SPILL_OAM_HIGH,x
    inx
    inx
    cpx #32
    bcc @clear_high
@cell:
    lda m7_run_index
    cmp f:SPILL_VISIBLE
    jcs @done
    lda f:SPILL_OAM_BYTES
    clc
    adc f:SPILL_OAM_PREFIX
    cmp #512
    jcs @done
    sta map_left
    ldx map_scan_x
    lda f:SPILL_FRAME,x
    sta view_x
    lda f:SPILL_FRAME+2,x
    sta view_y
    lsr a
    lsr a
    lsr a
    sta scratch
    tax
    lda view_y
    clc
    adc #7
    lsr a
    lsr a
    lsr a
    sta scratch2
@check:
    lda f:SPILL_OAM_BUDGET,x
    and #255
    cmp #33
    jcs @next
    inx
    cpx scratch2
    bcc @check
    beq @check
    ldx scratch
    sep #$20
    .a8
@charge:
    lda f:SPILL_OAM_BUDGET,x
    inc a
    sta f:SPILL_OAM_BUDGET,x
    inx
    cpx scratch2
    bcc @charge
    beq @charge
    rep #$20
    .a16
    ldx map_scan_x
    lda f:SPILL_FRAME+4,x
    and #255
    ora #$2100
    sta map_dest
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
    lda view_x
    bpl @added
    lda map_left
    and #12
    lsr a
    tax
.ifdef SA1_WRAM_RENDERER
    lda f:@x_high,x
.else
    lda f:$010000+@x_high,x
.endif
    sta scratch
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
@added:
    lda f:SPILL_OAM_BYTES
    clc
    adc #4
    sta f:SPILL_OAM_BYTES
@next:
    lda map_scan_x
    clc
    adc #6
    sta map_scan_x
    inc m7_run_index
    jmp @cell
@done:
    rts
@x_high:
    .word 1,4,16,64
.segment "CODE"
