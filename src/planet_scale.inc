.segment "NEOCODE"
planet_scale_update:
    lda #256
    sta planet_scale_values
    sta planet_scale_values+2
    sta planet_scale_values+4
    ldx #0
@level:
    lda selected_level
    cmp f:planet_scale_levels,x
    beq @found
    inx
    inx
    cpx #PLANET_SCALE_LEVEL_COUNT*2
    bcc @level
    rtl
@found:
    lda f:planet_scale_starts,x
    sta scratch
    lda f:planet_scale_ends,x
    sta scratch2
@search:
    lda scratch
    cmp scratch2
    bcs @result
    clc
    adc scratch2
    lsr a
    and #$FFF8
    tax
    lda f:planet_scale_rows,x
    cmp chart_time
    beq @row
    bcc @lower
    stx scratch2
    bra @search
@lower:
    txa
    clc
    adc #8
    sta scratch
    bra @search
@result:
    lda scratch
    sec
    sbc #8
    tax
@row:
    lda f:planet_scale_rows+2,x
    sta planet_scale_values
    lda f:planet_scale_rows+4,x
    sta planet_scale_values+2
    lda f:planet_scale_rows+6,x
    sta planet_scale_values+4
    rtl

planet_scaled_radius:
    lda sprite_attr
    and #6
    tax
    lda planet_scale_values,x
    ora m7_radius
    tax
    lda f:planet_scale_radii,x
    and #255
    rtl
.segment "CODE"
