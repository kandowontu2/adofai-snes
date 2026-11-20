.segment "NEOCODE"
planet_scale_update:
    lda #256
    sta planet_scale_values
    sta planet_scale_values+2
    sta planet_scale_values+4
    lda selected_level
    inc a
    cmp planet_scale_level
    beq @cached_level
    sta planet_scale_level
    ldx #0
@level:
    lda selected_level
    cmp f:planet_scale_levels,x
    beq @found
    inx
    inx
    cpx #PLANET_SCALE_LEVEL_COUNT*2
    bcc @level
    lda #$FFFF
    sta planet_scale_entry
    rtl
@cached_level:
    ldx planet_scale_entry
    cpx #$FFFF
    bne @found
    rtl
@found:
    stx planet_scale_entry
.ifdef PLANET_SCALE_CALLBACK_BUILD
    lda f:planet_scale_callback_ends,x
    pha
    lda f:planet_scale_callback_starts,x
    pha
.endif
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
.ifdef PLANET_SCALE_CALLBACK_BUILD
    pla
    tax
    pla
    sta scratch2
    phy
@callback:
    cpx scratch2
    bcs @callbacks_done
    lda f:planet_scale_callbacks+2,x
    cmp chart_time
    bcc @next_callback
    beq @next_callback
    lda f:planet_scale_callbacks,x
    cmp step
    bcc @judged_callback
    bne @next_callback
@judged_callback:
    phx
    lda f:planet_scale_callbacks,x
    tax
    lda f:NOTE_FLAGS,x
    bit #8
    bne @automatic_callback
    lda f:NOTE_JUDGMENTS,x
    and #255
    ; Native IsPerfect includes XPerfect and its PerfectMinus/Plus bands.
    ; Early/late perfect use separate callback tags. Stored grade is +1.
    cmp #4
    bcc @not_perfect_callback
    cmp #7
    bcs @not_perfect_callback
@automatic_callback:
    plx
    lda f:planet_scale_callbacks+4,x
    tay
    lda f:planet_scale_callbacks+6,x
    sta planet_scale_values,y
    bra @next_callback
@not_perfect_callback:
    plx
@next_callback:
    txa
    clc
    adc #8
    tax
    bra @callback
@callbacks_done:
    ply
.endif
planet_scale_update_done:
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
