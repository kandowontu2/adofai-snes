; Native-scale streak geometry and OAM budgeting form one bounded SA-1 job.
; The input budget belongs to the complete planet/track/symbol prefix.
worker_arc:
    phb
    sep #$20
    .a8
    lda #.bankbyte(TRAIL_JOB)
    pha
    plb
    rep #$20
    .a16
    ; Keep per-piece counters in private direct-page words. The complete
    ; result is published once, after the bounded job has finished.
    lda a:.loword(TRAIL_JOB+4)
    sta map_x
    lda a:.loword(TRAIL_JOB+8)
    sta map_y
    lda #0
    sta view_count
    sta view_rows
    ldx #0
@clear_high:
    sta a:.loword(TRAIL_JOB_HIGH),x
    inx
    inx
    cpx #32
    bcc @clear_high
@piece:
    lda view_rows
    lsr a
    clc
    adc a:.loword(TRAIL_JOB+10)
    cmp #4
    jcs @done
    .repeat 4
    asl a
    .endrepeat
    sta scratch
    lda map_x
    tax
    lda f:orbit_arc_tiles,x
    and #255
    clc
    adc scratch
    sta map_dest
    lda a:.loword(TRAIL_JOB+12)
    asl a
    clc
    adc #$38
    sta scratch
    lda f:orbit_arc_flips,x
    and #255
    ora scratch
    xba
    ora map_dest
    sta map_dest
    txa
    asl a
    tax
    lda f:orbit_arc_x,x
    clc
    adc a:.loword(TRAIL_JOB)
    sta view_x
    cmp #$FFF1
    bcs @x_ok
    cmp #256
    jcs @done
@x_ok:
    lda f:orbit_arc_y,x
    clc
    adc a:.loword(TRAIL_JOB+2)
    sta view_y
    cmp #32
    jcc @done
    cmp #177
    jcs @done
    lsr a
    lsr a
    lsr a
    tax
    stx scratch
    lda view_y
    clc
    adc #7
    lsr a
    lsr a
    lsr a
    sta scratch2
@check:
    lda a:.loword(TRAIL_JOB_BUDGET),x
    and #255
    cmp #33
    jcs @done
    inx
    cpx scratch2
    bcc @check
    beq @check
    lda view_count
    asl a
    asl a
    clc
    adc a:.loword(TRAIL_JOB+14)
    cmp #512
    jcs @done
    sta map_left
    ldx scratch
    sep #$20
    .a8
@charge:
    lda a:.loword(TRAIL_JOB_BUDGET),x
    inc a
    sta a:.loword(TRAIL_JOB_BUDGET),x
    inx
    cpx scratch2
    bcc @charge
    beq @charge
    rep #$20
    .a16
    lda view_count
    asl a
    asl a
    tax
    lda view_y
    xba
    and #$FF00
    sta scratch
    lda view_x
    and #255
    ora scratch
    sta a:.loword(TRAIL_JOB_OAM),x
    lda map_dest
    sta a:.loword(TRAIL_JOB_OAM+2),x
    lda view_x
    bpl @added
    lda map_left
    and #12
    lsr a
    tax
    lda f:$010000+@x_high,x
    sta scratch
    lda map_left
    .repeat 4
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda a:.loword(TRAIL_JOB_HIGH),x
    ora scratch
    sta a:.loword(TRAIL_JOB_HIGH),x
    rep #$20
    .a16
@added:
    lda view_count
    inc a
    sta view_count
    lda map_x
    clc
    adc a:.loword(TRAIL_JOB+6)
    and #63
    sta map_x
    lda view_rows
    inc a
    sta view_rows
    lda map_y
    dec a
    sta map_y
    jne @piece
@done:
    lda map_x
    sta a:.loword(TRAIL_JOB+4)
    lda map_y
    sta a:.loword(TRAIL_JOB+8)
    lda view_count
    sta a:.loword(TRAIL_JOB+16)
    lda view_rows
    sta a:.loword(TRAIL_JOB+20)
    plb
    rts
@x_high:
    .word 1,4,16,64
